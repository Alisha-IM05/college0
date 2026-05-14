"""
User Management & Authentication module (Zhuolin).

Covers UC-07 through UC-13:
    UC-07  Visitor submits student application
    UC-08  Visitor submits instructor application
    UC-09  Registrar approves or rejects applications
    UC-10  New student/instructor receives ID + temporary password
    UC-11  Approved user changes password on first login
    UC-12  User logs in with role-based access control
    UC-13  Student or instructor account is suspended or terminated

Visitors apply without third-party identity. Submitting an application creates a
provisional `users` row (`applicant_only=1`) with a temporary password; **username and
temporary password are shown on the website** at `/apply/status?token=…` (save that link).
Signed-in users can also load applications by email match. The registrar approves by
clearing `applicant_only` and adding `students` when applicable (password unchanged);
reject deletes the provisional user so the same email can apply again.
"""

from __future__ import annotations

import logging
import re
import secrets
from functools import wraps
from typing import Optional

from flask import redirect, session, url_for

from database.db import get_db

from modules.mail import send_application_rejected_email


# ── UC-07 / UC-08: visitor submits an application ────────────────────────────


def submit_application(
    first_name: str,
    last_name: str,
    email: str,
    role_applied: str,
) -> tuple[bool, str, Optional[str]]:
    """Insert a pending application and provisional user. Returns (ok, message, view_token)."""
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = (email or "").strip().lower()

    if not first_name:
        return False, "Please enter your first name.", None
    if not last_name:
        return False, "Please enter your last name.", None
    if not email or "@" not in email:
        return False, "Please enter a valid email address.", None
    if role_applied not in ("student", "instructor"):
        return False, "Role must be either 'student' or 'instructor'.", None

    name = f"{first_name} {last_name}"
    view_token = secrets.token_urlsafe(24)

    conn = get_db()
    try:
        existing_pending = conn.execute(
            """SELECT id FROM applications
               WHERE LOWER(email) = ? AND status = 'pending'""",
            (email,),
        ).fetchone()
        if existing_pending:
            return False, "You already have a pending application with this email.", None

        existing_user = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?", (email,)
        ).fetchone()
        if existing_user:
            return False, "An account with that email already exists. Try logging in.", None

        username = _generate_username(conn, name)
        temp_password = secrets.token_urlsafe(8)

        with conn:
            conn.execute(
                """INSERT INTO applications (name, email, role_applied, clerk_user_id, view_token)
                   VALUES (?, ?, ?, NULL, ?)""",
                (name, email, role_applied, view_token),
            )
            conn.execute(
                """INSERT INTO users
                       (username, email, password, role, status, must_change_password,
                        clerk_user_id, applicant_only)
                   VALUES (?, ?, ?, ?, 'active', 1, NULL, 1)""",
                (username, email, temp_password, role_applied),
            )
    finally:
        conn.close()

    return (
        True,
        "Application submitted! Your username and temporary password are on the next page — save your status link.",
        view_token,
    )


def get_applications_for_view_token(view_token: str) -> list:
    """Return 0–1 application rows for a secret status token (joined with users)."""
    if not view_token or not view_token.strip():
        return []
    conn = get_db()
    try:
        return conn.execute(
            """SELECT a.id, a.name, a.email, a.role_applied, a.status,
                      a.submitted_at, a.reviewed_at,
                      u.id AS user_id,
                      u.username AS issued_username,
                      u.must_change_password,
                      CASE WHEN u.must_change_password = 1 THEN u.password ELSE NULL END
                          AS issued_temp_password
               FROM applications a
               LEFT JOIN users u ON LOWER(u.email) = LOWER(a.email)
               WHERE a.view_token = ?
               ORDER BY a.submitted_at DESC""",
            (view_token.strip(),),
        ).fetchall()
    finally:
        conn.close()


def get_applications_for_user_id(user_id: int) -> list:
    """Applications whose email matches the signed-in user's email (same columns as token query)."""
    if not user_id:
        return []
    conn = get_db()
    try:
        return conn.execute(
            """SELECT a.id, a.name, a.email, a.role_applied, a.status,
                      a.submitted_at, a.reviewed_at,
                      u.id AS user_id,
                      u.username AS issued_username,
                      u.must_change_password,
                      CASE WHEN u.must_change_password = 1 THEN u.password ELSE NULL END
                          AS issued_temp_password
               FROM applications a
               LEFT JOIN users u ON LOWER(u.email) = LOWER(a.email)
               WHERE LOWER(a.email) = (SELECT LOWER(email) FROM users WHERE id = ?)
               ORDER BY a.submitted_at DESC""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


# ── UC-09: registrar approves or rejects ─────────────────────────────────────


def list_pending_applications() -> list:
    conn = get_db()
    try:
        return conn.execute(
            """SELECT * FROM applications
               WHERE status = 'pending'
               ORDER BY submitted_at ASC"""
        ).fetchall()
    finally:
        conn.close()


def list_all_applications() -> list:
    conn = get_db()
    try:
        return conn.execute(
            """SELECT * FROM applications
               ORDER BY submitted_at DESC"""
        ).fetchall()
    finally:
        conn.close()


def _first_name_slug(full_name: str) -> str:
    first = (full_name or "").strip().split()[0] if (full_name or "").strip() else "user"
    slug = re.sub(r"[^a-z0-9]+", "", first.lower())
    if not slug:
        slug = "user"
    if slug[0].isdigit():
        slug = "u" + slug
    return slug[:32]


def _generate_username(conn, full_name: str) -> str:
    """Collision-free username derived from the applicant's first name."""
    base = _first_name_slug(full_name)
    n = 0
    while True:
        candidate = base if n == 0 else f"{base}{n}"
        if not conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (candidate,)
        ).fetchone():
            return candidate
        n += 1


