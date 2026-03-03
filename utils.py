"""
Shared utility functions for StoryBook Generator.
Extracted from app.py for reuse by both the CLI and the Telegram bot.
"""

import os
import re
import json


def sanitize_folder_name(title: str) -> str:
    """Convert a story title into a safe folder name."""
    # Remove special characters, keep alphanumeric and spaces
    clean = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    clean = re.sub(r'\s+', '_', clean.strip())
    return clean


def get_next_story_number(output_dir: str) -> int:
    """
    Determine the next serial number for a story folder.
    Scans existing folders in the output directory.
    """
    if not os.path.exists(output_dir):
        return 1

    existing = []
    for name in os.listdir(output_dir):
        if os.path.isdir(os.path.join(output_dir, name)):
            # Try to parse the serial number prefix
            match = re.match(r'^(\d+)_', name)
            if match:
                existing.append(int(match.group(1)))

    return max(existing, default=0) + 1


def create_story_folder(output_dir: str, serial_number: int, title: str) -> str:
    """
    Create the story folder: <output_dir>/<sno>_<title>/

    Returns:
        str: Path to the created folder
    """
    folder_name = f"{serial_number:03d}_{sanitize_folder_name(title)}"
    folder_path = os.path.join(output_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def save_story_json(story: dict, folder_path: str) -> str:
    """Save the story data as JSON for reference."""
    json_path = os.path.join(folder_path, "story_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(story, f, indent=2, ensure_ascii=False)
    return json_path
