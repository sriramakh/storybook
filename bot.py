#!/usr/bin/env python3
"""
StoryBook Generator — Telegram Bot Interface
=============================================
An async Telegram bot that drives the StoryBook generation pipeline
via a ConversationHandler.

Usage:
    python bot.py

Requires TELEGRAM_BOT_TOKEN and ALLOWED_USER_IDS in .env.
"""

import asyncio
import logging
import os
import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from story_generator import StoryGenerator
from image_generator import ImageGenerator
from text_overlay import TextOverlay
from pdf_compiler import StoryBookPDF
from character_registry import CharacterRegistry
from utils import (
    sanitize_folder_name,
    get_next_story_number,
    create_story_folder,
    save_story_json,
)

# ── Logging ───────────────────────────────────────────────────────────────── #

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("storybook.bot")

# ── Conversation states ───────────────────────────────────────────────────── #

(
    CHOOSING_PROVIDER,
    CHOOSING_STYLE,
    CHOOSING_MODE,
    ENTERING_DESCRIPTION,
    CHOOSING_SCENES,
    REVIEWING_STORY,
    GENERATING_IMAGES,
    STORY_COMPLETE,
) = range(8)

# ── Parse allowed user IDs ────────────────────────────────────────────────── #


def _parse_allowed_users() -> list[int]:
    raw = Config.ALLOWED_USER_IDS
    if not raw:
        return []
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip()]


ALLOWED_USERS = _parse_allowed_users()

# ── Access filter ─────────────────────────────────────────────────────────── #


def _user_filter() -> filters.BaseFilter:
    """Return a filter that only passes messages from allowed users."""
    if ALLOWED_USERS:
        return filters.User(user_id=ALLOWED_USERS)
    # No whitelist configured — allow everyone (useful for testing)
    return filters.ALL


# ── Style key map (for inline keyboard) ───────────────────────────────────── #

STYLE_KEYS = list(Config.ANIMATION_STYLES.keys())

# ── Helper: throttled progress editor ─────────────────────────────────────── #


class ProgressNotifier:
    """Edit a Telegram message at most once per `interval` seconds."""

    def __init__(self, chat_id: int, message_id: int, app: Application, interval: float = 3.0):
        self.chat_id = chat_id
        self.message_id = message_id
        self.app = app
        self.interval = interval
        self._last_edit: float = 0.0
        self._last_text: str = ""

    async def update(self, text: str):
        now = time.monotonic()
        if text == self._last_text:
            return
        if now - self._last_edit < self.interval:
            return
        try:
            await self.app.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=text,
            )
            self._last_edit = now
            self._last_text = text
        except Exception:
            pass  # Telegram may reject identical edits

    async def final(self, text: str):
        """Send a final edit regardless of throttle."""
        try:
            await self.app.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=text,
            )
            self._last_text = text
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  Command handlers
# ══════════════════════════════════════════════════════════════════════════════


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — welcome message."""
    await update.message.reply_text(
        "Welcome to StoryBook Generator!\n\n"
        "I create beautifully illustrated children's bedtime stories.\n\n"
        "Commands:\n"
        "/story  — Generate a new storybook\n"
        "/provider — Switch default image provider\n"
        "/help   — Show help\n"
        "/cancel — Cancel current operation"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help — command reference."""
    await update.message.reply_text(
        "StoryBook Generator — Help\n"
        "─────────────────────────\n"
        "/story   — Start a new storybook\n"
        "/provider — Switch default image provider (gpt-image / gemini)\n"
        "/cancel  — Cancel the current conversation\n"
        "/help    — Show this message\n\n"
        "The bot will guide you through:\n"
        "1. Choosing an image provider\n"
        "2. Picking an art style\n"
        "3. Auto or custom story mode\n"
        "4. Number of scenes\n"
        "5. Reviewing the story\n"
        "6. Generating illustrations + PDF"
    )


async def cmd_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /provider — toggle session default provider."""
    current = context.user_data.get("default_provider", Config.IMAGE_PROVIDER)
    new = "gemini" if current == "gpt-image" else "gpt-image"
    context.user_data["default_provider"] = new

    labels = {"gpt-image": "GPT-image-1-mini (Fast)", "gemini": "Gemini Flash (Premium)"}
    await update.message.reply_text(
        f"Default provider switched to: {labels.get(new, new)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ConversationHandler steps
# ══════════════════════════════════════════════════════════════════════════════


async def story_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /story — show provider selection."""
    default = context.user_data.get("default_provider", Config.IMAGE_PROVIDER)
    gpt_label = "GPT-image-1-mini (Fast)"
    gem_label = "Gemini Flash (Premium)"
    if default == "gpt-image":
        gpt_label += " *"
    else:
        gem_label += " *"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(gpt_label, callback_data="provider:gpt-image"),
            InlineKeyboardButton(gem_label, callback_data="provider:gemini"),
        ]
    ])
    await update.message.reply_text(
        "Choose an image provider for this story (* = default):",
        reply_markup=keyboard,
    )
    return CHOOSING_PROVIDER


