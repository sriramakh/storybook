"""
Story Generator Module for StoryBook Generator.
Uses OpenAI GPT-4o-mini (via OpenAI API) to generate structured children's bedtime stories.
"""

import json
import random
import re
from openai import OpenAI
from config import Config


# --------------------------------------------------------------------------- #
#  System prompt that acts as the "children's story author" persona
# --------------------------------------------------------------------------- #
STORY_SYSTEM_PROMPT = """You are an award-winning children's bedtime story author who specializes in writing
stories for toddlers aged 2-3 years old. Your stories are warm, gentle, and imaginative.

RULES:
1. Stories must involve animals, birds, humans, and everyday objects that children recognize.
2. Stories must always have a HAPPY ENDING.
3. A moral is OPTIONAL. Some stories are just fun adventures — not every story needs a lesson.
   If the story naturally lends itself to a gentle takeaway, include it. Otherwise set
   "moral" to null in the JSON. When you do include a moral, make it FRESH and SURPRISING —
   never default to "sharing is caring" or "be kind to others".
4. Use simple, repetitive language that toddlers enjoy.
5. Characters should have friendly, easy-to-pronounce names.
6. Scenes should be vivid and colorful - describe colors, sounds, and feelings.
7. Each scene should naturally flow into the next.
8. Avoid anything scary, violent, or sad. Keep the tone gentle and reassuring.
9. Be ORIGINAL — avoid cliché storylines. Surprise the reader with unexpected characters,
   settings, or plot turns that still feel cozy and age-appropriate.
10. Surprise the reader with UNUSUAL animal choices — vary species across stories. Avoid
    defaulting to the same common animals (rabbits, bears, squirrels, foxes) every time.

You MUST respond ONLY with valid JSON in the exact format specified. No markdown, no extra text."""


# --------------------------------------------------------------------------- #
#  A large pool of moral / theme ideas — a random subset is injected each run
#  so the model gets fresh inspiration and avoids repeating the same stories.
# --------------------------------------------------------------------------- #
STORY_THEMES = [
    "Curiosity is a superpower — asking 'why?' helps you discover amazing things",
    "It's okay to feel shy; brave things can start with a tiny step",
    "Mistakes are how we learn — every oops is a step closer to hooray",
    "Everyone has a special talent, even if it takes time to find it",
    "Trying new foods can be a yummy adventure",
    "Nature is full of wonders if you slow down and look closely",
    "It's okay to ask for help — nobody has to do everything alone",
    "Listening carefully can teach you surprising things",
    "Being patient is hard, but good things come to those who wait",
    "You can be brave AND scared at the same time",
    "Taking care of a pet or plant teaches you about love and responsibility",
    "Dancing, singing, and making art are ways to show how you feel",
    "Old things and new things can both be wonderful",
    "Even the smallest creature can make a big difference",
    "Saying sorry (and meaning it) can fix a broken friendship",
    "Home is wherever you feel safe and loved",
    "Every season brings its own special magic",
    "You don't have to be fast to finish — steady and careful wins too",
    "Books and stories can take you anywhere in the world",
    "Getting lost can lead to the best discoveries",
    "Helping someone without being asked is extra special",
    "Sleep and rest give you energy for tomorrow's adventures",
    "Being different is what makes you interesting",
    "A messy room can become an imaginary kingdom",
    "Whispering is just as powerful as shouting",
    "Clouds, puddles, and bugs are worth stopping to admire",
    "Making a new friend starts with saying hello",
    "You can turn a bad day around with one silly idea",
    "Building something with your own hands feels amazing",
    "Grandparents and elders have the best stories to tell",
    "The dark isn't scary when you bring your imagination along",
    "Water, mud, and sand are nature's best toys",
    "Laughing together makes everything better",
    "Sometimes the journey is more fun than the destination",
    "Cleaning up can be a game if you make it one",
    "A little bit of practice every day adds up to something great",
    "Rainy days are perfect for cozy indoor adventures",
    "Saying 'thank you' makes two people happy — you and them",
    "Growing up doesn't mean you have to stop pretending",
    "Even grown-ups make mistakes and that's perfectly fine",
]


