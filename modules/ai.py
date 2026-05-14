"""React/API-facing AI assistant module.

This module owns the new architecture routes:
- GET  /ai/assistant        -> React shell page
- POST /api/ai/assistant    -> JSON chat API
- POST /api/ai/enroll/<id>  -> chat-card enrollment

The actual AI/privacy/recommendation logic remains in modules.ai_features so the
migration does not fork Almasur's backend behavior.
"""

from __future__ import annotations

import json
import os
from typing import Any

from flask import jsonify, redirect, render_template, request, session, url_for

from database.db import get_db
from modules.ai_features import (
    _infer_difficulty_str,
    _is_recommendation_query,
    check_user_ai_eligibility,
    enroll_from_ai,
    find_student_reference,
    flag_query,
    generate_recommendations,
    get_all_flags,
    get_query_history,
    get_student_username,
    submit_public_query,
    submit_query,
)


def _json_default(obj: Any) -> Any:
    try:
        return dict(obj)
    except (TypeError, ValueError):
        pass
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _render_react(page: str, page_title: str, **data: Any):
    data.setdefault("clerk_publishable_key", os.environ.get("CLERK_PUBLISHABLE_KEY", ""))
    return render_template(
        "_shell.html",
        page=page,
        page_title=page_title,
        data_json=json.dumps(data, default=_json_default),
    )


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    try:
        return db.execute(
            "SELECT id, username, role, status FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        db.close()


def _effective_role(user) -> str:
    if not user:
        return "visitor"
    role = user["role"]
    return role if role in {"student", "instructor", "registrar"} else "visitor"


def _recommendation_cards(student_id: int, label_prefix: str | None = None) -> list[dict[str, Any]]:
    cards = []
    for rec in generate_recommendations(student_id):
        reason = rec["reason"]
        if label_prefix:
            reason = f"{label_prefix}: {reason}"
        cards.append({
            "id": rec["course"]["id"],
            "course_name": rec["course"]["course_name"],
            "time_slot": rec["course"].get("time_slot") or "TBD",
            "reason": reason,
            "difficulty": _infer_difficulty_str(rec["course"]["course_name"]),
        })
    return cards


def _validate_active_user(user):
    if not user:
        return None
    if user["status"] != "active":
        return jsonify({
            "error": "Your account is not active. Please contact the registrar.",
            "response": None,
            "source": None,
            "query_id": None,
        }), 403
    eligible, deny_reason = check_user_ai_eligibility(user["id"])
    if not eligible:
        return jsonify({
            "error": deny_reason,
            "response": None,
            "source": None,
            "query_id": None,
        }), 403
    return None


def register_ai_routes(app):
    """Register React page and JSON API routes for the AI assistant."""

    # Runtime migration used by the feedback endpoint.
    db = get_db()
    try:
        db.execute("ALTER TABLE ai_queries ADD COLUMN helpful INTEGER DEFAULT NULL")
        db.commit()
    except Exception:
        pass
    finally:
        db.close()

    @app.route("/ai/assistant")
    def ai_assistant_page():
        user = _current_user()
        role = _effective_role(user)
        username = user["username"] if user else "Guest"
        active_student_name = None
        pending_flags_count = 0

        if role == "registrar":
            active_student_name = get_student_username(session.get("ai_active_student_id"))
            pending_flags_count = len(get_all_flags(status_filter="pending"))

        return _render_react(
            "ai_assistant",
            "College0 — AI Assistant",
            username=username,
            role=role,
            active_student_name=active_student_name,
            pending_flags_count=pending_flags_count,
        )

    @app.route("/api/ai/assistant", methods=["POST"])
    def api_ai_assistant():
        data = request.get_json(silent=True) or {}
        query_text = (data.get("query_text") or "").strip()
        user = _current_user()
        role = _effective_role(user)

        if not user:
            return jsonify(submit_public_query(query_text))

        invalid = _validate_active_user(user)
        if invalid:
            return invalid

        active_student_id = None
        if role == "registrar":
            mentioned_student_id = find_student_reference(query_text)
            if mentioned_student_id:
                session["ai_active_student_id"] = mentioned_student_id
            active_student_id = session.get("ai_active_student_id")

        result = submit_query(
            user["id"],
            role,
            query_text,
            active_student_id=active_student_id,
        )

        if role == "registrar" and result.get("active_student_id"):
            session["ai_active_student_id"] = result["active_student_id"]
            active_student_id = result["active_student_id"]

        if role == "student" and _is_recommendation_query(query_text) and not result.get("error"):
            result["recommendation_cards"] = _recommendation_cards(user["id"])
        elif role == "registrar" and active_student_id and _is_recommendation_query(query_text) and not result.get("error"):
            student_name = get_student_username(active_student_id)
            result["active_student_name"] = student_name
            result["recommendation_cards"] = _recommendation_cards(
                active_student_id,
                f"For {student_name}" if student_name else None,
            )

        return jsonify(result)

    @app.route("/api/ai/enroll/<int:course_id>", methods=["POST"])
    def api_ai_enroll(course_id: int):
        user = _current_user()
        if not user:
            return jsonify({"ok": False, "error": "Please log in before enrolling."}), 401

        invalid = _validate_active_user(user)
        if invalid:
            return invalid

        role = _effective_role(user)
        if role == "student":
            target_student_id = user["id"]
        elif role == "registrar" and session.get("ai_active_student_id"):
            target_student_id = session["ai_active_student_id"]
        else:
            return jsonify({
                "ok": False,
                "error": "Registrar must select a student in chat before enrolling.",
            }), 403

        message, ok = enroll_from_ai(target_student_id, course_id)
        return jsonify({"ok": ok, "message": message}), (200 if ok else 400)

    @app.route("/api/ai/query/<int:query_id>/feedback", methods=["POST"])
    def api_ai_feedback(query_id: int):
        user = _current_user()
        if not user:
            return jsonify({"ok": False, "error": "Not authenticated."}), 401
        data = request.get_json(silent=True) or {}
        helpful = data.get("helpful")
        if helpful not in (0, 1, True, False):
            return jsonify({"ok": False, "error": "helpful must be true or false."}), 400

        db = get_db()
        try:
            db.execute(
                "UPDATE ai_queries SET helpful = ? WHERE id = ? AND user_id = ?",
                (1 if helpful else 0, query_id, user["id"]),
            )
            db.commit()
        finally:
            db.close()
        return jsonify({"ok": True})

    @app.route("/api/ai/query/<int:query_id>/flag", methods=["POST"])
    def api_ai_flag(query_id: int):
        user = _current_user()
        if not user:
            return jsonify({"ok": False, "error": "Not authenticated."}), 401
        data = request.get_json(silent=True) or {}
        reason = (data.get("reason") or "Flagged from AI Assistant").strip()
        flag_id = flag_query(query_id, user["id"], reason)
        return jsonify({"ok": True, "flag_id": flag_id})

    @app.route("/api/ai/flags")
    def api_ai_flags():
        user = _current_user()
        if not user or _effective_role(user) != "registrar":
            return jsonify({"ok": False, "error": "Registrar access only."}), 403
        status = request.args.get("status", "pending")
        flags = get_all_flags(None if status == "all" else status)
        return jsonify({"ok": True, "flags": flags})

    # Legacy endpoints redirect to the React page instead of the old template.
    @app.route("/ai/query", methods=["GET", "POST"])
    def ai_query_legacy():
        return redirect(url_for("ai_assistant_page"))