async def choose_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle provider selection."""
    query = update.callback_query
    await query.answer()
    provider = query.data.split(":")[1]
    context.user_data["provider"] = provider

    labels = {"gpt-image": "GPT-image-1-mini", "gemini": "Gemini Flash"}
    await query.edit_message_text(f"Provider: {labels.get(provider, provider)}")

    # Show art style selection
    buttons = []
    for key in STYLE_KEYS:
        name = Config.ANIMATION_STYLES[key]["name"]
        buttons.append([InlineKeyboardButton(name, callback_data=f"style:{key}")])

    keyboard = InlineKeyboardMarkup(buttons)
    await query.message.reply_text("Choose an art style:", reply_markup=keyboard)
    return CHOOSING_STYLE


async def choose_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle art style selection."""
    query = update.callback_query
    await query.answer()
    style_key = query.data.split(":")[1]
    context.user_data["style"] = Config.ANIMATION_STYLES[style_key]

    await query.edit_message_text(f"Art style: {Config.ANIMATION_STYLES[style_key]['name']}")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Auto (Random)", callback_data="mode:auto"),
            InlineKeyboardButton("Custom (Your Idea)", callback_data="mode:custom"),
        ]
    ])
    await query.message.reply_text("Story mode:", reply_markup=keyboard)
    return CHOOSING_MODE


async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle story mode selection."""
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":")[1]
    context.user_data["mode"] = mode

    if mode == "custom":
        await query.edit_message_text("Mode: Custom")
        await query.message.reply_text("Describe your story idea:")
        return ENTERING_DESCRIPTION

    await query.edit_message_text("Mode: Auto (Random)")

    # Skip to scene count
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10", callback_data="scenes:10"),
            InlineKeyboardButton("12", callback_data="scenes:12"),
            InlineKeyboardButton("15", callback_data="scenes:15"),
        ]
    ])
    await query.message.reply_text("How many scenes?", reply_markup=keyboard)
    return CHOOSING_SCENES


async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom story description text."""
    context.user_data["description"] = update.message.text

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10", callback_data="scenes:10"),
            InlineKeyboardButton("12", callback_data="scenes:12"),
            InlineKeyboardButton("15", callback_data="scenes:15"),
        ]
    ])
    await update.message.reply_text("How many scenes?", reply_markup=keyboard)
    return CHOOSING_SCENES