# --------------------------------------------------------------------------- #
#  A large pool of character species — a random subset is injected each run
#  so the model gets fresh inspiration and stops defaulting to bunny/bear/squirrel.
# --------------------------------------------------------------------------- #
CHARACTER_SPECIES_POOL = [
    # Woodland
    "hedgehog", "badger", "dormouse", "red fox", "mole", "pine marten",
    "woodpecker", "chipmunk", "beaver", "porcupine",
    # Ocean & river
    "sea otter", "seahorse", "jellyfish", "octopus", "dolphin", "hermit crab",
    "starfish", "pufferfish", "narwhal", "manatee",
    # Farm & meadow
    "goat", "donkey", "rooster", "goose", "piglet", "lamb",
    "highland cow", "barn cat", "sheepdog", "alpaca",
    # Jungle & tropical
    "toucan", "chameleon", "sloth", "tree frog", "parrot", "lemur",
    "capybara", "tapir", "okapi", "pangolin",
    # Savanna & desert
    "meerkat", "warthog", "flamingo", "gecko", "tortoise", "fennec fox",
    "armadillo", "hummingbird", "roadrunner", "camel",
    # Insects & tiny creatures
    "ladybug", "firefly", "caterpillar", "dragonfly", "bumblebee",
    "snail", "ant", "cricket", "butterfly", "inchworm",
    # Birds
    "robin", "blue jay", "puffin", "pelican", "kingfisher",
    "sparrow", "wren", "owl", "heron", "swan",
    # Cold & mountain
    "penguin", "arctic fox", "snow leopard", "mountain goat", "yak",
    "red panda", "chinchilla", "ermine", "walrus", "snowy owl",
    # Reptiles & amphibians
    "salamander", "newt", "iguana", "box turtle", "axolotl",
    "gecko", "tree lizard", "toad", "skink", "chameleon",
]


# --------------------------------------------------------------------------- #
#  The user prompt that requests the structured story
# --------------------------------------------------------------------------- #
STORY_USER_PROMPT = """Create a children's bedtime story with {num_scenes} scenes.

Return your response as a JSON object with this EXACT structure:
{{
    "title": "The Story Title",
    "characters": [
        {{
            "name": "Character Name",
            "type": "animal/bird/human/object",
            "description": "Detailed visual description including species, color, size, clothing, 
             distinctive features - be VERY specific so an artist can draw them consistently. 
             Example: A small fluffy white rabbit with long floppy ears, bright blue eyes, 
             wearing a tiny red scarf and brown boots"
        }}
    ],
    "setting": "Detailed description of the story's main setting/environment - colors, time of day, 
     season, specific landmarks. Example: A sunny meadow with tall green grass, colorful wildflowers, 
     a sparkling blue stream, and a big oak tree with a red door at its base",
    "art_style": "A consistent art style description for all illustrations. Example: Soft watercolor 
     illustration style, warm pastel colors, rounded friendly shapes, picture book quality, 
     hand-drawn feel with gentle lighting",
    "moral": "A gentle moral in one simple sentence, OR null if the story is just a fun adventure",
    "scenes": [
        {{
            "scene_number": 1,
            "text": "The story text for this scene - 2-3 short sentences maximum, using simple 
             words a 2-3 year old understands. This text will be displayed on the illustration.",
            "image_description": "Detailed description of what should be shown in this scene's 
             illustration. Include character positions, expressions, actions, background elements, 
             colors, and mood. Reference the exact character descriptions from above."
        }}
    ]
}}

IMPORTANT:
- Generate exactly {num_scenes} scenes
- The first scene should introduce the characters and setting
- The last scene should show the happy ending (and subtly convey the moral, if one exists)
- Each scene's image_description must reference characters by their EXACT visual descriptions 
  to ensure visual consistency across all illustrations
- Scene text should be SHORT (2-3 sentences max) - remember this is for a 2-3 year old
- Make the story flow naturally from one scene to the next"""


