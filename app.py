#!/usr/bin/env python3
"""
StoryBook Generator - Main Application
========================================
An AI-powered children's bedtime storybook generator.

Workflow:
  1. Generate a structured story using an LLM (default: GPT-4o-mini)
  2. Present story to user for approval (loop until approved)
  3. Generate illustrations using CogView-4, review with GPT-4o-mini, fallback to Gemini
  4. Overlay story text on each illustration
  5. Compile everything into a PDF storybook
  6. Save all assets into a numbered folder: <sno>_<title>/

Usage:
    python app.py
"""

import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from config import Config
from story_generator import StoryGenerator
from image_generator import ImageGenerator
from text_overlay import TextOverlay
from video_compiler import VideoCompiler
from pdf_compiler import StoryBookPDF
from character_registry import CharacterRegistry
from utils import sanitize_folder_name, get_next_story_number, create_story_folder, save_story_json

console = Console()


# --------------------------------------------------------------------------- #
#  Display helpers
# --------------------------------------------------------------------------- #

def display_welcome():
    """Show the welcome banner."""
    console.print()
    console.print(
        Panel.fit(
            "[bold magenta]📚 StoryBook Generator[/bold magenta]\n"
            "[dim]AI-Powered Children's Bedtime Stories[/dim]\n\n"
            "[cyan]• Stories featuring animals, birds & humans[/cyan]\n"
            "[cyan]• Beautiful AI-generated illustrations[/cyan]\n"
            "[cyan]• Happy endings with optional gentle morals[/cyan]\n"
            "[cyan]• Perfect for toddlers aged 2-3[/cyan]",
            border_style="bright_magenta",
            padding=(1, 4),
        )
    )
    console.print()


def display_story_preview(story: dict):
    """Display the generated story in a rich formatted preview."""
    # Title
    console.print()
    console.print(
        Panel(
            f"[bold yellow]{story['title']}[/bold yellow]",
            border_style="yellow",
            title="📖 Story Title",
            subtitle=f"{len(story['scenes'])} scenes",
        )
    )

    # Characters table
    char_table = Table(title="🎭 Characters", border_style="cyan", show_lines=True)
    char_table.add_column("Name", style="bold green", width=15)
    char_table.add_column("Type", style="magenta", width=10)
    char_table.add_column("Description", style="white")

    for char in story["characters"]:
        char_table.add_row(char["name"], char["type"], char["description"])

    console.print(char_table)
    console.print()

    # Setting & Art Style
    console.print(Panel(story["setting"], title="🌍 Setting", border_style="green"))
    console.print(Panel(story["art_style"], title="🎨 Art Style", border_style="blue"))
    console.print()

    # Scenes
    console.print("[bold underline]📜 Story Scenes:[/bold underline]\n")
    for scene in story["scenes"]:
        scene_panel = Panel(
            f"[white]{scene['text']}[/white]\n\n"
            f"[dim italic]🖼️  {scene['image_description'][:120]}...[/dim italic]",
            title=f"Scene {scene['scene_number']}",
            border_style="bright_black",
            padding=(0, 2),
        )
        console.print(scene_panel)

    # Moral (only if the story has one)
    if story.get("moral"):
        console.print()
        console.print(
            Panel(
                f"[bold yellow]✨ {story['moral']} ✨[/bold yellow]",
                title="💡 Moral of the Story",
                border_style="yellow",
            )
        )

    # Instagram caption
    if story.get("instagram_caption"):
        console.print()
        console.print(
            Panel(
                f"[italic]{story['instagram_caption']}[/italic]",
                title="📸 Instagram Caption",
                border_style="magenta",
            )
        )
        console.print()


# --------------------------------------------------------------------------- #
#  Main workflow
# --------------------------------------------------------------------------- #

def step_select_animation_style() -> dict:
    """Let the user pick an animation style for this session."""
    console.print("\n[bold cyan]━━━ Animation Style ━━━[/bold cyan]\n")

    styles = Config.ANIMATION_STYLES
    keys = list(styles.keys())

    style_table = Table(
        title="Choose an illustration style",
        border_style="bright_magenta",
        show_lines=True,
    )
    style_table.add_column("#", style="bold yellow", width=3)
    style_table.add_column("Style", style="bold green", width=24)
    style_table.add_column("Description", style="white")

    for idx, key in enumerate(keys, 1):
        s = styles[key]
        style_table.add_row(str(idx), s["name"], s["description"][:90] + "...")

    console.print(style_table)
    console.print()

    choice = Prompt.ask(
        f"[yellow]Select a style (1-{len(keys)})[/yellow]",
        default="1",
        choices=[str(i) for i in range(1, len(keys) + 1)],
    )
    selected_key = keys[int(choice) - 1]
    selected = styles[selected_key]
    console.print(f"\n[green]Selected: {selected['name']}[/green]\n")
    return selected


