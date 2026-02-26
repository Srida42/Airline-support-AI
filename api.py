"""
api.py - Sprint 1 REST API backend
Exposes endpoints for flight search, booking operations, and the chat handler.
Run with: python api.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
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
CORS(app)  # Allow cross-origin requests from the frontend

# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    conn = get_db_connection()
    db_ok = conn is not None
    if conn and conn.is_connected():
        conn.close()
    return jsonify({
        "status": "ok",
        "database": "connected" if db_ok else "disconnected",
        "sprint": 1
    })


# ─────────────────────────────────────────────
# Flight Endpoints
# ─────────────────────────────────────────────

@app.route("/api/flights/search", methods=["GET"])
def api_search_flights():
    """
    GET /api/flights/search?origin=New+York&destination=London
    Returns matching flights with availability.
    """
    origin = request.args.get("origin", "").strip() or None
    destination = request.args.get("destination", "").strip() or None

    if not origin and not destination:
        return jsonify({"error": "Provide at least one of: origin, destination"}), 400

    result = search_flights(origin=origin, destination=destination)

    if "error" in result:
        return jsonify(result), 404

    log_action("search_flights", f"origin={origin}, destination={destination}")
    return jsonify(result)


# ─────────────────────────────────────────────
# Booking Endpoints
# ─────────────────────────────────────────────

@app.route("/api/bookings/<pnr>", methods=["GET"])
def api_get_booking(pnr: str):
    """GET /api/bookings/ABC123?last_name=Doe"""
    last_name = request.args.get("last_name", "").strip() or None
    result = get_booking_details(pnr=pnr, last_name=last_name)

    if "error" in result:
        return jsonify(result), 404

    log_action("get_booking", f"pnr={pnr}")
    return jsonify(result)


@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    """
    POST /api/bookings
    Body: { "user_id": 1, "flight_id": 2, "seat_number": "14A" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    user_id = data.get("user_id")
    flight_id = data.get("flight_id")
    seat_number = data.get("seat_number")

    if not user_id or not flight_id:
        return jsonify({"error": "user_id and flight_id are required"}), 400

    result = create_booking(
        user_id=int(user_id),
        flight_id=int(flight_id),
        seat_number=seat_number
    )

    if "error" in result:
        return jsonify(result), 409  # Conflict (e.g. no seats available)

    log_action("create_booking", f"user_id={user_id}, flight_id={flight_id}", user_id=int(user_id))
    return jsonify(result), 201


@app.route("/api/bookings/<pnr>/cancel", methods=["POST"])
def api_cancel_booking(pnr: str):
    """POST /api/bookings/ABC123/cancel"""
    result = cancel_booking(pnr=pnr)

    if "error" in result:
        return jsonify(result), 400

    log_action("cancel_booking", f"pnr={pnr}")
    return jsonify(result)


@app.route("/api/bookings/<pnr>/seat", methods=["PATCH"])
def api_update_seat(pnr: str):
    """
    PATCH /api/bookings/ABC123/seat
    Body: { "new_seat": "14B" }
    """
    data = request.get_json()
    new_seat = data.get("new_seat", "").strip() if data else ""

    if not new_seat:
        return jsonify({"error": "new_seat is required"}), 400

    result = update_seat(pnr=pnr, new_seat=new_seat)

    if "error" in result:
        return jsonify(result), 400

    log_action("change_seat", f"pnr={pnr}, new_seat={new_seat}")
    return jsonify(result)


# ─────────────────────────────────────────────
# Ticket Endpoint
# ─────────────────────────────────────────────

@app.route("/api/tickets", methods=["POST"])
def api_create_ticket():
    """
    POST /api/tickets
    Body: { "pnr": "ABC123", "issue": "...", "priority": "Medium" }
    """
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


# ─────────────────────────────────────────────
# Chat / Intent Handler Endpoint
# ─────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    POST /api/chat
    Body: { "message": "Cancel my booking ABC123" }

    Rule-based intent detection → routes to appropriate DB operation.
    No LLM involved in Sprint 1.
    """
    data = request.get_json()
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "message is required"}), 400

    user_message = data["message"].strip()
    intent_result = detect_intent(user_message)
    intent = intent_result["intent"]
    entities = intent_result["entities"]

    log_action("chat_intent", f"intent={intent}, entities={entities}")

    # ── help / greeting ──────────────────────────────────────
    if intent == "help":
        response_text = (
            "✈️ Welcome to Airline Support! Here's what I can help you with:\n\n"
            "• **Search flights** — e.g. 'Find flights from New York to London'\n"
            "• **Check booking** — e.g. 'Check booking ABC123'\n"
            "• **Cancel booking** — e.g. 'Cancel my booking ABC123'\n"
            "• **Change seat** — e.g. 'Change seat to 14B for ABC123'\n"
            "• **Create ticket** — e.g. 'I have an issue with my meal for ABC123'\n\n"
            "Just type your request and I'll take care of the rest!"
        )
        return jsonify({"intent": intent, "response": response_text, "data": None})

    # ── unknown ───────────────────────────────────────────────
    if intent == "unknown":
        return jsonify({
            "intent": intent,
            "response": (
                "I'm sorry, I didn't quite understand that. "
                "Type 'help' to see what I can assist you with."
            ),
            "data": None
        })

    # ── search_flights ────────────────────────────────────────
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
            return jsonify({"intent": intent, "response": result["error"], "data": None})

        flights = result["flights"]
        lines = [f"🔍 Found **{result['count']} flight(s)**:\n"]
        for f in flights:
            avail = f['available_seats']
            avail_label = "🔴 Full" if avail == 0 else ("🟡 Almost full" if avail < 15 else f"🟢 {avail} seats left")
            lines.append(
                f"**{f['flight_number']}** | {f['origin']} → {f['destination']}\n"
                f"   Departs: {f['departure_time']} | Price: ${f['price']:.2f} | {avail_label}"
            )
        return jsonify({"intent": intent, "response": "\n\n".join(lines), "data": result})

    # ── get_booking ───────────────────────────────────────────
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
        response_text = (
            f"📋 **Booking Details for PNR {b['pnr']}**\n\n"
            f"👤 Passenger: {b['passenger_name']}\n"
            f"✈️ Flight: {b['flight_number']} — {b['origin']} → {b['destination']}\n"
            f"🕐 Departure: {b['departure_time']}\n"
            f"💺 Seat: {b['seat_number'] or 'Not assigned'}\n"
            f"📌 Status: {b['booking_status']}\n"
            f"🔖 Booked on: {b['booked_on']}"
        )
        return jsonify({"intent": intent, "response": response_text, "data": result})

    # ── cancel_booking ────────────────────────────────────────
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

    # ── change_seat ───────────────────────────────────────────
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

    # ── create_ticket ─────────────────────────────────────────
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

        return jsonify({
            "intent": intent,
            "response": f"🎫 {result['message']}",
            "data": result
        })

    # Fallback
    return jsonify({
        "intent": intent,
        "response": "I understood your request but couldn't process it. Please try again.",
        "data": None
    })


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"🚀 Airline Support API running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)