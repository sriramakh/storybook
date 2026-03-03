"""
Image Generator Module for StoryBook Generator.

Pipeline:
  1. Generate ALL images with the configured provider (MiniMax image-01 or CogView-4)
  2. Review ALL images with GPT-4o-mini vision — confidence score per image
  3. For images scoring < 0.7, regenerate with Gemini using prior scene context
"""

import os
import io
import json
import time
import base64
import requests

from openai import OpenAI
from google import genai
from google.genai import types
from PIL import Image
from config import Config


class ImageGenerator:
    """Generates storybook illustrations using a primary generator + GPT-4o-mini review + Gemini fallback pipeline."""

    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, animation_style: dict | None = None):
        self.image_provider = Config.IMAGE_PROVIDER  # "minimax" or "cogview"
        self.size = Config.IMAGE_SIZE

        # Primary image generator — conditional on provider
        if self.image_provider == "cogview":
            self.glm_client = OpenAI(
                api_key=Config.GLM_API_KEY,
                base_url=Config.GLM_BASE_URL,
            )
            self.model = Config.IMAGE_MODEL
        else:
            self.minimax_token = Config.MINIMAX_API_TOKEN
            self.minimax_base_url = Config.MINIMAX_BASE_URL

        # Reviewer: GPT-4o-mini vision via OpenAI
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

        # Fallback generator: Gemini
        self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)

        self.animation_style = animation_style or Config.ANIMATION_STYLES[Config.DEFAULT_ANIMATION_STYLE]

        # MiniMax subject_reference: holds scene 1's base64 image for consistency
        self._reference_image_b64: str | None = None
        # Character visual sheet extracted from scene 1's rendered image by GPT-4o-mini
        self._character_visual_sheet: str | None = None
        # Prior scene PIL images for Gemini visual context
        self._prior_scene_images: list = []

    # ------------------------------------------------------------------ #
    #  CDN download helper (CogView returns a URL, not raw bytes)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _download_with_retry(url: str, output_path: str, retries: int = 3) -> str:
        """Download an image from a CDN URL with retry logic."""
        for attempt in range(retries):
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return output_path
            except Exception as e:
                if attempt < retries - 1:
                    wait = (attempt + 1) * 3
                    print(f"   Download attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"Failed to download image after {retries} attempts: {e}")

    # ------------------------------------------------------------------ #
    #  Prompt builder (shared by both GLM and Gemini)
    # ------------------------------------------------------------------ #

    def _build_image_prompt(self, story: dict, scene: dict, scene_index: int) -> str:
        """Build a focused prompt for image generation."""
        scene_desc = scene["image_description"].lower()
        relevant_chars = [
            c for c in story["characters"]
            if c["name"].lower() in scene_desc
        ]
        if not relevant_chars:
            relevant_chars = story["characters"]

        character_block = "\n".join(
            f"- {c['name']}: {c['description']}"
            for c in relevant_chars
        )

        scenes = story["scenes"]
        scene_type = ""
        if scene_index == 0:
            scene_type = "This is the OPENING scene. Make it inviting and introduce the characters clearly."
        elif scene_index == len(scenes) - 1:
            scene_type = "This is the FINAL scene. Show a warm, happy conclusion."

        style = self.animation_style

        prompt = f"""{style['description']}

SETTING: {story['setting']}

CHARACTERS (draw EXACTLY as described, {style['name']} rendering):
{character_block}

SCENE {scene['scene_number']} of {len(scenes)}:
{scene['image_description']}

{scene_type}

RULES:
- {style['image_rules']}
- Keep IDENTICAL character designs (same colors, proportions, features, clothing)
- Warm, friendly expressions appropriate for a children's book
- Suitable for a 2-3 year old child
- DO NOT include any text, words, letters, or numbers in the image"""

        return prompt

    # ------------------------------------------------------------------ #
    #  MiniMax helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        """Read an image file and return a data-URI base64 string."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def _analyze_reference_image(self, image_path: str, characters: list[dict]) -> str:
        """
        Analyze scene 1's rendered image with GPT-4o-mini vision to extract
        a hyper-detailed character visual sheet. This sheet is then embedded
        in every subsequent MiniMax prompt so the text reinforces the
        subject_reference image exactly.
        """
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        char_names = ", ".join(c["name"] for c in characters)
        char_hints = " | ".join(
            f"{c['name']}={c['type']}: {c['description'][:80]}"
            for c in characters
        )

        analysis_prompt = f"""You are a visual consistency expert for a children's picture book.

The characters in this story are: {char_names}
Hints: {char_hints}

Analyze this illustration and for EACH character write ONE dense line:
{'{'}Name{'}'}: {'{'}species/type{'}'}, {'{'}exact body/fur/skin/feather color{'}'}, {'{'}eye color{'}'}, {'{'}exact clothing colors & patterns{'}'}, {'{'}accessories{'}'}, {'{'}size/build relative to others{'}'}

Then write ONE line describing the art style (lighting, color palette, rendering).

Be OBSESSIVELY precise about colors — e.g. "cerulean blue sweater with 3 golden star patches" NOT "blue sweater". Mention EVERY visible detail: spots, stripes, buttons, buckles, bows, whiskers, tail shape, ear shape, hat style.

Total response MUST be under 500 characters. No headers, no bullet points, no extra words."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=350,
            )
            sheet = response.choices[0].message.content.strip()
            # Safety: hard-cap at 500 chars
            if len(sheet) > 500:
                cut = sheet[:500].rfind(".")
                sheet = sheet[: cut + 1] if cut > 300 else sheet[:500]
            return sheet
        except Exception as e:
            print(f"   Reference image analysis failed ({e}), using story descriptions")
            # Fallback: build a condensed sheet from the story character data
            return "\n".join(
                f"{c['name']}: {c['description'][:120]}"
                for c in characters
            )[:500]

    def _build_minimax_prompt(self, story: dict, scene: dict, scene_index: int) -> str:
        """
        Build a detail-packed prompt for MiniMax (hard limit: 1500 chars).

        Scene 1: Maximize character descriptions to establish the strongest visual baseline.
        Scenes 2+: Lead with the character visual sheet extracted from scene 1's actual
                    rendered image, then scene-specific action. The text reinforces
                    what the subject_reference image shows.
        """
        style = self.animation_style
        scenes = story["scenes"]
        all_chars = story["characters"]

        if scene_index == 0:
            # ── Scene 1: establish the visual baseline ──
            # Include ALL characters with full descriptions
            character_block = "\n".join(
                f"- {c['name']} ({c['type']}): {c['description']}"
                for c in all_chars
            )

            prompt = f"""{style['description']}

SETTING: {story['setting']}

CHARACTERS — draw EXACTLY as described, every detail matters:
{character_block}

SCENE 1/{len(scenes)}: {scene['image_description']}

CRITICAL: Each character MUST match their description PRECISELY — correct species, exact colors, exact clothing, exact proportions. {style['image_rules']}. No text/letters in image. Children's book for ages 2-3."""

        else:
            # ── Scenes 2+: consistency-focused, anchored to scene 1 ──
            visual_sheet = self._character_visual_sheet or "\n".join(
                f"{c['name']}: {c['description'][:100]}" for c in all_chars
            )

            scene_type = ""
            if scene_index == len(scenes) - 1:
                scene_type = " This is the FINAL scene — show a warm, happy conclusion."

            prompt = f"""CONTINUITY: Draw the EXACT SAME characters as the reference image. Same species, same colors, same clothing, same proportions, same art style. Do NOT change any character's appearance.

CHARACTER SHEET (match EXACTLY):
{visual_sheet}

SCENE {scene['scene_number']}/{len(scenes)}: {scene['image_description']}{scene_type}

{style['image_rules']}. No text in image. Children's book for ages 2-3."""

        # Hard-truncate at sentence boundary (1500 char API limit)
        if len(prompt) > 1500:
            truncated = prompt[:1500]
            last_period = truncated.rfind(".")
            if last_period > 1000:
                prompt = truncated[: last_period + 1]
            else:
                prompt = truncated

        return prompt

    # ------------------------------------------------------------------ #
    #  Phase 1a: Generate a single scene image with MiniMax image-01
    # ------------------------------------------------------------------ #

    def _generate_with_minimax(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        retry_count: int = 3,
    ) -> str:
        """Generate an illustration for a single scene using MiniMax image-01."""
        prompt = self._build_minimax_prompt(story, scene, scene_index)

        # Map IMAGE_SIZE to MiniMax aspect ratio
        aspect_map = {
            "1024x1024": "1:1",
            "1024x1536": "2:3",
            "1536x1024": "3:2",
            "768x1024": "3:4",
            "1024x768": "4:3",
        }
        aspect_ratio = aspect_map.get(self.size, "2:3")

        url = f"{self.minimax_base_url}/image_generation"
        headers = {
            "Authorization": f"Bearer {self.minimax_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "image-01",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
        }

        # For scenes after the first, pass scene 1's image as subject_reference
        if scene_index > 0 and self._reference_image_b64:
            payload["subject_reference"] = [
                {"type": "character", "image_file": self._reference_image_b64}
            ]

        for attempt in range(retry_count):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()

                status_code = data.get("base_resp", {}).get("status_code", -1)
                if status_code != 0:
                    status_msg = data.get("base_resp", {}).get("status_msg", "unknown error")
                    raise RuntimeError(f"MiniMax API error {status_code}: {status_msg}")

                image_url = data["data"]["image_urls"][0]
                self._download_with_retry(image_url, output_path)

                # After scene 1 succeeds: store reference image + analyze it
                if scene_index == 0:
                    self._reference_image_b64 = self._image_to_base64(output_path)
                    print("   Analyzing scene 1 for character visual consistency...")
                    self._character_visual_sheet = self._analyze_reference_image(
                        output_path, story["characters"]
                    )
                    if self._character_visual_sheet:
                        print(f"   Character sheet extracted ({len(self._character_visual_sheet)} chars)")

                return output_path

            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"   MiniMax attempt {attempt+1} failed: {e}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to generate image for scene {scene['scene_number']} "
                        f"after {retry_count} attempts: {e}"
                    )

    # ------------------------------------------------------------------ #
    #  Phase 1b: Generate a single scene image with CogView-4 (GLM)
    # ------------------------------------------------------------------ #

    def _generate_with_cogview(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        retry_count: int = 3,
    ) -> str:
        """Generate an illustration for a single scene using CogView-4."""
        prompt = self._build_image_prompt(story, scene, scene_index)

        if len(prompt) > 16000:
            prompt = prompt[:16000] + "..."

        for attempt in range(retry_count):
            try:
                response = self.glm_client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=self.size,
                )

                image_url = response.data[0].url
                self._download_with_retry(image_url, output_path)
                return output_path

            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"   Attempt {attempt+1} failed: {e}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to generate image for scene {scene['scene_number']} "
                        f"after {retry_count} attempts: {e}"
                    )

    # ------------------------------------------------------------------ #
    #  Phase 1c: Generate a single scene image with Gemini Flash
    # ------------------------------------------------------------------ #

    # Map IMAGE_SIZE to Gemini aspect ratio string.
    _GEMINI_ASPECT_MAP = {
        "1024x1024": "1:1",
        "1024x1536": "2:3",
        "1536x1024": "3:2",
        "768x1024": "3:4",
        "1024x768": "4:3",
    }

    _GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

    def _generate_with_gemini_primary(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        retry_count: int = 3,
    ) -> str:
        """
        Generate an illustration using Gemini Flash with prior scene images
        as visual context for character consistency.
        """
        prompt = self._build_image_prompt(story, scene, scene_index)

        # Build contents: prior images for visual context, then text prompt
        contents = []
        if scene_index > 0 and self._prior_scene_images:
            # Always include scene 1 (character anchor)
            contents.append(self._prior_scene_images[0])
            # Also include the most recent scene if different from scene 1
            if len(self._prior_scene_images) >= 2:
                contents.append(self._prior_scene_images[-1])
            context_prefix = (
                "The images above are previous scenes from this children's storybook. "
                "Generate the next scene with the EXACT SAME character designs — same species, "
                "same colors, same clothing, same proportions, same face shapes, same art style. "
                "Do NOT change any character's appearance.\n\n"
            )
            contents.append(context_prefix + prompt)
        else:
            contents.append(prompt)

        aspect_ratio = self._GEMINI_ASPECT_MAP.get(self.size, "2:3")

        for attempt in range(retry_count):
            try:
                response = self.gemini_client.models.generate_content(
                    model=self._GEMINI_IMAGE_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                        ),
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image = part.as_image()
                        image.save(output_path)

                        # Store PIL image for future scene context
                        self._prior_scene_images.append(Image.open(output_path))
                        return output_path

                raise RuntimeError("No image returned in Gemini response")

            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"   Gemini attempt {attempt+1} failed: {e}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to generate image for scene {scene['scene_number']} "
                        f"after {retry_count} attempts: {e}"
                    )

    # ------------------------------------------------------------------ #
    #  Phase 1d: Generate a single scene image with GPT-image-1
    # ------------------------------------------------------------------ #

    def _build_gpt_image_prompt(self, story: dict, scene: dict, scene_index: int) -> str:
        """
        Build a detailed prompt for gpt-image-1-mini. No character limit,
        so we can include exhaustive character details.
        """
        style = self.animation_style
        scenes = story["scenes"]
        all_chars = story["characters"]

        character_block = "\n".join(
            f"- {c['name']} ({c['type']}): {c['description']}"
            for c in all_chars
        )

        scene_type = ""
        if scene_index == 0:
            scene_type = "This is the OPENING scene. Make it inviting and introduce all characters clearly."
        elif scene_index == len(scenes) - 1:
            scene_type = "This is the FINAL scene. Show a warm, happy conclusion."

        if scene_index == 0:
            prompt = f"""{style['description']}

SETTING: {story['setting']}

CHARACTERS — draw EVERY character EXACTLY as described. Each character's species, body colors, eye color, clothing colors, accessories, and proportions must match their description PRECISELY:
{character_block}

SCENE {scene['scene_number']} of {len(scenes)}:
{scene['image_description']}

{scene_type}

RULES:
- {style['image_rules']}
- EXACTLY {len(all_chars)} characters in this scene — no more, no less
- Keep IDENTICAL character designs (same colors, proportions, features, clothing)
- Warm, friendly expressions appropriate for a children's book
- Suitable for a 2-3 year old child
- DO NOT include any text, words, letters, or numbers in the image"""

        else:
            # Scenes 2+: lead with character visual sheet from scene 1 analysis
            visual_sheet = self._character_visual_sheet or ""
            sheet_section = ""
            if visual_sheet:
                sheet_section = f"""
IMPORTANT — CHARACTER VISUAL REFERENCE (how each character ACTUALLY looks — match this EXACTLY):
{visual_sheet}

"""
            prompt = f"""{style['description']}

{sheet_section}ORIGINAL CHARACTER DESCRIPTIONS:
{character_block}

SETTING: {story['setting']}

SCENE {scene['scene_number']} of {len(scenes)}:
{scene['image_description']}

{scene_type}

RULES:
- {style['image_rules']}
- EXACTLY {len(all_chars)} characters in this scene — no more, no less
- Every character MUST look IDENTICAL to how they appeared in scene 1 — same species, same face shape, same body proportions, same colors, same clothing, same accessories
- Warm, friendly expressions appropriate for a children's book
- Suitable for a 2-3 year old child
- DO NOT include any text, words, letters, or numbers in the image"""

        return prompt

    def _generate_with_gpt_image(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        retry_count: int = 3,
    ) -> str:
        """Generate an illustration for a single scene using gpt-image-1-mini."""
        prompt = self._build_gpt_image_prompt(story, scene, scene_index)

        for attempt in range(retry_count):
            try:
                result = self.openai_client.images.generate(
                    model="gpt-image-1-mini",
                    prompt=prompt,
                    size=self.size,
                    quality="medium",
                )

                image_bytes = base64.b64decode(result.data[0].b64_json)
                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                # After scene 1: analyze for character visual sheet
                if scene_index == 0:
                    print("   Analyzing scene 1 for character visual consistency...")
                    self._character_visual_sheet = self._analyze_reference_image(
                        output_path, story["characters"]
                    )
                    if self._character_visual_sheet:
                        print(f"   Character sheet extracted ({len(self._character_visual_sheet)} chars)")

                return output_path

            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"   GPT-image attempt {attempt+1} failed: {e}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to generate image for scene {scene['scene_number']} "
                        f"after {retry_count} attempts: {e}"
                    )

    # ------------------------------------------------------------------ #
    #  Phase 1: Dispatcher — route to the configured provider
    # ------------------------------------------------------------------ #

    def generate_scene_image(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        retry_count: int = 3,
    ) -> str:
        """Generate an illustration for a single scene using the configured provider."""
        if self.image_provider == "minimax":
            return self._generate_with_minimax(story, scene, scene_index, output_path, retry_count)
        elif self.image_provider == "gemini":
            return self._generate_with_gemini_primary(story, scene, scene_index, output_path, retry_count)
        elif self.image_provider == "gpt-image":
            return self._generate_with_gpt_image(story, scene, scene_index, output_path, retry_count)
        else:
            return self._generate_with_cogview(story, scene, scene_index, output_path, retry_count)

    # ------------------------------------------------------------------ #
    #  Phase 2: Review images with GPT-4o-mini vision
    # ------------------------------------------------------------------ #

    def _review_images(
        self,
        image_scene_pairs: list[tuple[str, dict]],
        characters: list[dict],
    ) -> dict[int, float]:
        """
        Review each generated image with GPT-4o-mini vision.

        Args:
            image_scene_pairs: List of (image_path, scene_dict) tuples
            characters: Full character list from the story

        Returns:
            dict mapping scene_number -> confidence (0.0-1.0)
        """
        character_block = "\n".join(
            f"- {c['name']} ({c['type']}): {c['description']}"
            for c in characters
        )

        scores = {}
        for image_path, scene in image_scene_pairs:
            scene_num = scene["scene_number"]
            try:
                with open(image_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")

                review_prompt = f"""You are reviewing an illustration for a children's storybook.

EXPECTED CHARACTERS:
{character_block}

SCENE DESCRIPTION:
{scene['image_description']}

Look at this image and rate your confidence (0.0 to 1.0) that:
1. All expected characters are present with the correct species
2. No unexpected/hallucinated characters dominate the scene
3. The scene matches the description

Respond ONLY with JSON: {{"confidence": 0.85, "reason": "short note"}}"""

                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": review_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_b64}",
                                        "detail": "low",
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=150,
                )

                raw = response.choices[0].message.content.strip()
                # Parse JSON from the response (handle markdown fences)
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                result = json.loads(raw)
                confidence = float(result.get("confidence", 1.0))
                reason = result.get("reason", "")
                scores[scene_num] = confidence
                print(f"   Scene {scene_num}: confidence={confidence:.2f} — {reason}")

            except Exception as e:
                # If review fails, don't block — assume it's fine
                print(f"   Scene {scene_num}: review failed ({e}), defaulting to 1.0")
                scores[scene_num] = 1.0

        return scores

    # ------------------------------------------------------------------ #
    #  Phase 3: Regenerate low-confidence images with Gemini
    # ------------------------------------------------------------------ #

    # Map IMAGE_SIZE to a Gemini-compatible aspect ratio string.
    _ASPECT_RATIO_MAP = {
        "1024x1024": "1:1",
        "1024x1536": "2:3",
        "1536x1024": "3:2",
        "768x1024": "3:4",
        "1024x768": "4:3",
    }

    def _regenerate_with_gemini(
        self,
        story: dict,
        scene: dict,
        scene_index: int,
        output_path: str,
        all_image_paths: list[str],
        retry_count: int = 3,
    ) -> str:
        """
        Regenerate an image using Gemini with up to 2 prior scene images as context.

        Args:
            story: Full story data
            scene: The scene to regenerate
            scene_index: Index of this scene (0-based)
            output_path: Where to save the new image
            all_image_paths: List of all current image paths (ordered by scene)
            retry_count: Number of retries

        Returns:
            str: Path to the saved image
        """
        # Collect up to 2 prior scene images for visual context
        prior_images = []
        for offset in [2, 1]:
            idx = scene_index - offset
            if 0 <= idx < len(all_image_paths) and os.path.exists(all_image_paths[idx]):
                try:
                    img = Image.open(all_image_paths[idx])
                    prior_images.append(img)
                except Exception:
                    pass

        # Build the text prompt
        scene_prompt = self._build_image_prompt(story, scene, scene_index)
        context_text = (
            "The images above are previous scenes from this children's storybook. "
            "Generate the next scene matching the SAME character designs and art style.\n\n"
            + scene_prompt
        )

        # Assemble contents: prior images first, then the text prompt
        contents = []
        for img in prior_images:
            contents.append(img)
        contents.append(context_text)

        aspect_ratio = self._ASPECT_RATIO_MAP.get(self.size, "2:3")

        for attempt in range(retry_count):
            try:
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash-image",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                        ),
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image = part.as_image()
                        image.save(output_path)
                        return output_path

                raise RuntimeError("No image returned in Gemini response")

            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"   Gemini attempt {attempt+1} failed: {e}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Gemini fallback failed for scene {scene['scene_number']} "
                        f"after {retry_count} attempts: {e}"
                    )

    # ------------------------------------------------------------------ #
    #  Orchestrator: generate all images with the full pipeline
    # ------------------------------------------------------------------ #

    def generate_all_images(
        self,
        story: dict,
        output_dir: str,
        progress_callback=None,
    ) -> list[str]:
        """
        Generate illustrations for all scenes using the full pipeline:
          1. Generate all with CogView-4
          2. Review all with GPT-4o-mini
          3. Regenerate low-confidence images with Gemini

        Args:
            story: The structured story data
            output_dir: Directory to save images
            progress_callback: Optional callback(scene_num, total, status)

        Returns:
            list[str]: Paths to all generated images in order
        """
        os.makedirs(output_dir, exist_ok=True)
        image_paths = []
        total = len(story["scenes"])

        # ── Phase 1: Generate all images with CogView-4 ──
        for i, scene in enumerate(story["scenes"]):
            scene_num = scene["scene_number"]
            filename = f"scene_{scene_num:02d}_raw.png"
            output_path = os.path.join(output_dir, filename)

            if progress_callback:
                progress_callback(scene_num, total, "generating")

            path = self.generate_scene_image(story, scene, i, output_path)
            image_paths.append(path)

            if progress_callback:
                progress_callback(scene_num, total, "done")

            # Brief pause between requests
            if i < total - 1:
                time.sleep(2)

        # ── Phase 2: Review all images with GPT-4o-mini ──
        if progress_callback:
            progress_callback(1, total, "reviewing")

        image_scene_pairs = list(zip(image_paths, story["scenes"]))
        scores = self._review_images(image_scene_pairs, story["characters"])

        # ── Phase 3: Regenerate low-confidence images with Gemini ──
        low_confidence = [
            (i, scene)
            for i, scene in enumerate(story["scenes"])
            if scores.get(scene["scene_number"], 1.0) < self.CONFIDENCE_THRESHOLD
        ]

        if low_confidence:
            print(f"\n   {len(low_confidence)} scene(s) below confidence threshold — regenerating with Gemini...")

        for idx, scene in low_confidence:
            scene_num = scene["scene_number"]

            if progress_callback:
                progress_callback(scene_num, total, "regenerating")

            try:
                output_path = image_paths[idx]
                self._regenerate_with_gemini(
                    story=story,
                    scene=scene,
                    scene_index=idx,
                    output_path=output_path,
                    all_image_paths=image_paths,
                )
                print(f"   Scene {scene_num}: regenerated with Gemini")
            except Exception as e:
                print(f"   Scene {scene_num}: Gemini fallback failed ({e}), keeping original")

        return image_paths
