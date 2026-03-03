"""
Character Registry Module for StoryBook Generator.
Persists character type-to-name mappings across stories so that recurring
character types (e.g. "bear") always receive the same name (e.g. "Benny").
"""

import json
import os
from config import Config


# Common animal/creature keywords used to resolve a generic "animal" type
# to a more specific species by scanning the character description.
_SPECIFIC_TYPES = [
    "bear", "rabbit", "bunny", "fox", "owl", "deer", "mouse", "squirrel",
    "cat", "kitten", "dog", "puppy", "duck", "duckling", "frog", "turtle",
    "hedgehog", "penguin", "elephant", "lion", "tiger", "monkey", "bird",
    "parrot", "sparrow", "robin", "butterfly", "ladybug", "bee", "lamb",
    "sheep", "pig", "horse", "pony", "cow", "goat", "chicken", "hen",
    "rooster", "wolf", "badger", "otter", "raccoon", "panda",
]


class CharacterRegistry:
    """Maintains a persistent mapping of character type -> name + description."""

    def __init__(self, path: str | None = None):
        self.path = path or Config.CHARACTER_REGISTRY_PATH
        self.registry: dict[str, dict] = {}

    # ── persistence ──────────────────────────────────────────────────────── #

    def load(self):
        """Load the registry from disk (no-op if file doesn't exist yet)."""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.registry = json.load(f)

    def save(self):
        """Write the current registry to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    # ── update from a story ──────────────────────────────────────────────── #

    def update_from_story(self, story: dict):
        """
        Extract character type->name mappings from an approved story and
        merge them into the registry.  Only adds NEW types; existing entries
        are never overwritten so the first name "sticks".
        """
        for char in story.get("characters", []):
            raw_type = char.get("type", "")
            name = char.get("name", "")
            description = char.get("description", "")
            if not raw_type or not name:
                continue

            # Resolve generic types like "animal" to a specific species
            ctype = self._extract_specific_type(raw_type, description)
            ctype = self._normalize_type(ctype)

            if ctype and ctype not in self.registry:
                self.registry[ctype] = {
                    "name": name,
                    "description": description,
                }

        self.save()

    # ── prompt generation ─────────────────────────────────────────────────── #

    def get_prompt_text(self) -> str | None:
        """
        Build an LLM instruction string that tells the model to reuse
        previously established character names.

        Returns None if the registry is empty.
        """
        if not self.registry:
            return None

        lines = [
            "RECURRING CHARACTER NAMES — If you happen to include any of these "
            "species, use the established name. But do NOT feel obligated to include "
            "these species — feel free to create entirely new character types:"
        ]
        for ctype, info in self.registry.items():
            lines.append(f'- A {ctype} should be called "{info["name"]}"')

        lines.append(
            "You are encouraged to invent NEW species and characters not listed above."
        )
        return "\n".join(lines)

    # ── helpers ────────────────────────────────────────────────────────────── #

    @staticmethod
    def _extract_specific_type(raw_type: str, description: str) -> str:
        """
        If *raw_type* is a vague category like 'animal' or 'bird', scan the
        description for a more specific species keyword and return it.
        """
        generic_labels = {"animal", "bird", "creature", "object", "human", "character"}
        normalized = raw_type.strip().lower()

        if normalized not in generic_labels:
            return normalized

        desc_lower = description.lower()
        for species in _SPECIFIC_TYPES:
            if species in desc_lower:
                return species

        # Couldn't narrow it down — keep the original
        return normalized

    @staticmethod
    def _normalize_type(ctype: str) -> str:
        """Lowercase, strip whitespace, and basic de-pluralise."""
        ctype = ctype.strip().lower()
        # Very simple de-pluralise: remove trailing 's' for common cases
        if ctype.endswith("ies"):
            ctype = ctype[:-3] + "y"  # e.g. "bunnies" -> "bunny"
        elif ctype.endswith("es") and not ctype.endswith("ses"):
            ctype = ctype[:-2]  # e.g. "foxes" -> "fox"
        elif ctype.endswith("s") and not ctype.endswith("ss"):
            ctype = ctype[:-1]  # e.g. "bears" -> "bear"
        return ctype
