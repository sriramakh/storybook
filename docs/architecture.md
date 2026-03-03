# 📐 System Architecture

**StoryBook Generator** orchestrates multiple state-of-the-art Large Language and Vision Models to generate high-quality children's picture books with remarkable character consistency.

## 🗂 File Structure Overview

```
StoryBook/
├── app.py              # CLI Controller & Orchestrator
├── config.py           # Configuration loader (API keys, constraints, style presets)
├── story_generator.py  # GPT-4o-mini story generation (JSON output)
├── image_generator.py  # Primary generator + LLM vision review + Fallback mechanism
├── text_overlay.py     # Pillow-based typography overlay and whitespace generation
├── pdf_compiler.py     # FPDF2 assembly system
├── requirements.txt    # Library dependencies
├── README.md           # Application documentation
└── docs/               # System architecture documentation (this file)
```

## ⚙️ The Multimodal Generation Pipeline

### 1. Story Concept Generation (`story_generator.py`)
Driven by an instance of **OpenAI's `gpt-4o-mini`**.

* **Input**: User-provided inputs (number of scenes, optional character names, optional art style hints)
* **Process**: A deeply seeded system prompt coerces GPT-4o-mini to output pure JSON. The script dynamically injects random themes and creature choices (from pools in code) to ensure a diverse, less clichéd array of generated stories. 
* **Validation**: The JSON is validated and structurally parsed for missing keys.
* **Output**: A 10-15 element array of scenes (text descriptions + image prompts), explicit character definitions, and style markers.

### 2. Illustration Pipeline (`image_generator.py`)
This represents the most complex technical hurdle: **Character visual consistency**. To solve it, a 3-Tier Image Pipeline is used:

1. **Phase 1 (Primary Generation)**: **CogView-4 via ZhipuAI / GLM.**
   * For each scene, the image prompt is infused with exactly specified character profiles, rules about the aesthetic (e.g., Pixar 3D, Classic Disney), and setting constraints. All N scenes are generated serially.

2. **Phase 2 (Vision Review)**: **GPT-4o-mini Vision via OpenAI.**
   * Once images exist dynamically on disk, GPT-4o-mini Vision receives each low-res image + the expected character description + the text intent of the scene.
   * `gpt-4o-mini` outputs a JSON indicating its "Confidence" (0.0 to 1.0) that the image features the right characters and no hallucinations.

3. **Phase 3 (Fallback Generation)**: **Gemini 2.0 Flash Preview via Google.**
   * Any image that scores below 0.70 confidence triggers a fallback.
   * Gemini 2.0 Flash receives the prompt *and* the visual context of the 2 preceding scenes to try to guarantee alignment with previous illustrations.

### 3. Typesetting & Formatting (`text_overlay.py`)
Powered by **Pillow (Python Imaging Library)**.
* Instead of printing over the artwork directly, a high-contrast text band is constructed below the image.
* The original image dimensions are respected, but the canvas height is expanded dynamically downwards to house the block of text.
* Calculates word-wrapping to ensure the font size looks appealing across the bottom text strip.

### 4. PDFA Compilation (`pdf_compiler.py`)
Powered by **fpdf2**.
* Automates generating a landscape (or dynamically sized based on image ratio) PDF containing one illustration + text ribbon per page.
* Assigns title metadata safely out to the designated output folder.
