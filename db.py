import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def get_booking_details(pnr, last_name=None):
    connection = get_db_connection()
    if not connection:
        return {"error": "Database connection failed"}
    
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT b.pnr, u.name, f.flight_number, f.origin, f.destination, f.departure_time, b.seat_number, b.status
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN flights f ON b.flight_id = f.id
            WHERE b.pnr = %s
        """
        cursor.execute(query, (pnr,))
        booking = cursor.fetchone()
        
        if not booking:
            return {"error": "Booking not found"}
        
        # Simple name check if provided
        if last_name and last_name.lower() not in booking['name'].lower():
             return {"error": "Passenger name mismatch"}
             
        return booking
    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def update_seat(pnr, new_seat):
    connection = get_db_connection()
    if not connection:
        return {"error": "Database connection failed"}
    
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE bookings SET seat_number = %s WHERE pnr = %s"
        cursor.execute(query, (new_seat, pnr))
        connection.commit()
        
        if cursor.rowcount == 0:
            return {"error": "Booking not found or seat not updated"}
            
        return {"success": True, "message": f"Seat updated to {new_seat} for PNR {pnr}"}
    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def create_ticket(pnr, issue):
    connection = get_db_connection()
    if not connection:
        return {"error": "Database connection failed"}
    
    cursor = None
    try:
        cursor = connection.cursor()
        # Find booking id
        cursor.execute("SELECT id FROM bookings WHERE pnr = %s", (pnr,))
        booking = cursor.fetchone()
        
        if not booking:
            return {"error": "Booking not found"}
        
        booking_id = booking[0]
        
        query = "INSERT INTO tickets (booking_id, issue_description) VALUES (%s, %s)"
        cursor.execute(query, (booking_id, issue))
        connection.commit()
        
        ticket_id = cursor.lastrowid
        return {"success": True, "message": f"Support ticket created with ID {ticket_id}"}
    except Error as e:
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def log_action(user_id, action):
    connection = get_db_connection()
    if not connection:
        return
    
    cursor = None
    try:
        cursor = connection.cursor()
        query = "INSERT INTO logs (user_id, action) VALUES (%s, %s)"
        cursor.execute(query, (user_id, action))
        connection.commit()
    except Error as e:
        print(f"Error logging action: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()
