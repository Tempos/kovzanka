import os
import sqlite3
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "ice_rink.db"


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _get_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def migrate_data(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> None:
    if not sqlite_path.exists():
        print(f"Локальна база SQLite не знайдена ({sqlite_path}). Міграцію пропущено.")
        return

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()

    mysql_conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "kovzanka"),
        password=os.getenv("MYSQL_PASSWORD", "secret"),
        database=os.getenv("MYSQL_DATABASE", "kovzanka_db"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        charset="utf8mb4",
    )
    mysql_cursor = mysql_conn.cursor()

    try:
        # 1. skate_inventory
        if _table_exists(sqlite_cursor, "skate_inventory"):
            sqlite_cursor.execute(
                "SELECT size, total_stock, maintenance_count, is_deleted FROM skate_inventory"
            )
            inventory_rows = sqlite_cursor.fetchall()
            for row in inventory_rows:
                mysql_cursor.execute(
                    """
                    INSERT IGNORE INTO skate_inventory
                        (size, total_stock, maintenance_count, is_deleted)
                    VALUES (%s, %s, %s, %s)
                    """,
                    row,
                )
            print(f"Оброблено записів skate_inventory: {len(inventory_rows)}")

        # 2. queue (в старих базах могло називатися queue_items)
        queue_table = (
            "queue"
            if _table_exists(sqlite_cursor, "queue")
            else ("queue_items" if _table_exists(sqlite_cursor, "queue_items") else None)
        )
        if queue_table:
            cols = _get_columns(sqlite_cursor, queue_table)
            issue_status_expr = "issue_status" if "issue_status" in cols else "NULL"
            issue_note_expr = "issue_note" if "issue_note" in cols else "NULL"

            sqlite_cursor.execute(
                f"""
                SELECT
                    id, ticket_number, phone, people_count, shoe_sizes,
                    duration_minutes, status, comment,
                    {issue_status_expr}, {issue_note_expr},
                    telegram_chat_id, tracking_token,
                    session_start, session_end, created_at, called_at, overtime_stopped_at
                FROM {queue_table}
                """
            )
            queue_rows = sqlite_cursor.fetchall()
            for row in queue_rows:
                mysql_cursor.execute(
                    """
                    INSERT IGNORE INTO queue
                        (id, ticket_number, phone, people_count, shoe_sizes,
                         duration_minutes, status, comment,
                         issue_status, issue_note,
                         telegram_chat_id, tracking_token,
                         session_start, session_end, created_at, called_at, overtime_stopped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    row,
                )
            print(f"Оброблено записів {queue_table} -> queue: {len(queue_rows)}")

        # 3. users (підтримка старих баз з password_hash та актуальних з password)
        if _table_exists(sqlite_cursor, "users"):
            user_cols = _get_columns(sqlite_cursor, "users")
            pwd_col = "password" if "password" in user_cols else ("password_hash" if "password_hash" in user_cols else None)
            if pwd_col:
                sqlite_cursor.execute(f"SELECT id, username, {pwd_col}, role FROM users")
                user_rows = sqlite_cursor.fetchall()
                for row in user_rows:
                    mysql_cursor.execute(
                        """
                        INSERT IGNORE INTO users (id, username, password, role)
                        VALUES (%s, %s, %s, %s)
                        """,
                        row,
                    )
                print(f"Оброблено записів users: {len(user_rows)}")

        mysql_conn.commit()
        print("Міграцію даних з SQLite до MySQL успішно завершено.")
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    env_path = os.getenv("SQLITE_PATH")
    migrate_data(Path(env_path) if env_path else DEFAULT_SQLITE_PATH)