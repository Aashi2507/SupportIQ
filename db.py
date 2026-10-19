
import mysql.connector
import streamlit as st


VALID_STATUSES = ("New", "In Progress", "Resolved")


def get_connection():
    """Connect to the SupportIQ MySQL database."""
    config = st.secrets["mysql"]

    return mysql.connector.connect(
        host=config["host"],
        port=int(config.get("port", 3306)),
        user=config["user"],
        password=config["password"],
        database=config.get("database", "supportiq"),
    )


def save_ticket(
    user_id,
    subject,
    body,
    category,
    priority,
    sentiment,
    sentiment_score,
    model_version="SupportIQ-v1",
):
    """Save an analyzed complaint and return its ticket ID."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO tickets (
                user_id, subject, body, predicted_category,
                predicted_priority, predicted_sentiment,
                sentiment_score, model_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                subject,
                body,
                category,
                priority.lower(),
                sentiment.lower(),
                sentiment_score,
                model_version,
            ),
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_customer_ticket_counts(user_id):
    """Return ticket counts for one customer only."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'New'), 0) AS new,
                COALESCE(SUM(status = 'In Progress'), 0) AS in_progress,
                COALESCE(SUM(status = 'Resolved'), 0) AS resolved
            FROM tickets
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_agent_ticket_counts():
    """Return overall ticket counts for the agent dashboard."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'New'), 0) AS new,
                COALESCE(SUM(status = 'In Progress'), 0) AS in_progress,
                COALESCE(SUM(status = 'Resolved'), 0) AS resolved
            FROM tickets
            """
        )
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_customer_tickets(user_id, status=None, search=None):
    """Return only the authenticated customer's tickets."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT id, subject, status, created_at
            FROM tickets
            WHERE user_id = %s
        """
        values = [user_id]

        if status and status in VALID_STATUSES:
            query += " AND status = %s"
            values.append(status)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query += " AND (CAST(id AS CHAR) LIKE %s OR subject LIKE %s)"
            values.extend([term, term])

        query += " ORDER BY created_at DESC"

        cursor.execute(query, tuple(values))
        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_agent_tickets(status=None, search=None):
    """Return tickets for the support-agent queue."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                t.id, t.subject, t.status, t.created_at,
                t.predicted_category, t.predicted_priority,
                u.full_name AS customer_name, u.email AS customer_email
            FROM tickets t
            JOIN users u ON t.user_id = u.user_id
            WHERE 1 = 1
        """
        values = []

        if status and status in VALID_STATUSES:
            query += " AND t.status = %s"
            values.append(status)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query += """
                AND (
                    CAST(t.id AS CHAR) LIKE %s
                    OR t.subject LIKE %s
                    OR u.full_name LIKE %s
                    OR u.email LIKE %s
                )
            """
            values.extend([term, term, term, term])

        query += """
            ORDER BY
                CASE t.predicted_priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                t.created_at DESC
        """

        cursor.execute(query, tuple(values))
        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_customer_ticket_by_id(ticket_id, user_id):
    """Fetch a ticket only if it belongs to this customer."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, subject, body, status, created_at
            FROM tickets
            WHERE id = %s AND user_id = %s
            """,
            (ticket_id, user_id),
        )
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_agent_ticket_by_id(ticket_id):
    """Fetch ticket details and AI analysis for an agent."""
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                t.id, t.subject, t.body, t.status, t.created_at,
                t.predicted_category, t.predicted_priority,
                t.predicted_sentiment, t.sentiment_score,
                t.model_version,
                u.user_id AS customer_id,
                u.full_name AS customer_name,
                u.email AS customer_email
            FROM tickets t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.id = %s
            """,
            (ticket_id,),
        )
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        connection.close()


def update_ticket_status(ticket_id, new_status):
    """Update a ticket to an allowed status."""
    if new_status not in VALID_STATUSES:
        raise ValueError("Invalid ticket status.")

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE tickets SET status = %s WHERE id = %s",
            (new_status, ticket_id),
        )
        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        connection.close()
