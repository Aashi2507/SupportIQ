
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import streamlit as st
from mysql.connector import IntegrityError

from db import get_connection
from email_service import send_otp_email


OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


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

    except (ValueError, TypeError, AttributeError):
        return False


def _clean_email(email):
    return email.strip().lower()


def _hash_otp(email, purpose, otp):
    pepper = st.secrets["security"]["otp_pepper"]

    message = (
        f"{_clean_email(email)}:{purpose}:{otp}"
    ).encode("utf-8")

    return hmac.new(
        pepper.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def email_exists(email):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT 1 FROM users WHERE email = %s LIMIT 1",
            (_clean_email(email),),
        )

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        connection.close()


def request_otp(email, purpose, role=None):
    email = _clean_email(email)

    if purpose not in ("REGISTER", "LOGIN", "RESET_PASSWORD"):
        return False, "Invalid OTP request."

    if not email or "@" not in email:
        return False, "Please enter a valid email address."

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, role, email_verified
            FROM users
            WHERE email = %s
            """,
            (email,),
        )

        user = cursor.fetchone()

        if purpose == "REGISTER":
            # Support verification is allowed only for an
            # existing Support Agent account.
            if role == "SUPPORT" and (
                not user or user["role"] != "SUPPORT"
            ):
                return False, (
                    "No existing Support Agent account matches that email."
                )

            # Customer registration must never verify a
            # Support Agent account.
            if (
                user
                and user["role"] == "SUPPORT"
                and role != "SUPPORT"
            ):
                return False, (
                    "This email belongs to an existing Support Agent account."
                )

            if user and user["email_verified"]:
                return False, "This email is already registered."

            # Existing unverified accounts can verify their email.
            # This flow never creates an account.

        else:
            if (
                not user
                or not user["email_verified"]
                or (role and user["role"] != role)
            ):
                return False, (
                    "No verified account matches that email and account type."
                )

        cursor.execute(
            """
            SELECT created_at
            FROM auth_otps
            WHERE email = %s AND purpose = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email, purpose),
        )

        recent_otp = cursor.fetchone()

        if recent_otp:
            elapsed = datetime.now() - recent_otp["created_at"]

            if (
                elapsed.total_seconds()
                < OTP_RESEND_COOLDOWN_SECONDS
            ):
                return False, (
                    "Please wait 60 seconds before requesting another code."
                )

        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(email, purpose, otp)

        expires_at = datetime.now() + timedelta(
            minutes=OTP_EXPIRY_MINUTES
        )

        cursor.execute(
            """
            DELETE FROM auth_otps
            WHERE email = %s AND purpose = %s
            """,
            (email, purpose),
        )

        cursor.execute(
            """
            INSERT INTO auth_otps
                (email, otp_hash, purpose, expires_at, attempts)
            VALUES (%s, %s, %s, %s, 0)
            """,
            (email, otp_hash, purpose, expires_at),
        )

        connection.commit()

        try:
            send_otp_email(email, otp, purpose)

        except Exception:
            cursor.execute(
                """
                DELETE FROM auth_otps
                WHERE email = %s AND purpose = %s
                """,
                (email, purpose),
            )

            connection.commit()
            raise

        return True, "Verification code sent to your email."

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def verify_otp(email, otp, purpose):
    email = _clean_email(email)
    otp = otp.strip()

    if purpose not in ("REGISTER", "LOGIN", "RESET_PASSWORD"):
        return False, "Invalid OTP purpose."

    if len(otp) != 6 or not otp.isdigit():
        return False, "Enter the 6-digit verification code."

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT otp_id, otp_hash, expires_at, attempts
            FROM auth_otps
            WHERE email = %s AND purpose = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email, purpose),
        )

        record = cursor.fetchone()

        if not record:
            return False, "No active code found. Request a new code."

        if record["expires_at"] <= datetime.now():
            cursor.execute(
                "DELETE FROM auth_otps WHERE otp_id = %s",
                (record["otp_id"],),
            )

            connection.commit()
            return False, "This code has expired. Request a new code."

        if record["attempts"] >= OTP_MAX_ATTEMPTS:
            cursor.execute(
                "DELETE FROM auth_otps WHERE otp_id = %s",
                (record["otp_id"],),
            )

            connection.commit()
            return False, "Too many attempts. Request a new code."

        expected_hash = _hash_otp(email, purpose, otp)

        if not hmac.compare_digest(
            expected_hash,
            record["otp_hash"],
        ):
            cursor.execute(
                """
                UPDATE auth_otps
                SET attempts = attempts + 1
                WHERE otp_id = %s
                """,
                (record["otp_id"],),
            )

            connection.commit()
            return False, "Incorrect code."

        # For registration verification, confirm the existing
        # account is eligible before marking its email verified.
        if purpose == "REGISTER":
            cursor.execute(
                """
                SELECT user_id, role, email_verified
                FROM users
                WHERE email = %s
                """,
                (email,),
            )

            user = cursor.fetchone()

            if user and user["email_verified"]:
                cursor.execute(
                    "DELETE FROM auth_otps WHERE otp_id = %s",
                    (record["otp_id"],),
                )

                connection.commit()
                return False, "This email is already registered."

            cursor.execute(
                """
                UPDATE users
                SET email_verified = 1
                WHERE email = %s AND email_verified = 0
                """,
                (email,),
            )

        cursor.execute(
            "DELETE FROM auth_otps WHERE otp_id = %s",
            (record["otp_id"],),
        )

        connection.commit()
        return True, "Email verified successfully."

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def register_customer(
    full_name,
    email,
    password,
    email_verified=False,
):
    if not email_verified:
        return False, "Verify your email before creating an account."

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users
                (full_name, email, password_hash, role, email_verified)
            VALUES (%s, %s, %s, 'CUSTOMER', 1)
            """,
            (
                full_name.strip(),
                _clean_email(email),
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


def get_verified_user(email, role):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, full_name, email, role
            FROM users
            WHERE email = %s
              AND role = %s
              AND email_verified = 1
            """,
            (_clean_email(email), role),
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def authenticate_user(email, password):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, full_name, email, password_hash,
                   role, email_verified
            FROM users
            WHERE email = %s
            """,
            (_clean_email(email),),
        )

        user = cursor.fetchone()

        if (
            user
            and user["email_verified"]
            and verify_password(password, user["password_hash"])
        ):
            user.pop("password_hash")
            user.pop("email_verified")
            return user

        return None

    finally:
        cursor.close()
        connection.close()


def reset_password_with_otp(
    email,
    otp,
    new_password,
    role,
):
    if len(new_password) < 8:
        return False, "Your password must contain at least 8 characters."

    user = get_verified_user(email, role)

    if not user:
        return False, (
            "No verified account matches that email and account type."
        )

    valid, message = verify_otp(
        email,
        otp,
        "RESET_PASSWORD",
    )

    if not valid:
        return False, message

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE email = %s
              AND role = %s
              AND email_verified = 1
            """,
            (
                hash_password(new_password),
                _clean_email(email),
                role,
            ),
        )

        connection.commit()

        if cursor.rowcount != 1:
            return False, (
                "Password could not be updated. Please try again."
            )

        return True, "Password updated successfully."

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