def _edit_scenes_cli(story: dict, generator: StoryGenerator) -> dict:
    """Let the user pick specific scenes to regenerate."""
    import re

    total = len(story["scenes"])
    console.print(f"\n[cyan]Which scenes to regenerate? (1-{total})[/cyan]")
    console.print("[dim]Enter scene numbers separated by commas, or ranges.[/dim]")
    console.print("[dim]Examples: 3  or  2,5,8  or  4-7  or  1,3,10-12[/dim]")

    raw = Prompt.ask("[yellow]Scene numbers[/yellow]")

    # Parse scene numbers
    scene_numbers = set()
    for part in re.split(r"[,\s]+", raw.strip()):
        part = part.strip()
        if not part:
            continue
        range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            for n in range(start, end + 1):
                if 1 <= n <= total:
                    scene_numbers.add(n)
        elif part.isdigit():
            n = int(part)
            if 1 <= n <= total:
                scene_numbers.add(n)

    if not scene_numbers:
        console.print("[red]No valid scene numbers entered. Returning to review.[/red]")
        return story

    scene_list = sorted(scene_numbers)

    # Show current text for selected scenes
    console.print()
    for n in scene_list:
        scene = story["scenes"][n - 1]
        console.print(
            Panel(
                f"[white]{scene['text']}[/white]",
                title=f"Scene {n} (current)",
                border_style="dim",
                padding=(0, 2),
            )
        )

    console.print()
    instructions = Prompt.ask(
        "[yellow]Describe what you want to change[/yellow]"
    )

    console.print(f"\n[cyan]Rewriting scene(s): {', '.join(str(n) for n in scene_list)}...[/cyan]")

    with console.status("[bold green]Rewriting scenes..."):
        try:
            story = generator.regenerate_scenes(story, scene_list, instructions=instructions)
        except Exception as e:
            console.print(f"\n[red]❌ Scene edit failed: {e}[/red]")
            return story

    console.print("[green]✅ Scenes updated![/green]")

    # Show updated scenes
    for n in scene_list:
        scene = story["scenes"][n - 1]
        console.print(
            Panel(
                f"[white]{scene['text']}[/white]\n\n"
                f"[dim italic]🖼️  {scene['image_description'][:120]}...[/dim italic]",
                title=f"Scene {scene['scene_number']} (updated)",
                border_style="green",
                padding=(0, 2),
            )
        )

    return story


def step_generate_story(
    generator: StoryGenerator,
    selected_style: dict,
    registry: CharacterRegistry,
) -> dict:
    """
    Step 1: Generate a story and get user approval.
    Supports auto (random) and custom (user-provided brief) modes.
    Loops until the user approves the story.
    """
    console.print("\n[bold cyan]━━━ STEP 1: Story Generation ━━━[/bold cyan]\n")

    # Story mode selection
    mode = Prompt.ask(
        "[yellow]Story mode[/yellow]",
        choices=["auto", "custom"],
        default="auto",
    )

    description = None
    if mode == "custom":
        description = Prompt.ask(
            "[yellow]Describe your story idea[/yellow]"
        )

    num_scenes = 12  # Default
    custom_scenes = Confirm.ask(
        "[yellow]Would you like to specify the number of scenes?[/yellow]",
        default=False,
    )
    if custom_scenes:
        num_scenes = int(
            Prompt.ask(
                "[yellow]How many scenes (10-15)?[/yellow]",
                default="12",
                choices=[str(i) for i in range(10, 16)],
            )
        )

    # Prepare optional prompt additions
    art_style_hint = selected_style.get("story_art_style")
    character_names_prompt = registry.get_prompt_text()

    while True:
        console.print(f"\n[cyan]🪄 Generating a {num_scenes}-scene bedtime story...[/cyan]")
        if description:
            console.print(f"[dim]Brief: {description}[/dim]")

        with console.status(f"[bold green]Crafting your story with {Config.STORY_MODEL}..."):
            try:
                story = generator.generate_story(
                    num_scenes=num_scenes,
                    description=description,
                    art_style_hint=art_style_hint,
                    character_names_prompt=character_names_prompt,
                )
            except Exception as e:
                console.print(f"\n[red]❌ Error generating story: {e}[/red]")
                retry = Confirm.ask("[yellow]Try again?[/yellow]", default=True)
                if retry:
                    continue
                else:
                    sys.exit(1)

        # Display the story preview
        display_story_preview(story)

        # Ask for approval
        console.print("[bold]What would you like to do?[/bold]")
        choice = Prompt.ask(
            "[yellow]Choose[/yellow]",
            choices=["approve", "regenerate", "edit", "quit"],
            default="approve",
        )

        if choice == "approve":
            console.print("\n[green]✅ Story approved! Moving to illustration generation...[/green]")
            return story
        elif choice == "quit":
            console.print("\n[dim]Goodbye! 👋[/dim]")
            sys.exit(0)
        elif choice == "edit":
            story = _edit_scenes_cli(story, generator)
            display_story_preview(story)
            continue
        else:
            console.print("\n[yellow]🔄 Generating a new story...[/yellow]")
            continue


