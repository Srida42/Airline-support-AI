from db import get_db_connection

try:
    conn = get_db_connection()
    print("SUCCESS! Connected to MySQL.")
    conn.close()
except Exception as e:
    print("ERROR:", e)
