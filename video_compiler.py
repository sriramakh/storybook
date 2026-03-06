"""
Video Compiler Module for StoryBook Generator.
Compiles scene images into a slideshow video (MP4) with background music,
smooth slide transitions, and audio looping with fade-out.

Output format: 1080x1920 (9:16 vertical) for Instagram Reels / YouTube Shorts.
Requires ffmpeg installed on the system.
"""

import logging
import os
import subprocess

from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)

TRACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks")
DEFAULT_TRACK = "02_cozy_storytime"

SCENE_DURATION = 8       # seconds each scene is shown
TRANSITION_DURATION = 1  # seconds for crossfade between scenes
FPS = 30
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Track catalog: filename stem -> description for GPT selection
AVAILABLE_TRACKS = {
    "01_bedtime_magical": (
        "Calm, magical bedtime tune with twinkling sounds. "
        "Best for: nighttime stories, stars, moon, sleep, magical dreams"
    ),
    "02_cozy_storytime": (
        "Warm, cozy melody for family storytime. "
        "Best for: home, comfort, friendship, heartwarming tales, family"
    ),
    "03_fantasy_adventure": (
        "Upbeat adventure theme with wonder and excitement. "
        "Best for: quests, journeys, exploration, brave heroes, discoveries"
    ),
    "04_lullaby": (
        "Ultra-gentle lullaby, the softest and most calming track. "
        "Best for: very young audience, tender moments, peaceful endings, bedtime"
    ),
    "05_bright_cheerful": (
        "Bright, happy, and energetic tune. "
        "Best for: sunny days, celebrations, playing, joyful stories, parties"
    ),
    "06_playful_curiosity": (
        "Playful, curious melody with a sense of wonder. "
        "Best for: discovery, mischief, peeking, exploring new things, curiosity"
    ),
    "07_dreamy_clouds": (
        "Floaty, dreamy atmosphere with a gentle sway. "
        "Best for: imagination, flying, clouds, sky adventures, whimsical journeys"
    ),
    "08_silly_cartoon": (
        "Fun cartoon slapstick music with bouncy energy. "
        "Best for: funny stories, silly mishaps, wacky characters, slapstick comedy"
    ),
    "09_magical_forest": (
        "Enchanted woodland melody with nature atmosphere. "
        "Best for: forest adventures, animal stories, nature themes, woodland creatures"
    ),
    "10_the_glimmering_glade_expedition": (
        "Sparkling expedition theme with a sense of awe. "
        "Best for: trail exploration, discovery, glimmering magical environments, expeditions"
    ),
    "11_cloud_weaver_waltz": (
        "Graceful waltz with a whimsical, floating feel. "
        "Best for: dance, elegance, breeze, gentle movement stories, spinning and twirling"
    ),
}


class VideoCompiler:
    """Compiles scene images into a slideshow MP4 with background music."""

    def __init__(self, tracks_dir: str | None = None):
        self.tracks_dir = tracks_dir or TRACKS_DIR
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def select_track(self, story: dict) -> str:
        """Use GPT-4o-mini to pick the best background track for the story.

        Returns the full path to the selected .mp3 file.
        Falls back to the default track on any error.
        """
        track_list = "\n".join(
            f"- {name}: {desc}" for name, desc in AVAILABLE_TRACKS.items()
        )

        story_summary = (
            f"Title: {story.get('title', '')}\n"
            f"Setting: {story.get('setting', '')}\n"
            f"Moral: {story.get('moral', 'None')}\n"
            f"Characters: {', '.join(c.get('name', '') + ' (' + c.get('type', '') + ')' for c in story.get('characters', []))}\n"
            f"First scene: {story.get('scenes', [{}])[0].get('text', '')}"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You select background music for children's storybook videos. "
                            "Reply with ONLY the track filename stem (e.g. '03_fantasy_adventure'). "
                            "Nothing else — no explanation, no quotes, just the name."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Pick the single best background track for this children's story:\n\n"
                            f"{story_summary}\n\n"
                            f"Available tracks:\n{track_list}\n\n"
                            f"Reply with ONLY the track name."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=50,
            )
            choice = response.choices[0].message.content.strip()
            if choice in AVAILABLE_TRACKS:
                track_path = os.path.join(self.tracks_dir, f"{choice}.mp3")
                if os.path.exists(track_path):
                    logger.info(f"Selected track: {choice}")
                    return track_path

            logger.warning(f"GPT returned unknown track '{choice}', using default")
        except Exception as e:
            logger.warning(f"Track selection failed ({e}), using default")

        return os.path.join(self.tracks_dir, f"{DEFAULT_TRACK}.mp3")

    def compile_video(
        self,
        story: dict,
        image_paths: list[str],
        output_path: str,
        track_path: str | None = None,
    ) -> str:
        """Compile scene images into a slideshow MP4 with background music.

        Args:
            story: Story dict (used for track selection if track_path is None)
            image_paths: List of scene image file paths (JPG/PNG)
            output_path: Where to write the output .mp4
            track_path: Optional explicit track path; auto-selected if None

        Returns:
            The output_path of the created video.
        """
        if not image_paths:
            raise ValueError("No images provided for video compilation")

        if track_path is None:
            track_path = self.select_track(story)

        n = len(image_paths)
        total_duration = n * SCENE_DURATION - (n - 1) * TRANSITION_DURATION

        # Build ffmpeg input arguments
        # Each image becomes an 8-second video stream via -loop 1
        inputs = []
        for img in image_paths:
            inputs.extend(["-loop", "1", "-t", str(SCENE_DURATION), "-i", img])

        # Audio input: loop infinitely, we'll trim in the filter
        inputs.extend(["-stream_loop", "-1", "-i", track_path])
        audio_idx = n  # 0-indexed input number for the audio

        # Build the filter_complex
        filter_parts = []

        # Scale each image to target dimensions (center-crop to fit 9:16)
        for i in range(n):
            filter_parts.append(
                f"[{i}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
                f"force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                f"setsar=1,fps={FPS}[v{i}]"
            )

        # Chain xfade transitions between consecutive clips
        if n == 1:
            last_label = "v0"
        else:
            prev_label = "v0"
            for i in range(1, n):
                offset = i * SCENE_DURATION - i * TRANSITION_DURATION
                out_label = f"xf{i}"
                filter_parts.append(
                    f"[{prev_label}][v{i}]xfade=transition=slideleft:"
                    f"duration={TRANSITION_DURATION}:offset={offset}[{out_label}]"
                )
                prev_label = out_label
            last_label = prev_label

        # Audio: trim to video length, set to 50% volume, fade in (2s) and fade out (3s)
        fade_out_duration = 3
        filter_parts.append(
            f"[{audio_idx}:a]atrim=0:{total_duration},"
            f"volume=0.5,"
            f"afade=t=in:st=0:d=2,"
            f"afade=t=out:st={total_duration - fade_out_duration}:d={fade_out_duration},"
            f"asetpts=PTS-STARTPTS[aout]"
        )

        filter_complex = ";\n".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{last_label}]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(
            f"Compiling video: {n} scenes, {total_duration}s duration, "
            f"track={os.path.basename(track_path)}"
        )

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )

        if result.returncode != 0:
            stderr_tail = result.stderr[-1000:] if result.stderr else "no stderr"
            raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {stderr_tail}")

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Video compiled: {output_path} ({size_mb:.1f} MB)")

        return output_path