def step_generate_images(image_gen: ImageGenerator, story: dict, folder_path: str) -> list[str]:
    """
    Step 2: Generate illustrations for all scenes.
    """
    console.print("\n[bold cyan]━━━ STEP 2: Image Generation ━━━[/bold cyan]\n")
    style_name = image_gen.animation_style["name"]
    provider_labels = {
        "minimax": "MiniMax image-01",
        "gemini": "Gemini Flash",
        "gpt-image": "GPT-image-1",
        "cogview": Config.IMAGE_MODEL,
    }
    provider_label = provider_labels.get(Config.IMAGE_PROVIDER, Config.IMAGE_PROVIDER)
    console.print(
        f"[cyan]Generating {len(story['scenes'])} {style_name} illustrations using {provider_label}...[/cyan]"
    )
    console.print("[dim]This may take several minutes due to API rate limits.[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[green]Generating illustrations...", total=len(story["scenes"])
        )

        def on_progress(scene_num, total, status):
            if status == "generating":
                progress.update(
                    task,
                    description=f"[green]🖼️  Generating scene {scene_num}/{total}...",
                )
            elif status == "done":
                progress.advance(task)
            elif status == "reviewing":
                progress.update(
                    task,
                    description=f"[yellow]🔍 Reviewing scenes with GPT-4o-mini...",
                )
            elif status == "regenerating":
                progress.update(
                    task,
                    description=f"[yellow]🔄 Regenerating scene {scene_num}/{total} with Gemini...",
                )

        image_paths = image_gen.generate_all_images(
            story=story,
            output_dir=folder_path,
            progress_callback=on_progress,
        )

    console.print(f"\n[green]✅ All {len(image_paths)} illustrations generated![/green]")
    return image_paths


def step_overlay_text(overlay: TextOverlay, story: dict, image_paths: list[str], folder_path: str) -> list[str]:
    """
    Step 3: Overlay story text on each illustration.
    """
    console.print("\n[bold cyan]━━━ STEP 3: Text Overlay ━━━[/bold cyan]\n")
    console.print("[cyan]Adding story text to illustrations...[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[green]Overlaying text...", total=len(story["scenes"])
        )

        def on_progress(scene_num, total, status):
            if status == "overlaying":
                progress.update(
                    task,
                    description=f"[green]✏️  Adding text to scene {scene_num}/{total}...",
                )
            elif status == "done":
                progress.advance(task)

        final_paths = overlay.process_all_scenes(
            story=story,
            raw_image_paths=image_paths,
            output_dir=folder_path,
            progress_callback=on_progress,
        )

    console.print(f"\n[green]✅ Text overlaid on all {len(final_paths)} images![/green]")
    return final_paths


def step_compile_video(
    video_compiler: VideoCompiler, story: dict, final_images: list[str], folder_path: str
) -> str:
    """
    Step 4: Compile images into a slideshow video with background music.
    """
    console.print("\n[bold cyan]--- STEP 4: Video Compilation ---[/bold cyan]\n")

    video_filename = f"{sanitize_folder_name(story['title'])}.mp4"
    video_path = os.path.join(folder_path, video_filename)

    with console.status("[bold green]Selecting background music..."):
        track_path = video_compiler.select_track(story)
    console.print(f"[dim]Track: {os.path.basename(track_path)}[/dim]")

    with console.status("[bold green]Compiling video slideshow..."):
        video_path = video_compiler.compile_video(
            story=story,
            image_paths=final_images,
            output_path=video_path,
            track_path=track_path,
        )

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    console.print(f"\n[green]Video compiled! ({size_mb:.1f} MB)[/green]")
    return video_path


