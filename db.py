"""
db.py — Database layer for AeroDesk
Aligned with current schema.sql and .env variable names.
"""

import os
import random
import string
from pathlib import Path

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / '.env')


# ── Connection ────────────────────────────────────────────────────────────────

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "airline_support"),
            autocommit=False,
        )
        return conn
    except Error as e:
        print(f"[DB] Connection error: {e}")
        return None


def _row_to_dict(cursor, row):
    return {col[0]: val for col, val in zip(cursor.description, row)}


def _generate_pnr(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Search flights ────────────────────────────────────────────────────────────

def search_flights(origin: str = None, destination: str = None) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        cursor = conn.cursor()
        conditions = []
        params = []

        if origin:
            conditions.append("LOWER(origin) LIKE %s")
            params.append(f"%{origin.lower()}%")
        if destination:
            conditions.append("LOWER(destination) LIKE %s")
            params.append(f"%{destination.lower()}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
            SELECT id, flight_number, origin, destination,
                   departure_time, arrival_time,
                   total_seats, available_seats, price, status
            FROM flights
            {where}
            ORDER BY departure_time
            LIMIT 10
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        flights = []
        for row in rows:
            d = _row_to_dict(cursor, row)
            d["departure_time"] = str(d["departure_time"])
            d["arrival_time"]   = str(d["arrival_time"])
            d["price"]          = round(float(d["price"]) * 83.5, 2)
            flights.append(d)

        return {"flights": flights, "count": len(flights)}

    except Error as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Get booking details ───────────────────────────────────────────────────────

def get_booking_details(pnr: str, last_name: str = None) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                b.id          AS booking_id,
                b.pnr,
                b.seat_number,
                b.booking_status,
                b.created_at  AS booked_on,
                u.name        AS passenger_name,
                u.email,
                f.flight_number,
                f.origin,
                f.destination,
                f.departure_time,
                f.arrival_time,
                f.price,
                f.status      AS flight_status
            FROM bookings b
            JOIN users   u ON u.id = b.user_id
            JOIN flights f ON f.id = b.flight_id
            WHERE b.pnr = %s
        """, (pnr.upper(),))

        row = cursor.fetchone()
        if not row:
            return {"error": f"No booking found for PNR {pnr.upper()}"}

        booking = _row_to_dict(cursor, row)

        if last_name:
            passenger_last = booking["passenger_name"].split()[-1].lower()
            if passenger_last != last_name.strip().lower():
                return {"error": "Last name does not match booking record"}

        booking["departure_time"] = str(booking["departure_time"])
        booking["arrival_time"]   = str(booking["arrival_time"])
        booking["booked_on"]      = str(booking["booked_on"])
        booking["price"]          = round(float(booking["price"]) * 83.5, 2)

        return {"booking": booking}

    except Error as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Create booking ────────────────────────────────────────────────────────────

def create_booking(user_id: int, flight_id: int, seat_number: str = None) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        pnr = _generate_pnr()
        cursor = conn.cursor()
        args = [user_id, flight_id, pnr, seat_number or "", ""]
        result_args = cursor.callproc("create_booking", args)
        conn.commit()

        p_result = result_args[4] if result_args else ""
        if p_result and p_result.startswith("ERROR"):
            return {"error": p_result.replace("ERROR: ", "")}

        return {"success": True, "pnr": pnr, "message": f"Booking confirmed! Your PNR is {pnr}."}

    except Error as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Cancel booking ────────────────────────────────────────────────────────────

def cancel_booking(pnr: str) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        cursor = conn.cursor()
        args = [pnr.upper(), ""]
        result_args = cursor.callproc("cancel_booking", args)
        conn.commit()

        p_result = result_args[1] if result_args else ""
        if p_result and p_result.startswith("ERROR"):
            return {"error": p_result.replace("ERROR: ", "")}

        return {"success": True, "message": f"Booking {pnr.upper()} has been cancelled successfully."}

    except Error as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Update seat ───────────────────────────────────────────────────────────────

def update_seat(pnr: str, new_seat: str) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, booking_status FROM bookings WHERE pnr = %s FOR UPDATE",
            (pnr.upper(),)
        )
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return {"error": f"No booking found for PNR {pnr.upper()}"}

        booking_id, status = row
        if status == "Cancelled":
            conn.rollback()
            return {"error": "Cannot change seat on a cancelled booking"}
        if status == "Checked-in":
            conn.rollback()
            return {"error": "Cannot change seat after check-in"}

        cursor.execute(
            "UPDATE bookings SET seat_number = %s WHERE id = %s",
            (new_seat.upper(), booking_id)
        )
        conn.commit()
        return {"success": True, "message": f"Seat updated to {new_seat.upper()} for PNR {pnr.upper()}."}

    except Error as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Create support ticket ─────────────────────────────────────────────────────

def create_ticket(pnr: str, issue: str, priority: str = "Medium") -> dict:
    if priority not in {"Low", "Medium", "High", "Urgent"}:
        priority = "Medium"

    conn = get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, booking_status FROM bookings WHERE pnr = %s",
            (pnr.upper(),)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"No booking found for PNR {pnr.upper()}"}

        booking_id, booking_status = row
        if booking_status == "Cancelled":
            return {"error": "Cannot raise a ticket on a cancelled booking"}

        cursor.execute(
            """
            INSERT INTO tickets (booking_id, issue_description, ticket_status, priority)
            VALUES (%s, %s, 'Open', %s)
            """,
            (booking_id, issue, priority)
        )
        ticket_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": "Your ticket has been raised. Our team will contact you shortly."
        }

    except Error as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ── Action log ────────────────────────────────────────────────────────────────

def log_action(action: str, details: str = "", user_id: int = None, ip_address: str = None) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, action[:100], details[:500] if details else None, ip_address)
        )
        conn.commit()
    except Error:
        pass
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass