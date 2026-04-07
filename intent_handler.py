"""
intent_handler.py — Lightweight intent detection for AeroDesk.
No external NLP library needed; pure regex + keyword matching.

Supported intents:
  search_flights  → entities: origin, destination
  get_booking     → entities: pnr, last_name
  cancel_booking  → entities: pnr
  change_seat     → entities: pnr, new_seat
  create_ticket   → entities: pnr, issue, priority
  help
  unknown
"""

import re

_PNR_RE  = re.compile(r'\b([A-Z0-9]{6})\b', re.IGNORECASE)
_SEAT_RE = re.compile(r'\b(\d{1,2}[A-HJ-Z])\b', re.IGNORECASE)

_PRIORITY_MAP = {
    "urgent": "Urgent",
    "high":   "High",
    "medium": "Medium",
    "low":    "Low",
}

_CITY_ALIASES = {
    "mumbai": "Mumbai", "bom": "Mumbai", "bombay": "Mumbai",
    "delhi": "Delhi", "del": "Delhi", "new delhi": "Delhi",
    "bangalore": "Bangalore", "bengaluru": "Bangalore", "blr": "Bangalore",
    "chennai": "Chennai", "maa": "Chennai", "madras": "Chennai",
    "hyderabad": "Hyderabad", "hyd": "Hyderabad",
    "kolkata": "Kolkata", "ccu": "Kolkata", "calcutta": "Kolkata",
    "goa": "Goa", "goi": "Goa",
    "kochi": "Kochi", "cok": "Kochi", "cochin": "Kochi",
    "pune": "Pune", "pnq": "Pune",
    "ahmedabad": "Ahmedabad", "amd": "Ahmedabad",
    "london": "London", "lhr": "London",
    "dubai": "Dubai", "dxb": "Dubai",
    "singapore": "Singapore", "sin": "Singapore",
    "san francisco": "San Francisco", "sfo": "San Francisco",
    "bangkok": "Bangkok", "bkk": "Bangkok",
    "new york": "New York", "jfk": "New York", "nyc": "New York",
    "paris": "Paris", "cdg": "Paris",
    "chicago": "Chicago", "ord": "Chicago",
    "los angeles": "Los Angeles", "lax": "Los Angeles",
    "miami": "Miami", "mia": "Miami",
}


def _extract_pnr(text: str) -> str | None:
    stopwords = {"flight", "ticket", "please", "booking", "cancel", "search",
                 "change", "update", "raise", "create", "medium", "urgent"}
    for m in _PNR_RE.finditer(text):
        token = m.group(1).upper()
        if token.lower() not in stopwords:
            return token
    return None


def _extract_seat(text: str) -> str | None:
    m = _SEAT_RE.search(text)
    return m.group(1).upper() if m else None


def _extract_priority(text: str) -> str:
    text_lower = text.lower()
    for kw, label in _PRIORITY_MAP.items():
        if kw in text_lower:
            return label
    return "Medium"


def _find_city_in_text(text: str) -> str | None:
    for alias in sorted(_CITY_ALIASES, key=len, reverse=True):
        if alias in text.lower():
            return _CITY_ALIASES[alias]
    return None


def _extract_origin_destination(text: str):
    text_lower = text.lower()

    from_to = re.search(
        r'from\s+([a-z\s\(\)]+?)\s+to\s+([a-z\s\(\)]+?)(?:\s|$|,|\.|on|at)',
        text_lower
    )
    if from_to:
        origin = _CITY_ALIASES.get(from_to.group(1).strip()) or _find_city_in_text(from_to.group(1).strip())
        dest   = _CITY_ALIASES.get(from_to.group(2).strip()) or _find_city_in_text(from_to.group(2).strip())
        return origin, dest

    to_only = re.search(r'to\s+([a-z\s]+?)(?:\s|$|,|\.)', text_lower)
    if to_only:
        dest = _CITY_ALIASES.get(to_only.group(1).strip()) or _find_city_in_text(to_only.group(1).strip())
        return None, dest

    city = _find_city_in_text(text)
    return None, city


_SEARCH_KW  = {"search", "find", "show", "list", "flights", "available", "fly", "flying", "route", "routes"}
_BOOKING_KW = {"booking", "bookings", "reservation", "check", "my booking", "pnr", "show booking",
               "retrieve", "look up", "details", "what's my", "view my"}