# ── UC-10: issue ID + temporary password ─────────────────────────────────────


def approve_application(application_id: int) -> dict:
    """Approve pending application: activate user (no password change, no email)."""
    conn = get_db()
    try:
        app = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not app:
            return {"ok": False, "message": "Application not found."}
        if app["status"] != "pending":
            return {"ok": False, "message": f"Application is already {app['status']}."}

        urow = conn.execute(
            """SELECT id, username, email, role, applicant_only
               FROM users WHERE LOWER(email) = LOWER(?)""",
            (app["email"],),
        ).fetchone()
        if not urow:
            return {
                "ok": False,
                "message": "No account found for this applicant. They may need to submit again.",
            }
        if int(urow["applicant_only"] or 0) != 1:
            return {
                "ok": False,
                "message": "This applicant is already fully activated or the account is not provisional.",
            }

        user_id = urow["id"]
        username = urow["username"]

        conn.execute(
            "UPDATE users SET applicant_only = 0 WHERE id = ?",
            (user_id,),
        )
        if app["role_applied"] == "student":
            conn.execute(
                "INSERT OR IGNORE INTO students (id) VALUES (?)", (user_id,)
            )
        conn.execute(
            """UPDATE applications
               SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (application_id,),
        )
        conn.commit()

        return {
            "ok": True,
            "message": "Application approved.",
            "user_id": user_id,
            "username": username,
            "role": app["role_applied"],
            "email": app["email"],
        }
    finally:
        conn.close()


def reject_application(application_id: int) -> tuple[bool, str]:
    conn = get_db()
    try:
        app = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not app:
            return False, "Application not found."
        if app["status"] != "pending":
            return False, f"Application is already {app['status']}."
        conn.execute(
            """DELETE FROM users
               WHERE LOWER(email) = LOWER(?) AND IFNULL(applicant_only, 0) = 1""",
            (app["email"],),
        )
        conn.execute(
            """UPDATE applications
               SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (application_id,),
        )
        conn.commit()
        send_application_rejected_email(app["email"])
        return True, "Application rejected."
    finally:
        conn.close()


# ── UC-11: change password on first login ────────────────────────────────────


def change_password(
    user_id: int, old_password: str, new_password: str
) -> tuple[bool, str]:
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    if old_password == new_password:
        return False, "New password must be different from the current one."

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "User not found."
        if user["password"] != old_password:
            return False, "Current password is incorrect."

        conn.execute(
            """UPDATE users
               SET password = ?, must_change_password = 0
               WHERE id = ?""",
            (new_password, user_id),
        )
        conn.commit()
        return True, "Password updated successfully."
    finally:
        conn.close()


# ── UC-12: role-based access control ─────────────────────────────────────────


def require_role(*roles: str):
    """Decorator that enforces login + (optionally) a role allow-list."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("home"))

            conn = get_db()
            user = conn.execute(
                """SELECT status, role, must_change_password, applicant_only
                   FROM users WHERE id = ?""",
                (session["user_id"],),
            ).fetchone()
            conn.close()

            if not user:
                session.clear()
                return redirect(url_for("home"))

            if user["status"] != "active":
                reason = user["status"]
                session.clear()
                return redirect(url_for("account_blocked_page", reason=reason))

            if user["must_change_password"] and view.__name__ != "change_password_page" \
                    and view.__name__ != "change_password_submit":
                session["must_change_password"] = True
                return redirect(url_for("change_password_page"))

            if roles and user["role"] not in roles:
                return redirect(url_for("dashboard"))

            if (
                roles
                and user["role"] in roles
                and int(user["applicant_only"] or 0) == 1
                and user["role"] in ("student", "instructor")
            ):
                return redirect(url_for("apply_status"))

            return view(*args, **kwargs)

        return wrapper

    return decorator


# ── UC-13: suspend / terminate ───────────────────────────────────────────────


def _set_user_status(user_id: int, status: str) -> tuple[bool, str]:
    if status not in ("active", "suspended", "terminated"):
        return False, "Invalid status."
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "User not found."
        if user["role"] == "registrar":
            return False, "Cannot change status of a registrar account."
        conn.execute(
            "UPDATE users SET status = ? WHERE id = ?", (status, user_id)
        )
        conn.commit()
        return True, f"User marked {status}."
    finally:
        conn.close()


def suspend_user(user_id: int) -> tuple[bool, str]:
    return _set_user_status(user_id, "suspended")


def terminate_user(user_id: int) -> tuple[bool, str]:
    return _set_user_status(user_id, "terminated")


def reactivate_user(user_id: int) -> tuple[bool, str]:
    return _set_user_status(user_id, "active")


def list_manageable_users() -> list:
    conn = get_db()
    try:
        return conn.execute(
            """SELECT id, username, email, role, status, created_at
               FROM users
               WHERE role != 'registrar'
               ORDER BY
                   CASE status WHEN 'active' THEN 1
                               WHEN 'suspended' THEN 2
                               WHEN 'terminated' THEN 3 END,
                   role, username"""
        ).fetchall()
    finally:
        conn.close()
