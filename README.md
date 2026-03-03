# StoryBook Generator

An AI-powered children's bedtime storybook generator that creates beautifully illustrated, cohesive stories for toddlers (aged 2-3). Available as a Telegram bot (primary) or CLI.

## Features

- **AI Story Generation** — GPT-4o-mini crafts structured 10-15 scene stories with varied animal species, optional morals, and fresh themes.
- **4 Image Providers**:
  - **gpt-image-1-mini** (default) — Fast, affordable ($0.015/image), strong prompt adherence
  - **Gemini 2.5 Flash** — Premium quality ($0.045/image), best character consistency via visual context
  - **MiniMax image-01** — Subject-reference based consistency (single-character only)
  - **CogView-4** — Legacy ZhipuAI/GLM provider
- **3-Tier Image Pipeline**: Generate all scenes -> GPT-4o-mini vision review -> Gemini fallback for low-confidence images
- **5 Art Styles** — Pixar 3D, Studio Ghibli, Classic Disney 2D, Claymation, Storybook Illustration
- **Text Overlay** — Semi-transparent speech bubbles drawn directly on the illustration (no canvas extension)
- **PDF Delivery** — All scenes compiled into a single printable PDF storybook
- **Telegram Bot** — Full conversational interface with inline keyboards, progress updates, and media delivery
- **Docker Deployment** — Single-command deployment for VPS hosting

## Quick Start

### Option A: Telegram Bot (Recommended)

#### 1. Configure

```bash
cp .env.example .env
# Edit .env — add API keys + TELEGRAM_BOT_TOKEN + ALLOWED_USER_IDS
```

#### 2. Run with Docker

```bash
docker-compose up -d
```

Or run directly:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

#### 3. Chat with the bot

Send `/story` to your bot in Telegram to begin.

### Option B: CLI

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + command list |
| `/story` | Begin a new storybook generation |
| `/provider` | Toggle default image provider (gpt-image / gemini) |
| `/help` | Command reference |
| `/cancel` | Cancel current conversation |

The `/story` flow guides you through: provider selection, art style, story mode (auto/custom), scene count, story preview and approval, then image generation with progress updates.

## Output Structure

```
stories/
├── 001_The_Curious_Hedgehog/
│   ├── story_data.json          # Full generated story structure
│   ├── scene_01_raw.png         # Raw AI-generated image
│   ├── scene_01.jpg             # Final image with speech bubble overlay
│   ├── ...
│   └── The_Curious_Hedgehog.pdf # Compiled storybook
```

## Configuration Reference

All settings are configured via environment variables in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** OpenAI API key (story generation, image review, gpt-image provider) |
| `GEMINI_API_KEY` | — | **Required.** Google Gemini API key (fallback generation, gemini provider) |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token (required for bot.py) |
| `ALLOWED_USER_IDS` | — | Comma-separated Telegram user IDs allowed to use the bot |
| `IMAGE_PROVIDER` | `gpt-image` | Image provider: `gpt-image`, `gemini`, `minimax`, `cogview` |
| `MINIMAX_API_TOKEN` | — | MiniMax API token (required if IMAGE_PROVIDER=minimax) |
| `GLM_API_KEY` | — | ZhipuAI API key (required if IMAGE_PROVIDER=cogview) |
| `STORY_MODEL` | `gpt-4o-mini` | LLM for story generation |
| `IMAGE_MODEL` | `cogView-4-250304` | Model name for CogView provider |
| `IMAGE_SIZE` | `1024x1536` | Image dimensions |
| `MIN_SCENES` | `10` | Minimum scenes per story |
| `MAX_SCENES` | `15` | Maximum scenes per story |
| `OUTPUT_DIR` | `stories` | Output directory for generated storybooks |

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f storybook-bot

# Rebuild after code changes
docker-compose up -d --build

# Stop
docker-compose down
```

Stories are persisted to `./stories/` on the host via a Docker volume mount.

## Art Styles

- **Pixar 3D** — Smooth, vibrant CGI with expressive cartoon eyes
- **Studio Ghibli** — Hand-painted watercolor with gentle pastels
- **Classic Disney 2D** — Bold outlines, vibrant flat colors, theatrical expressions
- **Claymation** — Clay textures, miniature sets, handmade feel
- **Storybook Illustration** — Colored pencil and gouache, warm vintage tones
