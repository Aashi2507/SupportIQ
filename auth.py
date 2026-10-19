
import hashlib
import hmac
import secrets

from mysql.connector import IntegrityError
from db import get_connection


def hash_password(password):
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000,
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(password, stored_hash):
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            600_000,
        )

        return hmac.compare_digest(
            password_hash.hex(),
            hash_hex,
        )
    except (ValueError, TypeError):
        return False


def register_customer(full_name, email, password):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users
                (full_name, email, password_hash, role)
            VALUES (%s, %s, %s, 'CUSTOMER')
            """,
            (
                full_name.strip(),
                email.strip().lower(),
                hash_password(password),
            ),
        )
        connection.commit()
        return True, "Registration successful."

    except IntegrityError:
        connection.rollback()
        return False, "This email is already registered."

    finally:
        cursor.close()
        connection.close()


def authenticate_user(email, password):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, full_name, email, password_hash, role
            FROM users
            WHERE email = %s
            """,
            (email.strip().lower(),),
        )
        user = cursor.fetchone()

        if user and verify_password(password, user["password_hash"]):
            user.pop("password_hash")
            return user

        return None

    finally:
        cursor.close()
        connection.close()
