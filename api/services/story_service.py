import os
import sys
import json
import uuid
import threading
import logging
from datetime import datetime, timezone

# Add parent directory to path so we can import StoryBook modules
_STORYBOOK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _STORYBOOK_ROOT not in sys.path:
    sys.path.insert(0, _STORYBOOK_ROOT)

from story_generator import StoryGenerator
from image_generator import ImageGenerator
from text_overlay import TextOverlay
from video_compiler import VideoCompiler
from pdf_compiler import StoryBookPDF
from character_registry import CharacterRegistry
from config import Config
from utils import get_next_story_number, create_story_folder, save_story_json

logger = logging.getLogger(__name__)


class StoryService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.jobs: dict[str, dict] = {}
        self.stories_dir = os.path.join(_STORYBOOK_ROOT, Config.OUTPUT_DIR)
        os.makedirs(self.stories_dir, exist_ok=True)

    def start_generation(
        self,
        description: str | None,
        num_scenes: int,
        animation_style: str | None,
        age_group: str | None,
    ) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "story_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job_id, description, num_scenes, animation_style),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job_status(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def _update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)

    def _run_pipeline(
        self,
        job_id: str,
        description: str | None,
        num_scenes: int,
        animation_style: str | None,
    ):
        try:
            # Phase 1: Generate story text
            self._update_job(job_id, status="generating_story", progress=0.05, message="Generating story text...")

            style_config = None
            art_style_hint = None
            if animation_style and animation_style in Config.ANIMATION_STYLES:
                style_config = Config.ANIMATION_STYLES[animation_style]
                art_style_hint = style_config.get("story_art_style")

            registry = CharacterRegistry()
            character_prompt = registry.get_prompt_text()

            generator = StoryGenerator()
            story = generator.generate_story(
                num_scenes=num_scenes,
                description=description,
                art_style_hint=art_style_hint,
                character_names_prompt=character_prompt,
            )

            self._update_job(job_id, progress=0.15, message="Story text generated")

            # Create story folder
            serial = get_next_story_number(self.stories_dir)
            folder_path = create_story_folder(self.stories_dir, serial, story["title"])
            save_story_json(story, folder_path)
            story_id = os.path.basename(folder_path)

            # Phase 2: Generate images
            self._update_job(
                job_id, status="generating_images", progress=0.20,
                message="Generating illustrations...", story_id=story_id,
            )

            total_scenes = len(story.get("scenes", []))

            def image_progress_callback(scene_num, total, status):
                base = 0.20
                span = 0.50
                pct = base + span * (scene_num / max(total, 1))
                status_labels = {
                    "generating": f"Generating image {scene_num}/{total}...",
                    "done": f"Image {scene_num}/{total} done",
                    "reviewing": "Reviewing images with GPT-4o-mini...",
                    "regenerating": f"Regenerating image {scene_num}/{total} with Gemini...",
                }
                self._update_job(
                    job_id, progress=round(pct, 2),
                    message=status_labels.get(status, f"Processing scene {scene_num}/{total}..."),
                )

            img_gen = ImageGenerator(animation_style=style_config)
            raw_image_paths = img_gen.generate_all_images(
                story=story,
                output_dir=folder_path,
                progress_callback=image_progress_callback,
            )

            # Phase 3: Text overlay
            self._update_job(
                job_id, status="overlaying_text", progress=0.75,
                message="Overlaying text on images...",
            )

            overlay = TextOverlay()
            final_image_paths = overlay.process_all_scenes(
                story=story,
                raw_image_paths=raw_image_paths,
                output_dir=folder_path,
            )

            # Phase 4: Compile video
            self._update_job(
                job_id, status="compiling_video", progress=0.80,
                message="Compiling video slideshow...",
            )

            vid_compiler = VideoCompiler()
            video_path = os.path.join(folder_path, "story.mp4")
            try:
                vid_compiler.compile_video(
                    story=story,
                    image_paths=final_image_paths,
                    output_path=video_path,
                )
            except Exception as e:
                logger.warning(f"Video compilation failed for job {job_id}: {e}")

            # Phase 5: Compile PDF
            self._update_job(
                job_id, status="compiling_pdf", progress=0.90,
                message="Compiling PDF storybook...",
            )

            pdf_path = os.path.join(folder_path, "story.pdf")
            pdf_compiler = StoryBookPDF()
            pdf_compiler.compile_pdf(
                story=story,
                image_paths=final_image_paths,
                output_path=pdf_path,
            )

            # Update character registry
            registry.update_from_story(story)
            registry.save()

            self._update_job(
                job_id, status="completed", progress=1.0,
                message="Story complete!", story_id=story_id,
            )
            logger.info(f"Job {job_id} completed: {story_id}")

        except Exception as e:
            logger.exception(f"Job {job_id} failed")
            self._update_job(
                job_id, status="failed", message=f"Generation failed: {str(e)}",
            )

    def list_stories(self, page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
        all_stories = []

        if not os.path.exists(self.stories_dir):
            return [], 0

        for name in sorted(os.listdir(self.stories_dir), reverse=True):
            folder = os.path.join(self.stories_dir, name)
            json_path = os.path.join(folder, "story_data.json")
            if os.path.isdir(folder) and os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        story = json.load(f)
                    story["_folder_name"] = name
                    story["_folder_path"] = folder
                    all_stories.append(story)
                except (json.JSONDecodeError, OSError):
                    continue

        total = len(all_stories)
        start = (page - 1) * per_page
        end = start + per_page
        return all_stories[start:end], total

    def get_story(self, story_id: str) -> dict | None:
        folder = os.path.join(self.stories_dir, story_id)
        json_path = os.path.join(folder, "story_data.json")
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                story = json.load(f)
            story["_folder_name"] = story_id
            story["_folder_path"] = folder
            return story
        except (json.JSONDecodeError, OSError):
            return None

    def get_scene_image_path(self, story_id: str, scene_num: int) -> str | None:
        folder = os.path.join(self.stories_dir, story_id)
        raw_path = os.path.join(folder, f"scene_{scene_num:02d}_raw.png")
        if os.path.exists(raw_path):
            return raw_path
        # Fallback to overlaid version
        overlaid_path = os.path.join(folder, f"scene_{scene_num:02d}.jpg")
        if os.path.exists(overlaid_path):
            return overlaid_path
        return None

    def get_pdf_path(self, story_id: str) -> str | None:
        folder = os.path.join(self.stories_dir, story_id)
        pdf_path = os.path.join(folder, "story.pdf")
        if os.path.exists(pdf_path):
            return pdf_path
        return None

    def _story_to_response(self, story: dict, base_url: str = "") -> dict:
        story_id = story.get("_folder_name", "")
        folder_path = story.get("_folder_path", "")
        scenes = []
        for scene in story.get("scenes", []):
            snum = scene.get("scene_number", 0)
            scenes.append({
                "scene_number": snum,
                "text": scene.get("text", ""),
                "background": scene.get("background", ""),
                "image_url": f"{base_url}/api/v1/stories/{story_id}/scenes/{snum}/image",
            })

        pdf_path = os.path.join(folder_path, "story.pdf") if folder_path else ""
        has_pdf = os.path.exists(pdf_path) if pdf_path else False

        # Get creation time from folder
        created_at = ""
        if folder_path and os.path.exists(folder_path):
            ts = os.path.getctime(folder_path)
            created_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        characters = [
            {"name": c.get("name", ""), "type": c.get("type", ""), "description": c.get("description", "")}
            for c in story.get("characters", [])
        ]

        return {
            "id": story_id,
            "title": story.get("title", ""),
            "setting": story.get("setting", ""),
            "art_style": story.get("art_style", ""),
            "moral": story.get("moral"),
            "characters": characters,
            "scenes": scenes,
            "animation_style": story.get("animation_style"),
            "created_at": created_at,
            "pdf_url": f"{base_url}/api/v1/stories/{story_id}/pdf" if has_pdf else None,
        }


story_service = StoryService()
