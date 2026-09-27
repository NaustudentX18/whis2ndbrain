"""Bounded typed suggestion classifier for note transcripts.

Zero hallucination: uses exact lexical patterns, sentiment/urgency triggers, and
fails closed to 'unreviewed' and 'normal' priority when ambiguous.
"""

from __future__ import annotations

import re

from contracts.schemas import Category, SuggestionPayload, Urgency

_TODO_PATTERNS = [
    r"\b(todo|to-do|remember to|need to|don't forget to|must|action item|task)\b",
    r"^(buy|call|email|send|check|fix|clean|order|schedule)\b",
]

_MEETING_PATTERNS = [
    r"\b(meeting with|synced with|spoke with|talked to|discussed with|1-on-1|standup)\b",
]

_IDEA_PATTERNS = [
    r"\b(idea:|what if|concept:|thought experiment|brainstorm|feature idea)\b",
]

_HIGH_URGENCY_PATTERNS = [
    r"\b(urgent|asap|emergency|immediately|right now|critical|today)\b",
]

_LOW_URGENCY_PATTERNS = [
    r"\b(someday|eventually|low priority|no rush|whenever|when you can)\b",
]


def classify_transcript(text: str | None) -> SuggestionPayload:
    """Classify note text into bounded category and urgency.

    Returns typed suggestion. Does not overwrite or delete any raw data.
    """
    if not text or len(text.strip()) < 3:
        return SuggestionPayload(
            category=Category.UNREVIEWED.value,
            urgency=Urgency.NORMAL.value,
            actionable=False,
            confidence=0.0,
        )

    clean = text.strip().lower()

    # Determine Urgency
    urgency = Urgency.NORMAL.value
    confidence = 0.5
    if any(re.search(pat, clean) for pat in _HIGH_URGENCY_PATTERNS):
        urgency = Urgency.HIGH.value
        confidence = 0.85
    elif any(re.search(pat, clean) for pat in _LOW_URGENCY_PATTERNS):
        urgency = Urgency.LOW.value
        confidence = 0.8

    # Determine Category and Actionability
    category = Category.THOUGHT.value
    actionable = False

    if any(re.search(pat, clean) for pat in _TODO_PATTERNS):
        category = Category.TODO.value
        actionable = True
        confidence = max(confidence, 0.85)
    elif any(re.search(pat, clean) for pat in _MEETING_PATTERNS):
        category = Category.MEETING.value
        confidence = max(confidence, 0.8)
    elif any(re.search(pat, clean) for pat in _IDEA_PATTERNS):
        category = Category.IDEA.value
        confidence = max(confidence, 0.75)
    elif len(clean.split()) < 4:
        # Very short fragments remain unreviewed to prevent misclassification
        category = Category.UNREVIEWED.value
        confidence = 0.3

    return SuggestionPayload(
        category=category,
        urgency=urgency,
        actionable=actionable,
        confidence=confidence,
    )
