"""
Configuration module for StoryBook Generator.
Loads settings from .env file and provides defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration loaded from .env file."""

    # OpenAI API (used for story generation)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Google Gemini API (used for image generation)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # GLM / ZhipuAI API (legacy, kept for reference)
    GLM_API_KEY = os.getenv("GLM_API_KEY", "")
    GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")

    # MiniMax API (used for image generation)
    MINIMAX_API_TOKEN = os.getenv("MINIMAX_API_TOKEN", "")
    MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")

    # Model settings
    STORY_MODEL = os.getenv("STORY_MODEL", "gpt-4o-mini")
    IMAGE_MODEL = os.getenv("IMAGE_MODEL", "cogView-4-250304")
    IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1536")
    IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "gemini")  # "gemini", "gpt-image", "minimax", or "cogview"

    # Story settings
    MIN_SCENES = int(os.getenv("MIN_SCENES", "10"))
    MAX_SCENES = int(os.getenv("MAX_SCENES", "15"))

    # Output settings
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "stories")

    # Character registry
    CHARACTER_REGISTRY_PATH = os.getenv(
        "CHARACTER_REGISTRY_PATH", os.path.join(OUTPUT_DIR, "character_registry.json")
    )

    # Telegram bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "")

    # Animation styles
    DEFAULT_ANIMATION_STYLE = "pixar_3d"

    ANIMATION_STYLES = {
        "pixar_3d": {
            "name": "Pixar 3D",
            "description": (
                "Pixar 3D animation style children's picture book illustration. "
                "Render with smooth, vibrant Pixar-quality CGI: soft volumetric lighting, "
                "rich saturated colors, expressive cartoon eyes, rounded friendly shapes, "
                "and cinematic depth of field."
            ),
            "story_art_style": "Pixar-style 3D CGI with smooth shapes and expressive cartoon eyes",
            "image_rules": "Pixar 3D animation aesthetic throughout — NOT flat 2D",
        },
        "studio_ghibli": {
            "name": "Studio Ghibli",
            "description": (
                "Studio Ghibli style children's picture book illustration. "
                "Soft hand-painted watercolor look, gentle pastel color palette, "
                "dreamy atmospheric lighting, lush natural backgrounds with meticulous detail, "
                "warm and whimsical character designs."
            ),
            "story_art_style": "Studio Ghibli hand-painted watercolor with gentle pastels and dreamy atmosphere",
            "image_rules": "Studio Ghibli hand-painted watercolor aesthetic — soft edges, pastel tones, NOT CGI",
        },
        "classic_disney_2d": {
            "name": "Classic Disney 2D",
            "description": (
                "Classic Disney 2D animation style children's picture book illustration. "
                "Bold clean outlines, vibrant flat colors, theatrical character expressions, "
                "dynamic poses, painted storybook backgrounds with depth, "
                "reminiscent of golden-age Disney feature animation."
            ),
            "story_art_style": "Classic Disney 2D animation with bold outlines and vibrant flat colors",
            "image_rules": "Classic Disney 2D animation aesthetic — bold outlines, flat vibrant colors, theatrical expressions",
        },
        "claymation": {
            "name": "Claymation",
            "description": (
                "Claymation stop-motion style children's picture book illustration. "
                "Visible clay textures on characters and props, handmade miniature sets, "
                "warm stop-motion lighting with soft shadows, charming imperfections, "
                "tactile and cozy feel like Wallace & Gromit."
            ),
            "story_art_style": "Claymation stop-motion with clay textures and miniature handmade sets",
            "image_rules": "Claymation stop-motion aesthetic — visible clay textures, miniature sets, handmade feel",
        },
        "storybook_illustration": {
            "name": "Storybook Illustration",
            "description": (
                "Classic storybook illustration style. "
                "Colored pencil and gouache on textured paper, warm earthy tones, "
                "soft hand-drawn linework, vintage picture book feel with gentle cross-hatching, "
                "cozy and nostalgic atmosphere like Beatrix Potter or classic Winnie the Pooh."
            ),
            "story_art_style": "Vintage storybook illustration with colored pencil, gouache, and warm tones",
            "image_rules": "Classic storybook illustration aesthetic — colored pencil & gouache, warm tones, vintage feel",
        },
        "glowlight_fantasy": {
            "name": "Glowlight Fantasy",
            "description": (
                "Glowlight fantasy children's picture book illustration. "
                "Luminous bioluminescent glow on characters and environment, deep twilight "
                "and midnight blue backgrounds, soft neon accents in teal, magenta, and gold, "
                "fireflies and glowing particles floating in the air, enchanted forest atmosphere "
                "with radiant mushrooms, glowing flowers, and shimmering water reflections."
            ),
            "story_art_style": "Glowlight fantasy with bioluminescent glow, twilight hues, and floating light particles",
            "image_rules": "Glowlight fantasy aesthetic — luminous glow effects, deep twilight palette, bioluminescent details, magical atmosphere",
        },
        "mystical_enchanted": {
            "name": "Mystical Enchanted",
            "description": (
                "Mystical enchanted realm children's picture book illustration. "
                "Ethereal misty landscapes, ancient stone ruins overgrown with vines, "
                "swirling aurora-like sky in purples, teals, and silvers, crystalline elements, "
                "magical runes subtly woven into the environment, soft diffused light "
                "filtering through ancient trees, mysterious yet warm and inviting."
            ),
            "story_art_style": "Mystical enchanted realm with ethereal mist, aurora skies, and crystalline magic",
            "image_rules": "Mystical enchanted aesthetic — ethereal mist, aurora palette of purples and teals, crystalline elements, ancient and magical",
        },
        "paper_cutout": {
            "name": "Paper Cutout",
            "description": (
                "Paper cutout collage children's picture book illustration. "
                "Layered paper textures with visible edges and subtle shadows between layers, "
                "bold flat colors with handmade imperfections, torn and cut paper shapes, "
                "decorative patterns and textures on each paper layer, slight 3D depth "
                "from stacked cutouts, playful and tactile like Eric Carle or Lois Ehlert."
            ),
            "story_art_style": "Paper cutout collage with layered textures, bold flat colors, and handmade feel",
            "image_rules": "Paper cutout collage aesthetic — layered paper textures, visible edges, bold flat colors, handmade imperfections",
        },
        "retro_cartoon": {
            "name": "Retro Cartoon",
            "description": (
                "1950s-1960s retro cartoon children's picture book illustration. "
                "Mid-century modern design sensibility, limited color palette with mustard yellow, "
                "burnt orange, olive green, and teal, bold geometric shapes, thick ink outlines, "
                "screen-print texture and halftone dots, playful atomic-age patterns, "
                "reminiscent of vintage Hanna-Barbera and UPA animation."
            ),
            "story_art_style": "Retro 1950s cartoon with mid-century colors, bold geometry, and screen-print textures",
            "image_rules": "Retro 1950s-60s cartoon aesthetic — mid-century palette, thick ink outlines, halftone textures, geometric shapes",
        },
        "soft_pastel_dream": {
            "name": "Soft Pastel Dream",
            "description": (
                "Soft pastel dream children's picture book illustration. "
                "Ultra-soft blended pastels in lavender, baby pink, mint green, and butter yellow, "
                "hazy dreamy atmosphere with gentle bokeh light spots, cotton-candy clouds, "
                "rounded bubbly character shapes, no hard edges anywhere, "
                "everything looks plush and huggable like a nursery mobile come to life."
            ),
            "story_art_style": "Soft pastel dream with ultra-gentle blended pastels, hazy bokeh, and plush rounded shapes",
            "image_rules": "Soft pastel dream aesthetic — blended pastels, no hard edges, hazy bokeh, plush bubbly shapes",
        },
    }

    # Image text overlay settings
    FONT_SIZE_TITLE = 48
    FONT_SIZE_BODY = 32
    FONT_SIZE_MORAL = 28
    TEXT_PADDING = 40

    # Text band settings (cream band below the image)
    TEXT_BAND_COLOR = (255, 249, 235)        # Warm cream background
    TEXT_BAND_MIN_HEIGHT = 250               # Minimum band height in pixels
    TEXT_COLOR_TITLE = (101, 67, 33)         # Dark brown for title
    TEXT_COLOR_BODY = (80, 55, 30)           # Dark brown for body text
    TEXT_COLOR_MORAL = (139, 90, 43)         # Warm brown for moral

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "❌ OPENAI_API_KEY is not set! Please add your OpenAI API key to the .env file."
            )
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "❌ GEMINI_API_KEY is not set! Please add your Google Gemini API key to the .env file."
            )
        if cls.IMAGE_PROVIDER == "cogview" and not cls.GLM_API_KEY:
            raise ValueError(
                "❌ GLM_API_KEY is not set! Please add your GLM/ZhipuAI API key to the .env file."
            )
        if cls.IMAGE_PROVIDER == "minimax" and not cls.MINIMAX_API_TOKEN:
            raise ValueError(
                "❌ MINIMAX_API_TOKEN is not set! Please add your MiniMax API token to the .env file."
            )
        if cls.IMAGE_PROVIDER == "gpt-image" and not cls.OPENAI_API_KEY:
            raise ValueError(
                "❌ OPENAI_API_KEY is not set! Please add your OpenAI API key to the .env file."
            )
        if cls.IMAGE_PROVIDER == "gemini" and not cls.GEMINI_API_KEY:
            raise ValueError(
                "❌ GEMINI_API_KEY is not set! Please add your Gemini API key to the .env file."
            )
        return True
