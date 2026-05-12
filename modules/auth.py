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

Clerk is used both for the visitor-facing application flow (sign-up + status
check) and as the front door for approved users on the main login page: an
approved user signs in with the same Clerk account they used when applying,
the JWT is verified server-side, and a Flask session is opened against the
matching `users.clerk_user_id` row. UC-10/UC-11 are unchanged — the user is
still issued a temporary password and forced through /change-password on
first login.
"""

from __future__ import annotations

import os
import secrets
from functools import wraps
from typing import Optional

from flask import redirect, request, session, url_for

from database.db import get_db


# ── CLERK (visitor sessions only) ────────────────────────────────────────────

_clerk_sdk = None


def _get_clerk_sdk():
    """Lazily build the Clerk SDK client. Returns None if no secret key is set
    so the app still boots for non-Clerk routes during local development."""
    global _clerk_sdk
    if _clerk_sdk is not None:
        return _clerk_sdk

    secret_key = os.environ.get("CLERK_SECRET_KEY")
    if not secret_key:
        return None

    try:
        from clerk_backend_api import Clerk  # type: ignore
    except ImportError:
        return None

    _clerk_sdk = Clerk(bearer_auth=secret_key)
    return _clerk_sdk


def verify_clerk_session(flask_request) -> Optional[str]:
    """Validate the Clerk session attached to a Flask request and return the
    Clerk user id (`sub` claim) when signed in, otherwise None.

    The Clerk frontend SDK puts the session JWT in either the `__session`
    cookie or an `Authorization: Bearer <jwt>` header; the Python SDK reads
    both automatically.
    """
    sdk = _get_clerk_sdk()
    if sdk is None:
        return None

    try:
        from clerk_backend_api.security.types import AuthenticateRequestOptions  # type: ignore
    except ImportError:
        return None

    authorized_parties = [
        p.strip()
        for p in os.environ.get(
            "CLERK_AUTHORIZED_PARTIES",
            "http://localhost:5000,http://127.0.0.1:5000",
        ).split(",")
        if p.strip()
    ]

    try:
        state = sdk.authenticate_request(
            flask_request,
            AuthenticateRequestOptions(authorized_parties=authorized_parties),
        )
    except Exception:
        return None

    if not getattr(state, "is_signed_in", False):
        return None

    payload = getattr(state, "payload", None) or {}
    return payload.get("sub")


def find_user_by_clerk_id(clerk_user_id: str):
    """Return the `users` row whose Clerk identity matches, or None."""
    if not clerk_user_id:
        return None
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE clerk_user_id = ?", (clerk_user_id,)
        ).fetchone()
    finally:
        conn.close()


def _has_pending_application(clerk_user_id: str) -> bool:
    if not clerk_user_id:
        return False
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT 1 FROM applications
               WHERE clerk_user_id = ? AND status = 'pending' LIMIT 1""",
            (clerk_user_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def establish_clerk_session(flask_request) -> dict:
    """Bridge a verified Clerk session into the Flask session shape used by
    `@require_role` and `enforce_password_change`. Returns a result dict the
    /auth/clerk-login route can act on:

        { ok: True,  user: <Row>,  redirect: '/dashboard' | '/change-password',
          must_change_password: bool }

        { ok: False, status: 'not_signed_in' | 'no_account' | 'pending'
                             | 'suspended' | 'terminated',
          error: '<human message>', redirect: '<optional next page>' }

    UC-10/UC-11 behaviour is preserved: when the linked user still has
    `must_change_password = 1`, the caller redirects to /change-password just
    like `POST /login` does today.
    """
    clerk_user_id = verify_clerk_session(flask_request)
    if not clerk_user_id:
        return {
            "ok": False,
            "status": "not_signed_in",
            "error": "Clerk session could not be verified. Please sign in again.",
        }

    user = find_user_by_clerk_id(clerk_user_id)
    if user is None:
        if _has_pending_application(clerk_user_id):
            return {
                "ok": False,
                "status": "pending",
                "error": "Your application is still pending review.",
                "redirect": url_for("apply_status"),
            }
        return {
            "ok": False,
            "status": "no_account",
            "error": "No account is linked to this Clerk identity yet. "
                     "Submit an application to get started.",
            "redirect": url_for("apply_page"),
        }

    if user["status"] == "suspended":
        return {
            "ok": False,
            "status": "suspended",
            "error": "Your account is suspended. Please contact the registrar.",
        }
    if user["status"] == "terminated":
        return {
            "ok": False,
            "status": "terminated",
            "error": "Your account has been terminated. Please contact the registrar.",
        }

    must_change = bool(user["must_change_password"])
    redirect_target = url_for(
        "change_password_page" if must_change else "dashboard"
    )
    return {
        "ok": True,
        "user": user,
        "must_change_password": must_change,
        "redirect": redirect_target,
    }


# ── UC-07 / UC-08: visitor submits an application ────────────────────────────


def submit_application(
    first_name: str,
    last_name: str,
    email: str,
    role_applied: str,
    clerk_user_id: Optional[str],
) -> tuple[bool, str]:
    """Insert a pending application for a visitor.

    Both `first_name` and `last_name` are mandatory; they are combined into
    a single `name` for storage so the existing `applications.name` column
    remains the source of truth. Returns (ok, message). Refuses duplicate
    pending applications from the same Clerk user so a refresh-spammer
    can't flood the registrar inbox.
    """
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = (email or "").strip().lower()

    if not first_name:
        return False, "Please enter your first name."
    if not last_name:
        return False, "Please enter your last name."
    if not email or "@" not in email:
        return False, "Please enter a valid email address."
    if role_applied not in ("student", "instructor"):
        return False, "Role must be either 'student' or 'instructor'."

    name = f"{first_name} {last_name}"

    conn = get_db()
    try:
        if clerk_user_id:
            existing = conn.execute(
                """SELECT id FROM applications
                   WHERE clerk_user_id = ? AND status = 'pending'""",
                (clerk_user_id,),
            ).fetchone()
            if existing:
                return False, "You already have a pending application."

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing_user:
            return False, "An account with that email already exists. Try logging in."

        conn.execute(
            """INSERT INTO applications (name, email, role_applied, clerk_user_id)
               VALUES (?, ?, ?, ?)""",
            (name, email, role_applied, clerk_user_id),
        )
        conn.commit()
        return True, "Application submitted! The registrar will review it shortly."
    finally:
        conn.close()


def get_applications_for_clerk_user(clerk_user_id: str) -> list:
    """Return all applications submitted by a given Clerk user, most recent
    first. Joined with `users` so an approved application can also surface
    the issued username and (while still required) the temp password."""
    if not clerk_user_id:
        return []
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT a.id, a.name, a.email, a.role_applied, a.status,
                      a.submitted_at, a.reviewed_at,
                      u.id AS user_id,
                      u.username AS issued_username,
                      u.must_change_password,
                      CASE WHEN u.must_change_password = 1 THEN u.password ELSE NULL END
                          AS issued_temp_password
               FROM applications a
               LEFT JOIN users u ON LOWER(u.email) = LOWER(a.email)
               WHERE a.clerk_user_id = ?
               ORDER BY a.submitted_at DESC""",
            (clerk_user_id,),
        ).fetchall()
        return rows
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


def _generate_username(conn, role: str) -> str:
    """Build a fresh, collision-free username of the form `<role><n>`."""
    row = conn.execute(
        """SELECT username FROM users
           WHERE role = ? AND username GLOB ?
           ORDER BY id DESC LIMIT 1""",
        (role, f"{role}*"),
    ).fetchone()

    base_n = 1
    if row:
        suffix = row["username"][len(role):]
        if suffix.isdigit():
            base_n = int(suffix) + 1

    candidate = f"{role}{base_n}"
    while conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (candidate,)
    ).fetchone():
        base_n += 1
        candidate = f"{role}{base_n}"
    return candidate


# ── UC-10: issue ID + temporary password ─────────────────────────────────────


def approve_application(application_id: int) -> dict:
    """Approve a pending application, create the corresponding `users` row
    with a temp password and `must_change_password=1`, and link the student
    row when appropriate. Returns the credentials so the registrar can show
    them to the new user (UC-10)."""
    conn = get_db()
    try:
        app = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not app:
            return {"ok": False, "message": "Application not found."}
        if app["status"] != "pending":
            return {"ok": False, "message": f"Application is already {app['status']}."}

        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (app["email"],)
        ).fetchone()
        if existing:
            return {
                "ok": False,
                "message": "A user with that email already exists; cannot approve.",
            }

        username = _generate_username(conn, app["role_applied"])
        temp_password = secrets.token_urlsafe(8)

        cur = conn.execute(
            """INSERT INTO users
                   (username, email, password, role, status, must_change_password, clerk_user_id)
               VALUES (?, ?, ?, ?, 'active', 1, ?)""",
            (
                username,
                app["email"],
                temp_password,
                app["role_applied"],
                app["clerk_user_id"],
            ),
        )
        new_user_id = cur.lastrowid

        if app["role_applied"] == "student":
            conn.execute(
                "INSERT OR IGNORE INTO students (id) VALUES (?)", (new_user_id,)
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
            "user_id": new_user_id,
            "username": username,
            "temp_password": temp_password,
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
            """UPDATE applications
               SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (application_id,),
        )
        conn.commit()
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
    """Decorator that enforces login + (optionally) a role allow-list.

    Usage:
        @app.route('/foo')
        @require_role('registrar')
        def foo(): ...

        @app.route('/bar')
        @require_role()          # any logged-in user
        def bar(): ...
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("home"))

            conn = get_db()
            user = conn.execute(
                "SELECT status, role, must_change_password FROM users WHERE id = ?",
                (session["user_id"],),
            ).fetchone()
            conn.close()

            if not user or user["status"] != "active":
                session.clear()
                return redirect(url_for("home"))

            if user["must_change_password"] and view.__name__ != "change_password_page" \
                    and view.__name__ != "change_password_submit":
                session["must_change_password"] = True
                return redirect(url_for("change_password_page"))

            if roles and user["role"] not in roles:
                return redirect(url_for("dashboard"))

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
    """All users a registrar can act on (everyone except themselves /
    other registrars), with their current status surfaced for the UI."""
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
