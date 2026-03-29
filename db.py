"""
db.py - Database operations layer for Sprint 1
Handles all MySQL interactions with proper error handling and transactions.
"""

import mysql.connector
from mysql.connector import Error
import os
import random
import string
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def get_db_connection():
    """Establish and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE", "airline_support")
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[DB ERROR] Connection failed: {e}")
        return None


def _generate_pnr():
    """Generate a unique 6-character alphanumeric PNR."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ─────────────────────────────────────────────
# FLIGHT OPERATIONS
# ─────────────────────────────────────────────

def search_flights(origin: str = None, destination: str = None):
    """
    Search flights by origin and/or destination (partial, case-insensitive match).
    Returns list of matching flights with availability info.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        # Build base query — all non-cancelled flights
        query = """
            SELECT 
                id, flight_number, origin, destination,
                DATE_FORMAT(departure_time, '%Y-%m-%d %H:%i') AS departure_time,
                DATE_FORMAT(arrival_time, '%Y-%m-%d %H:%i') AS arrival_time,
                total_seats, available_seats, price, status
            FROM flights
            WHERE status != 'Cancelled'
        """
        params = []

        # Use LIKE with % wildcards on both sides for flexible partial matching.
        # e.g. "New York", "York", or "JFK" all match "New York (JFK)".
        if origin:
            query += " AND LOWER(origin) LIKE LOWER(%s)"
            params.append("%" + origin.strip() + "%")
        if destination:
            query += " AND LOWER(destination) LIKE LOWER(%s)"
            params.append("%" + destination.strip() + "%")

        query += " ORDER BY departure_time ASC"
        cursor.execute(query, params)
        flights = cursor.fetchall()

        if not flights:
            return {"error": "No flights found matching your criteria"}

        # Convert Decimal to float for JSON serialization
        for f in flights:
            f['price'] = float(f['price'])

        return {"flights": flights, "count": len(flights)}

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


# ─────────────────────────────────────────────
# BOOKING OPERATIONS
# ─────────────────────────────────────────────

def get_booking_details(pnr: str, last_name: str = None):
    """Retrieve full booking details by PNR, optionally validating passenger last name."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                b.id AS booking_id, b.pnr, b.seat_number, b.booking_status,
                DATE_FORMAT(b.created_at, '%Y-%m-%d %H:%i') AS booked_on,
                u.name AS passenger_name, u.email, u.phone,
                f.flight_number, f.origin, f.destination,
                DATE_FORMAT(f.departure_time, '%Y-%m-%d %H:%i') AS departure_time,
                DATE_FORMAT(f.arrival_time, '%Y-%m-%d %H:%i') AS arrival_time,
                f.status AS flight_status, f.price
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN flights f ON b.flight_id = f.id
            WHERE b.pnr = %s
        """
        cursor.execute(query, (pnr.upper(),))
        booking = cursor.fetchone()

        if not booking:
            return {"error": f"No booking found for PNR '{pnr}'"}

        if last_name and last_name.lower() not in booking['passenger_name'].lower():
            return {"error": "Passenger last name does not match booking records"}

        booking['price'] = float(booking['price'])
        return {"booking": booking}

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


def create_booking(user_id: int, flight_id: int, seat_number: str = None):
    """
    Create a new booking using the stored procedure for atomic seat decrement.
    Returns the new booking details or an error.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor()

        # Generate a unique PNR
        pnr = _generate_pnr()

        cursor.callproc('create_booking', [user_id, flight_id, pnr, seat_number, ''])
        
        # Retrieve OUT parameter
        cursor.execute("SELECT @_create_booking_4")
        result_row = cursor.fetchone()
        proc_result = result_row[0] if result_row else 'ERROR: Unknown'

        if proc_result.startswith('ERROR'):
            return {"error": proc_result.replace('ERROR: ', '')}

        # Fetch new booking details
        return get_booking_details(pnr)

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


def cancel_booking(pnr: str):
    """
    Cancel a booking by PNR. Restores seat count atomically.
    Returns success or descriptive error.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.callproc('cancel_booking', [pnr.upper(), ''])

        cursor.execute("SELECT @_cancel_booking_1")
        result_row = cursor.fetchone()
        proc_result = result_row[0] if result_row else 'ERROR: Unknown'

        if proc_result.startswith('ERROR'):
            return {"error": proc_result.replace('ERROR: ', '')}

        return {
            "success": True,
            "message": f"Booking {pnr.upper()} has been cancelled successfully. Refund will be processed within 5-7 business days."
        }

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


def update_seat(pnr: str, new_seat: str):
    """Update seat number for an existing confirmed booking."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)

        # Validate booking exists and is cancellable
        cursor.execute(
            "SELECT id, booking_status FROM bookings WHERE pnr = %s",
            (pnr.upper(),)
        )
        booking = cursor.fetchone()

        if not booking:
            return {"error": f"No booking found for PNR '{pnr}'"}
        if booking['booking_status'] == 'Cancelled':
            return {"error": "Cannot change seat on a cancelled booking"}
        if booking['booking_status'] == 'Checked-in':
            return {"error": "Cannot change seat after check-in"}

        cursor.execute(
            "UPDATE bookings SET seat_number = %s WHERE pnr = %s",
            (new_seat, pnr.upper())
        )
        conn.commit()

        if cursor.rowcount == 0:
            return {"error": "Seat update failed"}

        return {
            "success": True,
            "message": f"Seat successfully updated to {new_seat} for PNR {pnr.upper()}"
        }

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


# ─────────────────────────────────────────────
# TICKET OPERATIONS
# ─────────────────────────────────────────────

def create_ticket(pnr: str, issue: str, priority: str = "Medium"):
    """Create a support ticket for a booking."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = None
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM bookings WHERE pnr = %s", (pnr.upper(),))
        booking = cursor.fetchone()

        if not booking:
            return {"error": f"No booking found for PNR '{pnr}'"}

        booking_id = booking[0]
        valid_priorities = ('Low', 'Medium', 'High', 'Urgent')
        if priority not in valid_priorities:
            priority = 'Medium'

        cursor.execute(
            "INSERT INTO tickets (booking_id, issue_description, priority) VALUES (%s, %s, %s)",
            (booking_id, issue, priority)
        )
        conn.commit()
        ticket_id = cursor.lastrowid

        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Support ticket #{ticket_id} created successfully. Our team will respond within 24 hours."
        }

    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()


def log_action(action: str, details: str = None, user_id: int = None, ip_address: str = None):
    """Log an action to the database."""
    conn = get_db_connection()
    if not conn:
        return

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, action, details, ip_address)
        )
        conn.commit()
    except Error as e:
        print(f"[WARN] Failed to log action: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()