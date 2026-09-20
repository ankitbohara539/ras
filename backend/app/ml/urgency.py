"""Reads a comment and decides whether it is pushing for the problem to be fixed.

That covers the explicit ("urgent", "asap") and the everyday: a complaint
("it has been quite a headache", "this is a big problem") or a plain request
("fix this", "please repair", "when will this be fixed?"). People who want
something done rarely write "urgent"; they complain. What does not count is
the neutral -- "thanks", "I saw it too", "is this the one near the bus stop?".

Deliberately a phrase list, not a model. The effect -- raising a ticket's
priority -- has to be something an officer can predict and a citizen can be
told ("three people asked for this to be fixed"), and a phrase that matched
is an explanation, where a classifier's 0.71 is not. It also has to work on
day one with no labelled comments to train on.

Covers English, Nepali in Devanagari, and romanised Nepali, because that is
how people actually type in the comment box.
"""

from __future__ import annotations

import re

# Matched on word boundaries, case-insensitively.
_ENGLISH = [
    # Explicit urgency.
    r"urgent(ly)?",
    r"asap",
    r"emergency",
    r"immediately",
    r"right (now|away)",
    r"rn",
    r"as soon as possible",
    r"(very|really|extremely|so|too) (dangerous|risky|bad|serious)",
    r"dangerous",
    r"(someone|somebody|people|children|kids) (will|could|might|may) (get )?(hurt|die|be injured|fall)",
    r"accidents?",
    r"injur(y|ies|ed)",
    # Asking for it to be fixed. "fix" as a word does not match "fixed", so
    # "I think it was fixed already" stays neutral.
    r"(please|pls|plz|kindly) (fix|repair|solve|resolve|clean|clear|remove|help|act|do something)",
    r"(fix|repair|solve|resolve|clean|clear|remove) (this|it|that|the \w+)",
    r"do something",
    r"take action",
    r"needs? (to be )?(fixing|fixed|repair(ing|ed)?|attention|action|cleaning)",
    r"(should|must|has to|have to) be (fixed|repaired|solved|resolved|cleaned|removed|done)",
    r"when (will|is|are) (this|it|they|you|someone)\b.*\b(fix|fixed|repair|repaired|solve|solved|done|clean|cleaned)",
    r"how long (will|do|does|must|should)",
    # Complaining about it.
    r"(big|major|serious|huge|real|critical|such a) (problem|issue|risk|hazard|trouble|mess)",
    r"(is|was|has been|it'?s) (a|an|such a|quite a|really a) (problem|issue|headache|nuisance|hazard|trouble|mess|nightmare)",
    r"this is (a )?problem",
    r"headache",
    r"nuisance",
    r"annoying",
    r"frustrat(ing|ed)",
    r"suffer(ing)?",
    r"(terrible|horrible|awful|pathetic|worst|disgusting|unbearable)",
    r"fed up",
    r"tired of",
    r"(can'?t|cannot|unable to|hard to|difficult to) (walk|drive|ride|pass|cross|use|sleep|breathe|get through)",
    r"(still|nothing) (not )?(fixed|done|repaired|broken|there|happening)",
    r"no (one|body) (cares|is doing|has done|came)",
    r"no action",
    r"(days|weeks|months) (and|now|already)?\s*(nothing|no action|still)",
    r"(getting|became|becoming) worse",
    r"stinks?|smells? (bad|terrible|awful)",
]

_ROMANISED_NEPALI = [
    r"chad[oa]i",
    r"chhit[oa]",
    r"jaruri",
    r"turuntai",
    r"khatarna(k|kh)",
    r"durghatana",
    r"samasya",
    r"gambhir",
    r"dukha",
    r"jhanjhat",
    r"hairan",
    r"banaideu",
    r"banau(nu|nus|nuhos)",
    r"banaunu paryo",
    r"garnu paryo",
    r"kahile (banch|banaun|banaune|thik)",
    r"thik (gara|garnu|pardeu)",
]

# Devanagari has no \b in Python's re (combining marks are \w-less), so these
# are matched as plain substrings.
_DEVANAGARI = [
    "चाँडै",
    "चाडै",
    "छिटो",
    "तुरुन्त",
    "जरुरी",
    "अत्यावश्यक",
    "आपतकालीन",
    "खतरनाक",
    "दुर्घटना",
    "समस्या",
    "गम्भीर",
    "दुःख",
    "दुख",
    "झन्झट",
    "हैरान",
    "बनाइदिनुहोस्",
    "बनाउनुहोस्",
    "बनाउनुपर्‍यो",
    "बनाउनु पर्‍यो",
    "मर्मत गर्नुहोस्",
    "सफा गर्नुहोस्",
    "ठीक गर्नुहोस्",
    "कहिले बन्छ",
    "कहिले बनाउने",
    "अझै बनेको छैन",
]

_LATIN_PATTERN = re.compile(
    r"\b(" + "|".join(_ENGLISH + _ROMANISED_NEPALI) + r")\b",
    re.IGNORECASE,
)


def urgency_phrases(text: str) -> list[str]:
    """Every pressing phrase found in `text`, in the order they appear."""
    if not text:
        return []

    found = [m.group(0).lower() for m in _LATIN_PATTERN.finditer(text)]
    found += [phrase for phrase in _DEVANAGARI if phrase in text]
    return found


def is_urgent(text: str) -> bool:
    """Whether this comment asks for a fix, complains, or says it is urgent."""
    return bool(urgency_phrases(text))
