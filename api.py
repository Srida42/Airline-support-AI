"""
api.py - Sprint 2 REST API backend
All quick actions + Gemini conversational fallback.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

from db import (
    search_flights,
    get_booking_details,
    create_booking,
    cancel_booking,
    update_seat,
    create_ticket,
    log_action,
    get_db_connection,
)
from intent_handler import detect_intent, missing_entity_prompt

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── Gemini client (conversational fallback) ───────────────────────────────────
_gemini_key = os.getenv("GEMINI_API_KEY", "")
ai_client = genai.Client(api_key=_gemini_key) if _gemini_key else None


def _ai_fallback(user_message: str, image_b64: str = None, image_type: str = "image/jpeg") -> str:
    """Call Gemini for general conversation, optionally with an image."""
    if not ai_client:
        return (
            "I can help you with flight searches, booking lookups, cancellations, "
            "seat changes, and support tickets. Type **help** to see all options."
        )
    try:
        if image_b64:
            import base64
            image_bytes = base64.b64decode(image_b64)
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=image_type),
                types.Part.from_text(text=(
                    user_message or
                    "This appears to be a boarding pass or travel document. "
                    "Please extract: PNR/booking reference, passenger name, flight number, "
                    "origin, destination, date, and seat number if visible. "
                    "Format clearly so I can look up the booking."
                ))
            ]
        else:
            contents = user_message

        resp = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are AeroDesk, a friendly airline support assistant. "
                    "When given a boarding pass image, extract all travel details clearly. "
                    "Keep replies concise and helpful. Never make up flight or booking data."
                ),
                max_output_tokens=500,
            )
        )
        return resp.text.strip()
    except Exception as e:
        return f"AI unavailable right now. Type **help** to see what I can do. ({e})"


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    conn = get_db_connection()
    db_ok = conn is not None
    if conn and conn.is_connected():
        conn.close()
    return jsonify({
        "status": "ok",
        "database": "connected" if db_ok else "disconnected",
        "ai": "connected" if ai_client else "no key",
        "sprint": 2
    })


# ── REST endpoints ─────────────────────────────────────────────────────────────
@app.route("/api/flights/search", methods=["GET"])
def api_search_flights():
    origin = request.args.get("origin", "").strip() or None
    destination = request.args.get("destination", "").strip() or None
    if not origin and not destination:
        return jsonify({"error": "Provide at least one of: origin, destination"}), 400
    result = search_flights(origin=origin, destination=destination)
    if "error" in result:
        return jsonify(result), 404
    log_action("search_flights", f"origin={origin}, destination={destination}")
    return jsonify(result)


@app.route("/api/bookings/<pnr>", methods=["GET"])
def api_get_booking(pnr: str):
    last_name = request.args.get("last_name", "").strip() or None
    result = get_booking_details(pnr=pnr, last_name=last_name)
    if "error" in result:
        return jsonify(result), 404
    log_action("get_booking", f"pnr={pnr}")
    return jsonify(result)


@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    user_id = data.get("user_id")
    flight_id = data.get("flight_id")
    seat_number = data.get("seat_number")
    if not user_id or not flight_id:
        return jsonify({"error": "user_id and flight_id are required"}), 400
    result = create_booking(user_id=int(user_id), flight_id=int(flight_id), seat_number=seat_number)
    if "error" in result:
        return jsonify(result), 409
    log_action("create_booking", f"user_id={user_id}, flight_id={flight_id}", user_id=int(user_id))
    return jsonify(result), 201


@app.route("/api/bookings/<pnr>/cancel", methods=["POST"])
def api_cancel_booking(pnr: str):
    result = cancel_booking(pnr=pnr)
    if "error" in result:
        return jsonify(result), 400
    log_action("cancel_booking", f"pnr={pnr}")
    return jsonify(result)


@app.route("/api/bookings/<pnr>/seat", methods=["PATCH"])
def api_update_seat(pnr: str):
    data = request.get_json()
    new_seat = data.get("new_seat", "").strip() if data else ""
    if not new_seat:
        return jsonify({"error": "new_seat is required"}), 400
    result = update_seat(pnr=pnr, new_seat=new_seat)
    if "error" in result:
        return jsonify(result), 400
    log_action("change_seat", f"pnr={pnr}, new_seat={new_seat}")
    return jsonify(result)


@app.route("/api/tickets", methods=["POST"])
def api_create_ticket():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    pnr = data.get("pnr", "").strip()
    issue = data.get("issue", "").strip()
    priority = data.get("priority", "Medium").strip()
    if not pnr or not issue:
        return jsonify({"error": "pnr and issue are required"}), 400
    result = create_ticket(pnr=pnr, issue=issue, priority=priority)
    if "error" in result:
        return jsonify(result), 400
    log_action("create_ticket", f"pnr={pnr}, ticket_id={result.get('ticket_id')}")
    return jsonify(result), 201


# ── Main chat endpoint ─────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "message is required"}), 400

    user_message = data["message"].strip()
    image_b64  = data.get("image_b64")
    image_type = data.get("image_type", "image/jpeg")

    # If image attached, always route to Gemini for extraction
    if image_b64:
        ai_response = _ai_fallback(user_message, image_b64=image_b64, image_type=image_type)
        log_action("image_upload", "boarding pass or image submitted")
        return jsonify({"intent": "get_booking", "response": ai_response, "data": None})

    intent_result = detect_intent(user_message)
    intent = intent_result["intent"]
    entities = intent_result["entities"]

    log_action("chat_intent", f"intent={intent}, entities={entities}")

    # ── Help ──────────────────────────────────────────────────────────────────
    if intent == "help":
        response_text = (
            "✈️ **Welcome to AeroDesk Support!**\n\n"
            "Here's what I can help you with:\n\n"
            "• **Search flights** — Find available flights between cities\n\n"
            "• **Check booking** — View your flight booking details\n\n"
            "• **Cancel booking** — Cancel an existing reservation\n\n"
            "• **Change seat** — Update your seat assignment\n\n"
            "• **Raise a ticket** — Report an issue with your booking\n\n"
            "Just type your request and I'll take care of the rest!"
        )
        return jsonify({"intent": intent, "response": response_text, "data": None})

    # ── Unknown → Gemini conversational fallback ──────────────────────────────
    if intent == "unknown":
        return jsonify({
            "intent": "unknown",
            "response": _ai_fallback(user_message),
            "data": None
        })



    # ── Search flights ────────────────────────────────────────────────────────
    if intent == "search_flights":
        origin = entities.get("origin")
        destination = entities.get("destination")

        if not origin and not destination:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "destination"),
                "data": None
            })

        result = search_flights(origin=origin, destination=destination)

        if "error" in result:
            return jsonify({"intent": intent, "response": f"❌ {result['error']}", "data": None})

        flights = result["flights"]
        lines = [f"🔍 **Found {result['count']} flight(s)**\n"]
        for f in flights:
            avail = f["available_seats"]
            avail_label = (
                "🔴 Full" if avail == 0
                else ("🟡 Almost full" if avail < 15 else f"🟢 {avail} seats left")
            )
            lines.append(
                f"**{f['flight_number']}** | {f['origin']} → {f['destination']}\n"
                f"   Departs: {f['departure_time']} | Price: ${float(f['price']):.2f} | {avail_label}"
            )
        return jsonify({"intent": intent, "response": "\n\n".join(lines), "data": result})

    # ── Get booking ───────────────────────────────────────────────────────────
    if intent == "get_booking":
        pnr = entities.get("pnr")
        if not pnr:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "pnr"),
                "data": None
            })

        result = get_booking_details(pnr=pnr, last_name=entities.get("last_name"))

        if "error" in result:
            return jsonify({"intent": intent, "response": f"❌ {result['error']}", "data": None})

        b = result["booking"]
        status_emoji = {
            "Confirmed": "✅", "Cancelled": "❌", "Checked-in": "🛫", "Pending": "⏳"
        }.get(b["booking_status"], "📌")

        response_text = (
            f"📋 **Booking Details — PNR {b['pnr']}**\n\n"
            f"👤 Passenger: {b['passenger_name']}\n"
            f"✈️ Flight: {b['flight_number']} | {b['origin']} → {b['destination']}\n"
            f"🕐 Departure: {b['departure_time']}\n"
            f"🛬 Arrival: {b['arrival_time']}\n"
            f"💺 Seat: {b['seat_number'] or 'Not assigned'}\n"
            f"{status_emoji} Status: {b['booking_status']}\n"
            f"💰 Price: ${float(b['price']):.2f}\n"
            f"🗓️ Booked on: {b['booked_on']}"
        )
        return jsonify({"intent": intent, "response": response_text, "data": result})

    # ── Cancel booking ────────────────────────────────────────────────────────
    if intent == "cancel_booking":
        pnr = entities.get("pnr")
        if not pnr:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "pnr"),
                "data": None
            })

        result = cancel_booking(pnr=pnr)

        if "error" in result:
            return jsonify({"intent": intent, "response": f"❌ {result['error']}", "data": None})

        return jsonify({
            "intent": intent,
            "response": f"✅ {result['message']}",
            "data": result
        })

    # ── Change seat ───────────────────────────────────────────────────────────
    if intent == "change_seat":
        pnr = entities.get("pnr")
        new_seat = entities.get("new_seat")

        if not pnr:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "pnr"),
                "data": None
            })
        if not new_seat:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "new_seat"),
                "data": None
            })

        result = update_seat(pnr=pnr, new_seat=new_seat)

        if "error" in result:
            return jsonify({"intent": intent, "response": f"❌ {result['error']}", "data": None})

        return jsonify({
            "intent": intent,
            "response": f"✅ {result['message']}",
            "data": result
        })

    # ── Create support ticket ─────────────────────────────────────────────────
    if intent == "create_ticket":
        pnr = entities.get("pnr")
        issue = entities.get("issue", user_message)
        priority = entities.get("priority", "Medium")

        if not pnr:
            return jsonify({
                "intent": intent,
                "response": missing_entity_prompt(intent, "pnr"),
                "data": None
            })

        result = create_ticket(pnr=pnr, issue=issue, priority=priority)

        if "error" in result:
            return jsonify({"intent": intent, "response": f"❌ {result['error']}", "data": None})

        priority_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Urgent": "🔴"}.get(priority, "🟡")
        return jsonify({
            "intent": intent,
            "response": (
                f"🎫 **Support Ticket #{result['ticket_id']} Created**\n\n"
                f"📝 Issue: {issue}\n"
                f"{priority_emoji} Priority: {priority}\n\n"
                f"{result['message']}"
            ),
            "data": result
        })

    # ── Safety net fallback ───────────────────────────────────────────────────
    return jsonify({
        "intent": intent,
        "response": _ai_fallback(user_message),
        "data": None
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    conn = get_db_connection()
    db_status = "✅" if conn else "❌"
    if conn and conn.is_connected():
        conn.close()
    print(f"🚀 AeroDesk API running on http://localhost:{port}")
    print(f"   Database : {db_status}")
    print(f"   Gemini   : {'✅' if ai_client else '❌ (no key)'}")
    app.run(host="0.0.0.0", port=port, debug=debug)