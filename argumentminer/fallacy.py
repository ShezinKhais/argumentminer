"""Detect common logical fallacies in text using pattern matching."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FallacyMatch:
    name: str
    description: str
    matched_text: str
    confidence: float


# each fallacy: (name, description, regex pattern, confidence)
FALLACY_PATTERNS: list[tuple[str, str, re.Pattern, float]] = [
    (
        "Ad Hominem",
        "Attacks the person rather than their argument.",
        re.compile(r'\b(stupid|idiot|fool|moron|ignorant|uneducated|'
                   r'you (don\'t|wouldn\'t) understand|typical \w+)\b', re.I),
        0.75,
    ),
    (
        "Straw Man",
        "Misrepresents the opponent's position to make it easier to attack.",
        re.compile(r'\b(so you\'re saying|you (think|believe|claim) that|'
                   r'your position is|what you\'re really saying)\b', re.I),
        0.65,
    ),
    (
        "Appeal to Authority",
        "Cites authority as evidence without proper justification.",
        re.compile(r'\b(experts (say|agree|believe)|scientists (say|agree|prove)|'
                   r'studies (show|prove|confirm)|according to (experts|scientists|'
                   r'researchers|authorities))\b', re.I),
        0.60,
    ),
    (
        "False Dichotomy",
        "Presents only two options when more exist.",
        re.compile(r'\b(either .+ or|you\'re (with us|against us)|'
                   r'(if you\'re not .+ then)|there (are only|is only) two)\b', re.I),
        0.70,
    ),
    (
        "Slippery Slope",
        "Claims one event will inevitably lead to extreme consequences.",
        re.compile(r'\b(will lead to|next thing you know|before (long|you know it)|'
                   r'eventually .+ will|if we allow .+ then|this is the first step)\b', re.I),
        0.65,
    ),
    (
        "Appeal to Emotion",
        "Manipulates emotions rather than using logical arguments.",
        re.compile(r'\b(think of the children|heartbreaking|devastating|outrageous|'
                   r'how (dare|could) (you|they)|this is a (tragedy|disgrace|shame))\b', re.I),
        0.60,
    ),
    (
        "Circular Reasoning",
        "The conclusion is used as a premise of the argument.",
        re.compile(r'\b(it\'s (true|correct|right) because (it is|I said so|everyone knows)|'
                   r'the (bible|law|rule) says so|by definition)\b', re.I),
        0.70,
    ),
    (
        "Hasty Generalization",
        "Draws a broad conclusion from a small or unrepresentative sample.",
        re.compile(r'\b(all \w+ are|every \w+ is|none of (them|the \w+)|'
                   r'they (all|always|never)|(always|never) (do|happens|works))\b', re.I),
        0.65,
    ),
]


class FallacyDetector:
    """Scans text for logical fallacies using pattern matching."""

    def detect(self, text: str) -> list[FallacyMatch]:
        """Return all fallacy matches found in text."""
        found = []
        for name, desc, pattern, conf in FALLACY_PATTERNS:
            for m in pattern.finditer(text):
                found.append(FallacyMatch(
                    name=name,
                    description=desc,
                    matched_text=m.group(),
                    confidence=conf,
                ))
        return found

    def detect_unique(self, text: str) -> list[FallacyMatch]:
        """Return the first match for each fallacy type found in text.

        Confidence is a property of the pattern, not of the individual match, so
        every hit on one fallacy carries the same score and there is nothing to
        rank them by. The earlier match wins, which keeps the results in the
        order the fallacies appear in the text.
        """
        seen: dict[str, FallacyMatch] = {}
        for m in self.detect(text):
            seen.setdefault(m.name, m)
        return list(seen.values())
