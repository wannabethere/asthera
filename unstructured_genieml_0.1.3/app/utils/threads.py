import json
from typing import Any, Dict, List, Optional

from app.utils.postgresdb import PostgresDB


def get_thread(thread_id: int) -> Optional[Dict[str, Any]]:
    """Get a thread by ID.

    Args:
        thread_id: ID of the thread to get

    Returns:
        Optional[Dict[str, Any]]: The thread data or None if not found
    """
    db = PostgresDB()
    query = "SELECT * FROM thread WHERE id = %s;"
    result = db.execute_query(query, (thread_id,))
    return result[0] if result else None


def create_thread(name: str) -> int:
    """Get an existing thread or create a new one.

    Args:
        name: Name for the new thread if creating one

    Returns:
        int: The thread ID
    """
    db = PostgresDB()
    result = db.execute_query(
        "INSERT INTO thread (name) VALUES (%s) RETURNING id;", (name,)
    )
    return result[0]["id"]


def get_thread_messages(thread_id: int) -> List[Dict[str, Any]]:
    """Get all messages for a specific thread.

    Args:
        thread_id: ID of the thread to get messages for

    Returns:
        List[Dict]: List of message dictionaries
    """
    db = PostgresDB()
    query = "SELECT * FROM thread_message WHERE thread_id = %s ORDER BY created_at ASC;"
    messages = db.execute_query(query, (thread_id,))
    return messages or []


def save_thread_messages(thread_id: int, messages: List[Dict[str, str]]) -> None:
    """Save multiple messages to a thread.

    Args:
        thread_id: ID of the thread to save messages to
        messages: List of message dictionaries with 'sender' and 'message' keys
    """
    db = PostgresDB()
    with db._get_cursor() as cursor:
        for msg in messages:
            cursor.execute(
                "INSERT INTO thread_message (thread_id, message_id, message_type, message_content, message_extra) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb);",
                (
                    thread_id,
                    msg["message_id"],
                    msg["message_type"],
                    json.dumps(msg["message_content"]),
                    json.dumps(msg["message_extra"]),
                ),
            )


def get_all_threads(limit: int = -1) -> List[Dict[str, Any]]:
    """Get all threads.

    Returns:
        List[Dict]: List of thread records
    """
    db = PostgresDB()
    query = "SELECT * FROM thread ORDER BY created_at ASC;"
    if limit > 0:
        query += f" LIMIT {limit};"
    threads = db.execute_query(query)
    return threads or []
