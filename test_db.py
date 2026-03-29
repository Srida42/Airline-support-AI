from db import get_db_connection
conn = get_db_connection()
if conn:
    print("✅ Connected successfully!")
    conn.close()
else:
    print("❌ Connection failed — check your .env credentials and MySQL status")