class StoryGenerator:
    """Generates structured children's stories using OpenAI GPT-4o-mini."""

    def __init__(self):
        self.client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
        )
        self.model = Config.STORY_MODEL

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a response that may contain markdown fences or extra text."""
        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try finding the first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])

        raise ValueError("Could not extract valid JSON from model response")

    def generate_story(
        self,
        num_scenes: int = 12,
        description: str | None = None,
        art_style_hint: str | None = None,
        character_names_prompt: str | None = None,
    ) -> dict:
        """
        Generate a structured children's bedtime story.

        Args:
            num_scenes: Number of scenes (10-15)
            description: Optional user-provided story brief
            art_style_hint: Optional art-style direction for the LLM
            character_names_prompt: Optional instruction to reuse character names

        Returns:
            dict: Structured story data with title, characters, scenes, etc.
        """
        num_scenes = max(Config.MIN_SCENES, min(Config.MAX_SCENES, num_scenes))

        # Build the user prompt with optional sections
        parts = []
        if description:
            parts.append(
                f"The user wants a story about: {description}\n"
                "Build the story around this idea.\n"
            )
        parts.append(STORY_USER_PROMPT.format(num_scenes=num_scenes))

        # Inject a random subset of theme ideas — moral is optional
        theme_sample = random.sample(STORY_THEMES, min(5, len(STORY_THEMES)))
        theme_bullets = "\n".join(f"  - {t}" for t in theme_sample)
        parts.append(
            "THEME INSPIRATION (you may weave ONE of these into the story as a moral, "
            "invent your own, or skip the moral entirely and just tell a fun adventure — "
            "do NOT force a lesson if it doesn't fit naturally):\n" + theme_bullets
        )

        # Inject a random subset of species ideas — encourages variety
        species_sample = random.sample(
            CHARACTER_SPECIES_POOL, min(10, len(CHARACTER_SPECIES_POOL))
        )
        species_list = ", ".join(species_sample)
        parts.append(
            "CHARACTER INSPIRATION — Choose from DIFFERENT and UNEXPECTED species. "
            "Avoid always using rabbits, bears, and squirrels. "
            "Here are some ideas (pick 2-3 that inspire you, or invent your own):\n"
            f"  {species_list}"
        )

        if character_names_prompt:
            parts.append(character_names_prompt)
        if art_style_hint:
            parts.append(
                f"ART DIRECTION: The illustrations will be rendered in {art_style_hint}. "
                "Keep your art_style field consistent with this direction."
            )

        user_content = "\n\n".join(parts)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.9,
            max_tokens=8192,
        )

        raw_content = response.choices[0].message.content
        story_data = self._extract_json(raw_content)

        # Validate the story structure
        self._validate_story(story_data, num_scenes)

        return story_data

    def _validate_story(self, story: dict, expected_scenes: int):
        """Validate that the story has all required fields."""
        required_keys = ["title", "characters", "setting", "art_style", "scenes"]
        for key in required_keys:
            if key not in story:
                raise ValueError(f"Story is missing required field: '{key}'")

        if not story["characters"]:
            raise ValueError("Story must have at least one character")

        if not story["scenes"]:
            raise ValueError("Story must have at least one scene")

        # Validate each scene
        for i, scene in enumerate(story["scenes"]):
            for field in ["scene_number", "text", "image_description"]:
                if field not in scene:
                    raise ValueError(f"Scene {i+1} is missing field: '{field}'")

    def format_story_preview(self, story: dict) -> str:
        """
        Format the story for a nice terminal preview.

        Args:
            story: The structured story data

        Returns:
            str: Formatted preview string
        """
        lines = []
        lines.append(f"\n{'='*70}")
        lines.append(f"📖  {story['title'].upper()}")
        lines.append(f"{'='*70}")

        lines.append(f"\n🎭 Characters:")
        for char in story["characters"]:
            lines.append(f"   • {char['name']} ({char['type']}): {char['description']}")

        lines.append(f"\n🌍 Setting: {story['setting']}")
        lines.append(f"\n🎨 Art Style: {story['art_style']}")
        if story.get("moral"):
            lines.append(f"\n💡 Moral: {story['moral']}")

        lines.append(f"\n{'─'*70}")
        lines.append("📜 STORY SCENES:")
        lines.append(f"{'─'*70}")

        for scene in story["scenes"]:
            lines.append(f"\n  Scene {scene['scene_number']}:")
            lines.append(f"  📝 {scene['text']}")
            lines.append(f"  🖼️  {scene['image_description'][:100]}...")

        lines.append(f"\n{'='*70}\n")
        return "\n".join(lines)
