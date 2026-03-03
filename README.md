# 📚 StoryBook Generator

An AI-powered children's bedtime storybook generator that creates beautifully illustrated, cohesive stories for toddlers (aged 2-3).

## ✨ Features

- **AI Story Generation** — Uses **GPT-4o-mini** to craft structured 10-15 scene stories featuring varied animal species, optional morals, and fresh themes.
- **Advanced 3-Tier Image Pipeline**:
  - **Generation**: Powered by **CogView-4 (GLM/ZhipuAI)** for high-quality, stylistically consistent original illustrations.
  - **AI Review**: Uses **GPT-4o-mini Vision** to automatically check each generated image against the character descriptions, scoring them for consistency.
  - **Fallback/Regeneration**: For any images scoring below a 70% confidence threshold, a fallback regeneration is triggered via **Gemini 2.0 Flash**, utilizing prior scene context to ensure character continuity.
- **Multiple Art Styles** — Support for various aesthetics, including Pixar 3D, Studio Ghibli, Classic Disney 2D, Claymation, and Vintage Storybook Illustration.
- **Text Overlay** — Story text is perfectly typeset on a warm cream band *below* the illustration for optimal readability.
- **PDF Delivery** — All scenes compiled directly into a single, printable PDF storybook.
- **Organized Output** — Each story is saved securely in a numbered folder alongside its raw JSON data and individual JPEG pairs.

## 🗂️ Output Structure

```
stories/
├── 001_The_Curious_Hedgehog/
│   ├── story_data.json          # Full generated story structure
│   ├── scene_01_raw.png         # Raw CogView-4/Gemini image 
│   ├── scene_01.jpg             # Final image with the cream text band 
│   ├── ...
│   └── The_Curious_Hedgehog.pdf # Compiled storybook
```

## 🚀 Quick Start

### 1. Install Dependencies

Requires Python 3.10+ and a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Create a `.env` file in the root directory and add your API keys:

```env
# Required for Story Logic & Image Review
OPENAI_API_KEY=your_openai_key

# Required for Primary Image Generation (CogView-4)
GLM_API_KEY=your_zhipuai_key

# Required for Fallback Image Generation
GEMINI_API_KEY=your_gemini_key
```

### 3. Run

```bash
python app.py
```

## ⚙️ Configuration Reference

Available settings in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GLM_API_KEY` | — | ZhipuAI API key (CogView-4) |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `STORY_MODEL` | `gpt-4o-mini` | LLM used for story script generation |
| `IMAGE_MODEL` | `cogView-4-250304` | Primary Image generation model |
| `MIN_SCENES` | `10` | Min scenes per story |
| `MAX_SCENES` | `15` | Max scenes per story |

## 🎨 Art Styles Available
The application allows you to select from predefined animation styles:
- **Pixar 3D** (`pixar_3d`)
- **Studio Ghibli** (`studio_ghibli`)
- **Classic Disney 2D** (`classic_disney_2d`)
- **Claymation** (`claymation`)
- **Storybook Illustration** (`storybook_illustration`)