def step_compile_pdf(compiler: StoryBookPDF, story: dict, final_images: list[str], folder_path: str) -> str:
    """
    Step 4: Compile everything into a PDF storybook.
    """
    console.print("\n[bold cyan]--- STEP 5: PDF Compilation ---[/bold cyan]\n")

    pdf_filename = f"{sanitize_folder_name(story['title'])}.pdf"
    pdf_path = os.path.join(folder_path, pdf_filename)

    with console.status("[bold green]📄 Compiling PDF storybook..."):
        pdf_path = compiler.compile_with_cover(
            story=story,
            image_paths=final_images,
            output_path=pdf_path,
        )

    console.print(f"\n[green]✅ PDF storybook created![/green]")
    return pdf_path


# --------------------------------------------------------------------------- #
#  Main entry point
# --------------------------------------------------------------------------- #

def main():
    """Main application entry point."""
    display_welcome()

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        console.print(f"\n[red]{e}[/red]")
        console.print("[yellow]Please edit the .env file and add your API keys.[/yellow]")
        sys.exit(1)

    # Select animation style (once per session)
    selected_style = step_select_animation_style()

    # Initialize modules
    generator = StoryGenerator()
    image_gen = ImageGenerator(animation_style=selected_style)
    overlay = TextOverlay()
    video_compiler = VideoCompiler()
    compiler = StoryBookPDF()

    # Load character registry
    registry = CharacterRegistry()
    registry.load()
    if registry.registry:
        console.print(
            f"[dim]Loaded {len(registry.registry)} character(s) from registry.[/dim]"
        )

    # Determine output directory and story serial number
    base_output_dir = Config.OUTPUT_DIR
    os.makedirs(base_output_dir, exist_ok=True)

    console.print(f"[dim]Output directory: {os.path.abspath(base_output_dir)}[/dim]")

    # ── Loop: allow generating multiple stories in one session ──
    while True:
        # Step 1: Generate & approve story
        story = step_generate_story(generator, selected_style, registry)

        # Determine folder
        serial_number = get_next_story_number(base_output_dir)
        folder_path = create_story_folder(base_output_dir, serial_number, story["title"])

        console.print(f"\n[dim]📁 Story folder: {folder_path}[/dim]")

        # Save story JSON
        save_story_json(story, folder_path)

        # Update character registry with new names
        registry.update_from_story(story)
        console.print("[dim]Character registry updated.[/dim]")

        # Step 2: Generate images
        raw_images = step_generate_images(image_gen, story, folder_path)

        # Step 3: Overlay text
        final_images = step_overlay_text(overlay, story, raw_images, folder_path)

        # Step 4: Compile video
        video_path = step_compile_video(video_compiler, story, final_images, folder_path)

        # Step 5: Compile PDF
        pdf_path = step_compile_pdf(compiler, story, final_images, folder_path)

        # ── Summary ──
        console.print()
        summary_table = Table(title="📚 Storybook Complete!", border_style="bright_magenta")
        summary_table.add_column("Item", style="bold cyan")
        summary_table.add_column("Details", style="white")

        summary_table.add_row("Title", story["title"])
        summary_table.add_row("Scenes", str(len(story["scenes"])))
        if story.get("moral"):
            summary_table.add_row("Moral", story["moral"])
        if story.get("instagram_caption"):
            summary_table.add_row("IG Caption", story["instagram_caption"])
        summary_table.add_row("Folder", folder_path)
        summary_table.add_row("Video", video_path)
        summary_table.add_row("PDF", pdf_path)
        summary_table.add_row("Images", f"{len(final_images)} JPEG files")

        console.print(summary_table)
        console.print()

        # List all files in the folder
        console.print("[bold]📂 Files created:[/bold]")
        for f in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, f)
            size_kb = os.path.getsize(fpath) / 1024
            icon = "📄" if f.endswith(".pdf") else "🖼️" if f.endswith((".jpg", ".png")) else "📋"
            console.print(f"   {icon} {f} ({size_kb:.1f} KB)")

        console.print()

        # Ask to create another story
        another = Confirm.ask(
            "[yellow]Would you like to create another storybook?[/yellow]",
            default=False,
        )
        if not another:
            console.print("\n[bold magenta]Thank you for using StoryBook Generator! 📚✨[/bold magenta]")
            console.print("[dim]Sweet dreams! 🌙[/dim]\n")
            break


if __name__ == "__main__":
    main()