_CANCEL_KW  = {"cancel", "cancellation", "cancelled", "refund"}
_SEAT_KW    = {"seat", "seats", "change seat", "update seat", "new seat", "move seat",
               "switch seat", "reassign", "upgrade seat"}
_TICKET_KW  = {"ticket", "issue", "problem", "complaint", "support", "raise", "report",
               "help with", "assistance"}
_HELP_KW    = {"help", "what can you do", "options", "menu", "commands", "how do i",
               "what do you do", "hi", "hello", "hey"}


def _keyword_score(text_lower: str, kw_set: set) -> int:
    return sum(1 for kw in kw_set if kw in text_lower)


def detect_intent(user_message: str) -> dict:
    msg   = user_message.strip()
    lower = msg.lower()

    scores = {
        "search_flights": _keyword_score(lower, _SEARCH_KW),
        "get_booking":    _keyword_score(lower, _BOOKING_KW),
        "cancel_booking": _keyword_score(lower, _CANCEL_KW),
        "change_seat":    _keyword_score(lower, _SEAT_KW),
        "create_ticket":  _keyword_score(lower, _TICKET_KW),
        "help":           _keyword_score(lower, _HELP_KW),
    }

    if "cancel" in lower:
        scores["cancel_booking"] += 5
    if re.search(r'\bseat\b', lower) and any(w in lower for w in ("change", "update", "move", "new")):
        scores["change_seat"] += 5
    if re.search(r'\b(ticket|issue|problem|complaint)\b', lower) and "raise" in lower:
        scores["create_ticket"] += 5
    if re.search(r'\b(flight|fly|flying)\b', lower) and re.search(r'\b(from|to|between)\b', lower):
        scores["search_flights"] += 5
    if re.search(r'\b(my booking|pnr|reservation)\b', lower):
        scores["get_booking"] += 4

    best_intent = max(scores, key=lambda k: scores[k])
    best_score  = scores[best_intent]

    if best_score == 0:
        return {"intent": "unknown", "entities": {}}

    entities: dict = {}

    if best_intent == "search_flights":
        origin, destination = _extract_origin_destination(msg)
        if origin:
            entities["origin"] = origin
        if destination:
            entities["destination"] = destination

    elif best_intent in ("get_booking", "cancel_booking", "change_seat", "create_ticket"):
        pnr = _extract_pnr(msg)
        if pnr:
            entities["pnr"] = pnr

        if best_intent == "get_booking":
            last_name_match = re.search(
                r'(?:last\s*name|surname|name)\s+(?:is\s+)?([A-Za-z]+)', msg, re.IGNORECASE
            )
            if last_name_match:
                entities["last_name"] = last_name_match.group(1)

        elif best_intent == "change_seat":
            seat = _extract_seat(msg)
            if seat:
                entities["new_seat"] = seat

        elif best_intent == "create_ticket":
            entities["priority"] = _extract_priority(msg)
            entities["issue"]    = msg

    return {"intent": best_intent, "entities": entities}


# ── Clarification prompts ─────────────────────────────────────────────────────

_CLARIFICATION_PROMPTS = {
    ("search_flights", "destination"): (
        "🔍 **Search Flights**\n\n"
        "Please tell me where you'd like to fly.\n"
    ),
    ("get_booking", "pnr"): (
        "📋 **Check Booking**\n\n"
        "Please provide your **PNR number** (6-character booking reference)."
    ),
    ("cancel_booking", "pnr"): (
        "❌ **Cancel Booking**\n\n"
        "Please provide your **PNR number** to proceed with cancellation."
    ),
    ("change_seat", "pnr"): (
        "💺 **Change Seat**\n\n"
        "Please provide your **PNR number** and the new seat you'd like."
    ),
    ("change_seat", "new_seat"): (
        "💺 **Change Seat**\n\n"
        "I have your PNR. Which seat number would you like?"
    ),
    ("create_ticket", "pnr"): (
        "🎫 **Raise Support Ticket**\n\n"
        "Please provide your **PNR number** and describe the issue."
    ),
}

_DEFAULT_CLARIFICATION = "I need a bit more information to help you. Could you please provide more details?"


def missing_entity_prompt(intent: str, entity: str) -> str:
    return _CLARIFICATION_PROMPTS.get((intent, entity), _DEFAULT_CLARIFICATION)