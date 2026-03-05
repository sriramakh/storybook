import re


BLOCKED_WORDS = [
    "violence", "violent", "weapon", "weapons", "blood", "bloody", "murder",
    "kill", "killing", "horror", "demon", "devil",
    "drug", "drugs", "alcohol", "beer", "wine", "cigarette", "tobacco", "smoking",
    "sex", "sexual", "naked", "nude", "gun", "guns", "sword", "war",
    "zombie", "zombies", "poison", "abuse", "racist",
    "racism", "torture", "kidnap", "suicide", "bomb",
    "explosive", "terror", "terrorist", "assault", "strangle", "suffocate",
]

BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in BLOCKED_WORDS) + r")\b",
    re.IGNORECASE,
)


class SafetyFilter:
    def is_safe(self, text: str) -> tuple[bool, str | None]:
        if not text or not text.strip():
            return True, None

        match = BLOCKED_PATTERN.search(text)
        if match:
            return False, f"Input contains inappropriate content for children: '{match.group()}'"

        return True, None


safety_filter = SafetyFilter()
