"""
intent_handler.py - Rule-based intent detection for Sprint 1
Maps natural language user input to structured backend actions without any LLM.

Intent taxonomy:
  - search_flights   : find flights between cities
  - get_booking      : retrieve booking details by PNR
  - cancel_booking   : cancel an existing booking
  - change_seat      : update seat assignment
  - create_ticket    : raise a support ticket
  - help             : show available commands
  - unknown          : fallback
"""

import re
from typing import Dict, Any


# ─────────────────────────────────────────────
# Keyword / Pattern Maps
# ─────────────────────────────────────────────

INTENT_PATTERNS = [
    # search_flights
    {
        "intent": "search_flights",
        "triggers": [
            r"\b(search|find|show|list|available|look\s*up)\b.*(flight|fly|ticket)",
            r"\bflight(s)?\b.*(from|to|between)",
            r"\b(from|between)\b.*\bto\b",
            r"\bwhat flights?\b",
        ]
    },
    # cancel_booking
    {
        "intent": "cancel_booking",
        "triggers": [
            r"\b(cancel|cancellation|void|refund|annul)\b",
        ]
    },
    # change_seat
    {
        "intent": "change_seat",
        "triggers": [
            r"\b(change|switch|update|move|upgrade|modify)\b.*(seat|row)",
            r"\bseat\b.*(change|update|switch|move)",
            r"\bnew seat\b",
        ]
    },
    # create_ticket
    {
        "intent": "create_ticket",
        "triggers": [
            r"\b(create|open|raise|file|submit|log)\b.*(ticket|issue|complaint|problem|report)",
            r"\bsupport\b.*(ticket|request)",
            r"\b(issue|complaint|problem|trouble)\b",
            r"\bnot working\b",
        ]
    },
    # get_booking — check after cancel/change to avoid false positives
    {
        "intent": "get_booking",
        "triggers": [
            r"\b(check|get|show|retrieve|view|lookup|status|details?|info)\b.*(booking|reservation|pnr)",
            r"\bmy booking\b",
            r"\bpnr\b",
            r"\bbooking\s+(number|id|ref|status)\b",
        ]
    },
    # help
    {
        "intent": "help",
        "triggers": [
            r"\bhelp\b",
            r"\bwhat can you do\b",
            r"\bcommands?\b",
            r"\bhow (do|can|to)\b",
            r"^\s*(hi|hello|hey|howdy|greetings)\s*[.!?]?\s*$",
        ]
    },
]

# ─────────────────────────────────────────────
# Extraction Helpers
# ─────────────────────────────────────────────

PNR_PATTERN = re.compile(r'\b([A-Z]{2,3}[0-9]{3,4}|[A-Z0-9]{5,7})\b')
SEAT_PATTERN = re.compile(r'\b([1-9][0-9]?[A-F])\b', re.IGNORECASE)


def _extract_pnr(text: str) -> str | None:
    """Extract a PNR-looking string from the text."""
    # Explicit label
    labeled = re.search(r'\b(?:pnr|booking|ref(?:erence)?)\s*[:#]?\s*([A-Z0-9]{5,10})\b', text, re.IGNORECASE)
    if labeled:
        return labeled.group(1).upper()
    # Fallback: bare alphanumeric string
    matches = PNR_PATTERN.findall(text.upper())
    return matches[0] if matches else None


def _extract_seat(text: str) -> str | None:
    """Extract a seat number like 14B from text."""
    match = SEAT_PATTERN.search(text)
    return match.group(1).upper() if match else None


def _extract_origin_destination(text: str):
    """Try to pull origin/destination city names from the text."""
    # Pattern: "from X to Y" or "X to Y" or "between X and Y"
    between = re.search(r'\bbetween\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\b|$)', text, re.IGNORECASE)
    if between:
        return between.group(1).strip(), between.group(2).strip()

    from_to = re.search(r'\bfrom\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\b|$|\?)', text, re.IGNORECASE)
    if from_to:
        return from_to.group(1).strip(), from_to.group(2).strip()

    # Only destination
    to_only = re.search(r'\bto\s+([A-Za-z\s]{3,30})(?:\b|$)', text, re.IGNORECASE)
    if to_only:
        return None, to_only.group(1).strip()

    return None, None