async def choose_scenes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle scene count selection, then generate the story."""
    query = update.callback_query
    await query.answer()
    num_scenes = int(query.data.split(":")[1])
    context.user_data["num_scenes"] = num_scenes

    await query.edit_message_text(f"Scenes: {num_scenes}")

    # Send a "generating..." message
    msg = await query.message.reply_text(
        f"Generating a {num_scenes}-scene bedtime story..."
    )

    # Generate story in a thread to avoid blocking
    style = context.user_data["style"]
    description = context.user_data.get("description")

    registry = CharacterRegistry()
    registry.load()
    character_names_prompt = registry.get_prompt_text()

    generator = StoryGenerator()

    try:
        story = await asyncio.to_thread(
            generator.generate_story,
            num_scenes=num_scenes,
            description=description,
            art_style_hint=style.get("story_art_style"),
            character_names_prompt=character_names_prompt,
        )
    except Exception as e:
        await msg.edit_text(f"Story generation failed: {e}\n\nUse /story to try again.")
        return ConversationHandler.END

    context.user_data["story"] = story

    # Build preview (title + characters + moral, within 4096 char limit)
    preview = _format_story_preview(story)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Approve", callback_data="review:approve"),
            InlineKeyboardButton("Regenerate", callback_data="review:regenerate"),
            InlineKeyboardButton("Cancel", callback_data="review:cancel"),
        ]
    ])

    await msg.edit_text(preview)
    await query.message.reply_text("What would you like to do?", reply_markup=keyboard)
    return REVIEWING_STORY


def _format_story_preview(story: dict) -> str:
    """Format story for Telegram preview (stays under 4096 chars)."""
    lines = [f"Title: {story['title']}\n"]

    lines.append("Characters:")
    for c in story["characters"]:
        lines.append(f"  - {c['name']} ({c['type']}): {c['description'][:80]}")

    if story.get("moral"):
        lines.append(f"\nMoral: {story['moral']}")

    lines.append(f"\nScenes: {len(story['scenes'])}")
    lines.append(f"Setting: {story['setting'][:120]}")

    # Add first and last scene text as a teaser
    scenes = story["scenes"]
    if scenes:
        lines.append(f"\nScene 1: {scenes[0]['text'][:150]}")
        if len(scenes) > 1:
            lines.append(f"...\nScene {scenes[-1]['scene_number']}: {scenes[-1]['text'][:150]}")

    text = "\n".join(lines)
    # Hard cap at 4096
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    return text


async def review_story(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle story review (approve / regenerate / cancel)."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "cancel":
        await query.edit_message_text("Story cancelled.")
        return ConversationHandler.END

    if action == "regenerate":
        await query.edit_message_text("Regenerating...")

        num_scenes = context.user_data["num_scenes"]
        style = context.user_data["style"]
        description = context.user_data.get("description")

        registry = CharacterRegistry()
        registry.load()
        character_names_prompt = registry.get_prompt_text()

        generator = StoryGenerator()

        try:
            story = await asyncio.to_thread(
                generator.generate_story,
                num_scenes=num_scenes,
                description=description,
                art_style_hint=style.get("story_art_style"),
                character_names_prompt=character_names_prompt,
            )
        except Exception as e:
            await query.message.reply_text(
                f"Story generation failed: {e}\n\nUse /story to try again."
            )
            return ConversationHandler.END

        context.user_data["story"] = story
        preview = _format_story_preview(story)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Approve", callback_data="review:approve"),
                InlineKeyboardButton("Regenerate", callback_data="review:regenerate"),
                InlineKeyboardButton("Cancel", callback_data="review:cancel"),
            ]
        ])

        await query.message.reply_text(preview)
        await query.message.reply_text("What would you like to do?", reply_markup=keyboard)
        return REVIEWING_STORY

    # ── Approved — start image generation ──
    await query.edit_message_text("Story approved! Starting illustration generation...")

    story = context.user_data["story"]
    style = context.user_data["style"]
    provider = context.user_data.get("provider", Config.IMAGE_PROVIDER)

    # Create output folder
    base_output_dir = Config.OUTPUT_DIR
    os.makedirs(base_output_dir, exist_ok=True)
    serial_number = get_next_story_number(base_output_dir)
    folder_path = create_story_folder(base_output_dir, serial_number, story["title"])
    context.user_data["folder_path"] = folder_path

    # Save story JSON
    save_story_json(story, folder_path)

    # Update character registry
    registry = CharacterRegistry()
    registry.load()
    registry.update_from_story(story)

    # Send progress message
    progress_msg = await query.message.reply_text(
        f"Generating {len(story['scenes'])} illustrations with {provider}...\n"
        "Scene 0/0 — starting..."
    )

    # Run image pipeline in a thread with progress updates
    notifier = ProgressNotifier(
        chat_id=progress_msg.chat_id,
        message_id=progress_msg.message_id,
        app=context.application,
    )

    loop = asyncio.get_event_loop()

    def progress_callback(scene_num, total, status):
        status_labels = {
            "generating": f"Generating scene {scene_num}/{total}...",
            "done": f"Scene {scene_num}/{total} done",
            "reviewing": "Reviewing images with GPT-4o-mini...",
            "regenerating": f"Regenerating scene {scene_num}/{total} with Gemini...",
        }
        text = (
            f"Generating {total} illustrations with {provider}...\n"
            f"{status_labels.get(status, status)}"
        )
        asyncio.run_coroutine_threadsafe(notifier.update(text), loop)

    # Temporarily override the image provider for this generation
    original_provider = Config.IMAGE_PROVIDER
    Config.IMAGE_PROVIDER = provider

    try:
        image_gen = ImageGenerator(animation_style=style)
        raw_images = await asyncio.to_thread(
            image_gen.generate_all_images,
            story=story,
            output_dir=folder_path,
            progress_callback=progress_callback,
        )
    except Exception as e:
        Config.IMAGE_PROVIDER = original_provider
        await notifier.final(f"Image generation failed: {e}")
        await query.message.reply_text("Use /story to try again.")
        return ConversationHandler.END

    Config.IMAGE_PROVIDER = original_provider

    await notifier.final("Images generated! Adding text overlays...")

    # Text overlay
    overlay = TextOverlay()
    try:
        final_images = await asyncio.to_thread(
            overlay.process_all_scenes,
            story=story,
            raw_image_paths=raw_images,
            output_dir=folder_path,
        )
    except Exception as e:
        await query.message.reply_text(f"Text overlay failed: {e}")
        return ConversationHandler.END

    await notifier.final("Compiling PDF...")

    # PDF compilation
    compiler = StoryBookPDF()
    pdf_filename = f"{sanitize_folder_name(story['title'])}.pdf"
    pdf_path = os.path.join(folder_path, pdf_filename)

    try:
        pdf_path = await asyncio.to_thread(
            compiler.compile_with_cover,
            story=story,
            image_paths=final_images,
            output_path=pdf_path,
        )
    except Exception as e:
        await query.message.reply_text(f"PDF compilation failed: {e}")
        return ConversationHandler.END

    await notifier.final("Done! Sending your storybook...")

    # ── Deliver results ──

    # Send scene images as media groups (max 10 per group)
    # Each image gets its scene text as a caption
    scenes = story["scenes"]
    for i in range(0, len(final_images), 10):
        batch = final_images[i : i + 10]
        media_group = []
        for j, img_path in enumerate(batch):
            scene_idx = i + j
            scene = scenes[scene_idx] if scene_idx < len(scenes) else None
            if scene:
                caption = f"Scene {scene['scene_number']}: {scene['text']}"
                # Telegram caption limit is 1024 chars
                if len(caption) > 1024:
                    caption = caption[:1021] + "..."
            else:
                caption = None
            media_group.append(InputMediaPhoto(open(img_path, "rb"), caption=caption))

        try:
            await query.message.reply_media_group(media_group)
        except Exception as e:
            logger.warning(f"Failed to send media group: {e}")
        finally:
            # Close file handles
            for m in media_group:
                if hasattr(m.media, "close"):
                    m.media.close()

    # Send PDF
    try:
        with open(pdf_path, "rb") as pdf_file:
            await query.message.reply_document(
                document=pdf_file,
                filename=os.path.basename(pdf_path),
                caption=f"{story['title']} — {len(story['scenes'])} scenes",
            )
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")
        await query.message.reply_text(f"PDF saved at: {pdf_path}")

    # Offer to generate another
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Generate Another", callback_data="another:yes"),
            InlineKeyboardButton("Done", callback_data="another:no"),
        ]
    ])
    await query.message.reply_text(
        f"Storybook complete!\n"
        f"Title: {story['title']}\n"
        f"Folder: {folder_path}",
        reply_markup=keyboard,
    )
    return STORY_COMPLETE


async def story_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'generate another' or 'done'."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "yes":
        await query.edit_message_text("Starting a new story...")
        # Re-enter the conversation from provider selection
        default = context.user_data.get("default_provider", Config.IMAGE_PROVIDER)
        gpt_label = "GPT-image-1-mini (Fast)"
        gem_label = "Gemini Flash (Premium)"
        if default == "gpt-image":
            gpt_label += " *"
        else:
            gem_label += " *"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(gpt_label, callback_data="provider:gpt-image"),
                InlineKeyboardButton(gem_label, callback_data="provider:gemini"),
            ]
        ])
        await query.message.reply_text(
            "Choose an image provider for this story (* = default):",
            reply_markup=keyboard,
        )
        return CHOOSING_PROVIDER

    await query.edit_message_text("Thanks for using StoryBook Generator!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════


def main():
    """Start the Telegram bot."""
    if not Config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set in .env")
        return

    if not Config.OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY is not set in .env")
        return

    if not Config.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in .env")
        return

    user_filter = _user_filter()

    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Story generation conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("story", story_entry, filters=user_filter)],
        states={
            CHOOSING_PROVIDER: [
                CallbackQueryHandler(choose_provider, pattern=r"^provider:"),
            ],
            CHOOSING_STYLE: [
                CallbackQueryHandler(choose_style, pattern=r"^style:"),
            ],
            CHOOSING_MODE: [
                CallbackQueryHandler(choose_mode, pattern=r"^mode:"),
            ],
            ENTERING_DESCRIPTION: [
                MessageHandler(user_filter & filters.TEXT & ~filters.COMMAND, enter_description),
            ],
            CHOOSING_SCENES: [
                CallbackQueryHandler(choose_scenes, pattern=r"^scenes:"),
            ],
            REVIEWING_STORY: [
                CallbackQueryHandler(review_story, pattern=r"^review:"),
            ],
            STORY_COMPLETE: [
                CallbackQueryHandler(story_complete, pattern=r"^another:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", cmd_start, filters=user_filter))
    app.add_handler(CommandHandler("help", cmd_help, filters=user_filter))
    app.add_handler(CommandHandler("provider", cmd_provider, filters=user_filter))

    logger.info("StoryBook bot starting (polling)...")
    if ALLOWED_USERS:
        logger.info(f"Allowed users: {ALLOWED_USERS}")
    else:
        logger.info("No user whitelist — all users allowed")

    app.run_polling()


if __name__ == "__main__":
    main()
