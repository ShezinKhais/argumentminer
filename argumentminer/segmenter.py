"""Segment text into argumentative units: claims, premises, and conclusions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class SegmentType(str, Enum):
    CLAIM      = "claim"
    PREMISE    = "premise"
    CONCLUSION = "conclusion"
    BACKGROUND = "background"


@dataclass
class Segment:
    text: str
    type: SegmentType
    confidence: float
    start_char: int
    end_char: int


# Signal words that help identify each segment type.
#
# Every word here has to earn its place: a marker that also has a common
# non-argumentative sense fires on ordinary prose and drags most of the text
# into one bucket, which is worse than not classifying it at all.
_CONCLUSION_SIGNALS = re.compile(
    r'\b(therefore|thus|hence|consequently|as a result|in conclusion|'
    r'it follows that|which means|this proves|this shows)\b'
    # "so" marks a conclusion only when it opens a clause. Mid-sentence it is
    # almost always an intensifier ("so cold"), which matched everywhere.
    r'|(?:^|[.;,]\s*)so\b', re.I
)
_PREMISE_SIGNALS = re.compile(
    # "as" and "for" are deliberately absent. Their premise sense ("as he was
    # late", "for he was tired") is rare beside their use as ordinary
    # prepositions, so including them classified nearly every sentence as a
    # premise.
    r'\b(because|since|given that|in light of|considering that|'
    r'the fact that|evidence shows|studies show|research indicates)\b', re.I
)
_CLAIM_SIGNALS = re.compile(
    r'\b(I (argue|believe|claim|maintain|contend)|it is (clear|evident|obvious) that|'
    r'we (should|must|ought)|this (demonstrates|suggests|proves))\b', re.I
)


def _split_to_clauses(text: str) -> list[tuple[str, int, int]]:
    """Split text at sentence boundaries, returning (text, start, end) tuples.

    The offsets bracket the stripped text exactly, so text[start:end] gives the
    clause back. Reporting the raw match bounds alongside a stripped string put
    every clause after the first one character early, which shifts anything that
    highlights a segment in the source.
    """
    parts = []
    for m in re.finditer(r'[^.!?]+[.!?]?', text):
        raw = m.group()
        part = raw.strip()
        if len(part) > 10:
            start = m.start() + (len(raw) - len(raw.lstrip()))
            parts.append((part, start, start + len(part)))
    return parts


class ArgumentSegmenter:
    """Identifies argument structure in text using signal word patterns."""

    def segment(self, text: str) -> list[Segment]:
        """Break text into typed argument segments."""
        clauses = _split_to_clauses(text)
        segments = []
        for clause, start, end in clauses:
            seg_type, conf = self._classify(clause)
            segments.append(Segment(
                text=clause,
                type=seg_type,
                confidence=conf,
                start_char=start,
                end_char=end,
            ))
        return segments

    def _classify(self, text: str) -> tuple[SegmentType, float]:
        """Return the most likely type and a rough confidence."""
        if _CONCLUSION_SIGNALS.search(text):
            return SegmentType.CONCLUSION, 0.85
        if _PREMISE_SIGNALS.search(text):
            return SegmentType.PREMISE, 0.80
        if _CLAIM_SIGNALS.search(text):
            return SegmentType.CLAIM, 0.75
        # default - treat as background text
        return SegmentType.BACKGROUND, 0.50

    def get_claims(self, text: str) -> list[Segment]:
        return [s for s in self.segment(text) if s.type == SegmentType.CLAIM]

    def get_premises(self, text: str) -> list[Segment]:
        return [s for s in self.segment(text) if s.type == SegmentType.PREMISE]
