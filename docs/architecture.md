# System Architecture

**StoryBook Generator** orchestrates multiple AI models to generate high-quality children's picture books with character consistency.

## File Structure

```
StoryBook/
├── bot.py                # Telegram bot interface (ConversationHandler)
├── app.py                # CLI interface & orchestrator
├── config.py             # Configuration loader (.env, style presets)
├── utils.py              # Shared utilities (folder creation, JSON saving)
├── story_generator.py    # GPT-4o-mini story generation (JSON output)
├── image_generator.py    # 4-provider dispatcher + vision review + fallback
├── text_overlay.py       # Speech bubble overlay on illustrations
├── pdf_compiler.py       # FPDF2 PDF assembly
├── character_registry.py # Persistent character name-to-species mapping
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container build (python:3.12-slim)
├── docker-compose.yml    # Single-service deployment
├── .env.example          # Environment variable template
└── docs/
    └── architecture.md   # This file
```

## The Multimodal Generation Pipeline

### Phase 1: Story Generation (`story_generator.py`)

Driven by **GPT-4o-mini** via the OpenAI API.

- **Input**: Scene count, optional custom description, art style hint, character name registry
- **Process**: A system prompt instructs GPT-4o-mini to output pure JSON. Random themes and species are injected each run for variety.
- **Validation**: JSON is parsed and structurally validated for required fields.
- **Output**: Structured story with title, characters (with detailed visual descriptions), setting, art style, moral, and 10-15 scenes (text + image descriptions).

### Phase 2: Illustration Pipeline (`image_generator.py`)

A dispatcher routes to one of 4 image providers, followed by a review and fallback tier:

**Phase 2a — Primary Generation** (one of):
- **gpt-image-1-mini** (default): OpenAI's image model. Scene 1 is analyzed by GPT-4o-mini vision to extract a character visual sheet used in subsequent scene prompts.
- **Gemini 2.5 Flash** (`gemini-2.5-flash-image`): Google's multimodal model. Accepts prior scene PIL images as visual context for character consistency.
- **MiniMax image-01**: Uses `subject_reference` with scene 1's base64 image. 1500-char prompt limit. Best for single-character stories.
- **CogView-4**: Legacy ZhipuAI/GLM provider. Text-only prompts.

**Phase 2b — Vision Review**: **GPT-4o-mini** reviews each generated image against character descriptions, outputting a confidence score (0.0-1.0).

**Phase 2c — Fallback**: Images scoring below 0.7 confidence are regenerated with **Gemini 2.5 Flash** (`gemini-2.5-flash-image`), using up to 2 prior scene images as visual context.

### Phase 3: Text Overlay (`text_overlay.py`)

Powered by **Pillow**.

- Draws semi-transparent speech bubbles directly on the illustration via RGBA compositing.
- Output dimensions match the input image — no canvas extension.
- Scene 1 gets a title banner at the top; the last scene includes the moral in the speech bubble.
- Font fallback chain covers macOS, Linux (DejaVu), and Windows.

### Phase 4: PDF Compilation (`pdf_compiler.py`)

Powered by **fpdf2**.

- Each text-overlaid image becomes a full page.
- Page dimensions are uniform, derived from the maximum image dimensions.
- Orientation is auto-detected from aspect ratio.

## Interfaces

### Telegram Bot (`bot.py`)

- Built on `python-telegram-bot>=21.0` (async).
- 8-state `ConversationHandler`: provider -> style -> mode -> description -> scenes -> review -> generation -> complete.
- Sync API calls (story generation, image pipeline) are offloaded via `asyncio.to_thread()`.
- Progress updates are throttled to one message edit per 3 seconds to avoid Telegram rate limits.
- Images are delivered as media groups (batches of 10), followed by the PDF as a document.
- Access is restricted via `ALLOWED_USER_IDS` whitelist.

### CLI (`app.py`)

- Rich-based terminal UI with progress bars, panels, and tables.
- Interactive prompts for style selection, story mode, and approval.
- Loops for multiple stories per session.

## Docker Deployment

- Base image: `python:3.12-slim` (Pillow wheel compatibility).
- System package: `fonts-dejavu-core` for text overlay font.
- Single service, polling mode (no exposed ports).
- Volume mount: `./stories:/app/stories` for persistent output on host.
- Restart policy: `unless-stopped`.

## Character Registry (`character_registry.py`)

- Persists character type-to-name mappings in `stories/character_registry.json`.
- When a story introduces a "bear" named "Benny", future stories reuse that name.
- Generic types ("animal") are resolved to specific species by scanning the character description.
- Registry prompt is optional — the LLM is encouraged to create new species too.
