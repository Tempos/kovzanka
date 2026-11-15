import os
import sqlite3
import pymysql
from dotenv import load_dotenv

load_dotenv()

def migrate_data():
    if not os.path.exists("ice_rink.db"):
        print("No local SQLite database found. Skipping migration.")
        return

    sqlite_conn = sqlite3.connect("ice_rink.db")
    sqlite_cursor = sqlite_conn.cursor()

    mysql_conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "kovzanka"),
        password=os.environ.get("MYSQL_PASSWORD", "secret"),
        database=os.environ.get("MYSQL_DATABASE", "kovzanka_db"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        charset="utf8mb4"
    )
    mysql_cursor = mysql_conn.cursor()

    # Migrate skate_inventory
    sqlite_cursor.execute("SELECT size, total_stock, maintenance_count, is_deleted FROM skate_inventory")
    for row in sqlite_cursor.fetchall():
        mysql_cursor.execute(
            "INSERT IGNORE INTO skate_inventory (size, total_stock, maintenance_count, is_deleted) VALUES (%s, %s, %s, %s)",
            row
        )

    # Migrate queue items
    sqlite_cursor.execute("""
        SELECT id, ticket_number, phone, people_count, shoe_sizes, duration_minutes, 
               status, comment, telegram_chat_id, tracking_token, session_start, session_end, created_at, called_at, overtime_stopped_at
        FROM queue_items
    """)
    for row in sqlite_cursor.fetchall():
        mysql_cursor.execute("""
            INSERT IGNORE INTO queue_items 
            (id, ticket_number, phone, people_count, shoe_sizes, duration_minutes, 
             status, comment, telegram_chat_id, tracking_token, session_start, session_end, created_at, called_at, overtime_stopped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, row)

    mysql_conn.commit()
    sqlite_conn.close()
    mysql_conn.close()
    print("Successfully migrated SQLite data to MySQL.")

if __name__ == "__main__":
    migrate_data()