def _extract_last_name(text: str) -> str | None:
    """Attempt to extract a passenger last name from text (naive heuristic)."""
    match = re.search(r'\b(?:last\s*name|surname|name)\s+(?:is\s+)?([A-Za-z]+)', text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_issue(text: str, intent_phrase_removed: str = None) -> str:
    """Extract issue description — remove common command prefixes."""
    prefixes = [
        r'^(create|open|raise|file|submit|log)\s+(a\s+)?(support\s+)?(ticket|issue|complaint|report)\s*(for|about|regarding)?\s*',
        r'^i\s+(have|am\s+having|am\s+experiencing|found)\s+an?\s+(issue|problem|complaint)\s*(with|about|regarding)?\s*',
    ]
    cleaned = text
    for p in prefixes:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned if len(cleaned) > 5 else text


# ─────────────────────────────────────────────
# Main Intent Detection
# ─────────────────────────────────────────────

def detect_intent(user_input: str) -> Dict[str, Any]:
    """
    Detect the intent of a user message and extract relevant entities.

    Returns a dict with:
      - intent: str
      - entities: dict of extracted params
      - confidence: 'high' | 'low'
      - raw: original input
    """
    text = user_input.strip()
    text_lower = text.lower()

    detected_intent = "unknown"
    confidence = "low"

    for pattern_set in INTENT_PATTERNS:
        for pattern in pattern_set["triggers"]:
            if re.search(pattern, text_lower):
                detected_intent = pattern_set["intent"]
                confidence = "high"
                break
        if confidence == "high":
            break

    # Entity extraction
    entities: Dict[str, Any] = {}

    pnr = _extract_pnr(text)
    if pnr:
        entities["pnr"] = pnr

    if detected_intent == "search_flights":
        origin, destination = _extract_origin_destination(text)
        if origin:
            entities["origin"] = origin
        if destination:
            entities["destination"] = destination

    if detected_intent == "change_seat":
        seat = _extract_seat(text)
        if seat:
            entities["new_seat"] = seat

    if detected_intent in ("get_booking", "cancel_booking"):
        last_name = _extract_last_name(text)
        if last_name:
            entities["last_name"] = last_name

    if detected_intent == "create_ticket":
        entities["issue"] = _extract_issue(text)
        # Priority detection
        if any(w in text_lower for w in ("urgent", "emergency", "asap", "immediately")):
            entities["priority"] = "Urgent"
        elif any(w in text_lower for w in ("high", "serious", "important")):
            entities["priority"] = "High"
        else:
            entities["priority"] = "Medium"

    return {
        "intent": detected_intent,
        "entities": entities,
        "confidence": confidence,
        "raw": text
    }


# ─────────────────────────────────────────────
# Response Formatter
# ─────────────────────────────────────────────

def missing_entity_prompt(intent: str, missing: str) -> str:
    """Generate a helpful prompt for a missing required entity."""
    prompts = {
        ("get_booking", "pnr"): "Please provide your PNR (booking reference number) to look up your booking. Example: 'ABC123'",
        ("cancel_booking", "pnr"): "To cancel your booking, please provide your PNR number. Example: 'Cancel booking ABC123'",
        ("change_seat", "pnr"): "Please provide your PNR number to change your seat.",
        ("change_seat", "new_seat"): "Please specify the seat number you'd like to move to. Example: '14B' or '22A'",
        ("create_ticket", "pnr"): "Please provide your PNR number so we can link the ticket to your booking.",
        ("search_flights", "origin"): "Please specify your departure city. Example: 'flights from New York to London'",
        ("search_flights", "destination"): "Please specify your destination city. Example: 'flights to London'",
    }
    return prompts.get((intent, missing), f"Could you provide your {missing}?")