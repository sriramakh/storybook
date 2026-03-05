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
8. Avoid anything genuinely scary, violent, or sad. Keep the tone gentle and reassuring.
   HOWEVER, mild comical mishaps are perfectly fine and encouraged — a character can
   trip and fall, bump their head, get a "boo-boo" on their knee from falling off a bicycle,
   two toy cars can bonk into each other, a character can slip on a banana peel, etc.
   These small slapstick moments make stories relatable and funny for toddlers. Just keep
   the tone lighthearted — the character always gets back up, laughs it off, or gets a
   comforting hug. No real injuries, no crying in pain, no lasting harm.
9. Be ORIGINAL — avoid cliché storylines. Surprise the reader with unexpected characters,
   settings, or plot turns that still feel cozy and age-appropriate.
10. Surprise the reader with UNUSUAL animal choices — vary species across stories. Avoid
    defaulting to the same common animals (rabbits, bears, squirrels, foxes) every time.
11. VARY THE LOCATIONS across scenes. Characters should TRAVEL and EXPLORE — move from
    one place to another as the story progresses. For example: start at a cozy home,
    walk through a meadow, discover a waterfall, visit a market, end at a hilltop at sunset.
    Every scene should NOT have the same background. Make each scene's location visually
    distinct and interesting.
12. CONTEXT-AWARE CHARACTERS: When the user provides a story description, your characters
    MUST match the context. If the user says "father teaching daughter to ride a bicycle",
    the father and daughter MUST be human — do NOT substitute them with random animals.
    If the user says "fish helping friends escape a shark", ALL the friends MUST be aquatic
    creatures (fish, octopus, seahorse, turtle, etc.) — do NOT use land animals like flamingos.
    Respect the user's intent precisely. Only add animal/fantasy characters when the description
    calls for them or leaves the choice open.
13. FLEXIBLE CHARACTER COUNT: Use as many characters as the story naturally requires — NOT
    always 3. A story about a father and daughter needs 2 main characters (plus optional
    side characters). A story about a school of fish may need 5-6. A solo adventure needs 1.
    Let the plot dictate the cast size (typically 2-6 characters).

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
    "setting": "The story's world or starting environment - general region, season, time period.
     Example: A magical forest kingdom in early autumn",
    "art_style": "A consistent art style description for all illustrations. Example: Soft watercolor 
     illustration style, warm pastel colors, rounded friendly shapes, picture book quality, 
     hand-drawn feel with gentle lighting",
    "moral": "A gentle moral in one simple sentence, OR null if the story is just a fun adventure",
    "instagram_caption": "A single catchy, heartwarming line for Instagram — include 2-3 relevant
     emojis, make it appeal to parents of toddlers. Example: Tiny fins, big courage — sometimes
     the smallest fish makes the biggest splash 🐠✨🌊",
    "scenes": [
        {{
            "scene_number": 1,
            "background": "The specific location/environment for THIS scene — should change as
             characters travel. Include colors, lighting, time of day, weather, landmarks.
             Example: A cozy treehouse kitchen with warm lantern light, wooden shelves full of
             jars, and a round window showing a pink sunrise",
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
- Make the story flow naturally from one scene to the next
- CRITICAL: Each scene MUST have a DIFFERENT background/location. Characters should journey
  through varied environments (e.g. home → garden → river → mountain → village → beach).
  Do NOT set every scene in the same place. The background field must be unique per scene."""


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
                "Build the story around this idea. IMPORTANT: The characters MUST match the "
                "user's description exactly. If the user mentions humans (father, daughter, boy, "
                "girl, etc.), use HUMAN characters — do NOT replace them with animals. If the "
                "user mentions specific animals or a specific environment (ocean, jungle, farm), "
                "ALL characters must fit that context. Respect the user's intent precisely.\n"
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

        # Inject species ideas only for auto mode — in custom mode the user's
        # description dictates the characters, and random species would mislead the model
        if not description:
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
            for field in ["scene_number", "text", "image_description", "background"]:
                if field not in scene:
                    raise ValueError(f"Scene {i+1} is missing field: '{field}'")

    def regenerate_scenes(
        self,
        story: dict,
        scene_numbers: list[int],
        instructions: str = "",
    ) -> dict:
        """
        Rewrite specific scenes based on user instructions.

        Args:
            story: The full story dict
            scene_numbers: List of scene numbers (1-based) to rewrite
            instructions: User's description of what to change

        Returns:
            dict: Updated story with rewritten scenes
        """
        char_block = "\n".join(
            f"- {c['name']} ({c['type']}): {c['description']}"
            for c in story["characters"]
        )

        scenes_context = []
        for s in story["scenes"]:
            if s["scene_number"] in scene_numbers:
                scenes_context.append(
                    f"Scene {s['scene_number']} [REWRITE]: {s['text']}"
                )
            else:
                scenes_context.append(
                    f"Scene {s['scene_number']}: {s['text']}"
                )

        instruction_block = ""
        if instructions:
            instruction_block = f"""
USER'S REQUESTED CHANGES:
{instructions}

Follow the user's instructions precisely when rewriting the marked scenes.
"""

        prompt = f"""You are rewriting specific scenes in an existing children's bedtime story.
Keep the story's tone, characters, and flow consistent.

STORY TITLE: {story['title']}
SETTING: {story['setting']}
ART STYLE: {story['art_style']}

CHARACTERS:
{char_block}

CURRENT SCENES:
{chr(10).join(scenes_context)}
{instruction_block}
Rewrite ONLY the scenes marked [REWRITE]. Apply the user's requested changes if provided,
otherwise provide fresh text. Each rewritten scene needs a new image_description and
background that fit the story flow — the scene before and after should connect naturally.

Return ONLY a JSON array of the rewritten scenes:
[
    {{
        "scene_number": N,
        "background": "new background for this scene",
        "text": "new story text for this scene",
        "image_description": "new image description for this scene"
    }}
]

RULES:
- Keep text SHORT (2-3 sentences max, for a 2-3 year old)
- Reference characters by their EXACT visual descriptions
- Each scene must have a DIFFERENT background from its neighbours
- Mild comical mishaps (tripping, bumping, small boo-boos) are fine
- Return ONLY valid JSON array, no extra text"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=4096,
        )

        raw = response.choices[0].message.content
        new_scenes = json.loads(self._extract_json_array(raw))

        # Merge regenerated scenes back into the story
        scene_map = {s["scene_number"]: s for s in new_scenes}
        for i, scene in enumerate(story["scenes"]):
            if scene["scene_number"] in scene_map:
                new = scene_map[scene["scene_number"]]
                story["scenes"][i]["text"] = new["text"]
                story["scenes"][i]["image_description"] = new["image_description"]
                story["scenes"][i]["background"] = new.get("background", scene.get("background", ""))

        return story

    @staticmethod
    def _extract_json_array(text: str) -> str:
        """Extract a JSON array string from model output."""
        text = text.strip()
        # Try direct parse
        if text.startswith("["):
            return text

        # Try markdown fence
        import re as _re
        match = _re.search(r"```(?:json)?\s*\n(.*?)\n```", text, _re.DOTALL)
        if match:
            return match.group(1)

        # Find first [ ... ] block
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            return text[start : end + 1]

        raise ValueError("Could not extract JSON array from model response")

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
