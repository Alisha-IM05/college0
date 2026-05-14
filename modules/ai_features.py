import os
import re
import csv
import time
from datetime import datetime, timedelta, timezone
from database.db import get_db

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# K-013: Hardcoded baseline — always filtered regardless of DB table contents.
# The DB taboo_words table adds to this list at runtime (managed by the registrar).
TABOO_WORDS = [
    "stupid", "idiot", "dumb", "moron", "hate",
    "worthless", "incompetent", "cheat", "cheater",
    "plagiarize", "plagiarism", "expel", "expelled",
    "loser", "failure",
    "fuck", "fucking", "fucked", "fucker", "shit", "shitty",
    "bullshit", "bitch", "bitches", "asshole", "dick", "dicks",
    "crap", "damn", "bastard", "slut", "whore", "piss",
    "suck", "sucks", "sucked", "sucking",
]

DB_PATH = os.path.expanduser("~/college0/database/chroma_db")  # absolute chroma path — shared with seed_chroma.py

# ── BLOCK 1: UI, Query Logging & Rollback Safety ──────────────────────────────

def validate_query(query_text):
    # K-001
    if not query_text or not query_text.strip():
        return False, "Query cannot be empty."
    if len(query_text.strip()) < 3:
        return False, "Query is too short."
    if len(query_text) > 2000:
        return False, "Query exceeds 2000 character limit."
    return True, None


def log_query(user_id, query_text, response_text, source, role_at_query):
    # K-002: Rollback-safe write to ai_queries — returns new query_id
    db = get_db()
    try:
        db.execute("BEGIN")
        cursor = db.execute(
            """INSERT INTO ai_queries
               (user_id, query_text, response_text, source, role_at_query)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, query_text.strip(), response_text, source, role_at_query),
        )
        query_id = cursor.lastrowid
        db.commit()
        return query_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def submit_query(user_id, _session_role, query_text, active_student_id=None):
    # K-003: Single entry point — all security gates run here.
    # _session_role is accepted for API compatibility but NEVER trusted.
    # We always fetch the live role from database/college0.db.

    # K-001: Cheapest check first — no DB hit
    valid, error = validate_query(query_text)
    if not valid:
        return {"error": error, "response": None, "source": None, "query_id": None}

    # K-007 / Source-of-Truth: read live role from database/college0.db
    db = get_db()
    try:
        user_row = db.execute(
            "SELECT role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        db.close()

    if not user_row:
        return {"error": "User not found.", "response": None, "source": None, "query_id": None}

    fresh_role = user_row["role"]

    # K-007: Hard-block suspended / terminated / graduated accounts
    if fresh_role in ("suspended", "terminated", "graduated"):
        return {
            "error": f"Access Denied: Your account status '{fresh_role}' does not permit AI queries.",
            "response": None, "source": None, "query_id": None,
        }

    # Role alignment: any DB role not in the recognised set is treated as "visitor"
    # in Python logic only — "visitor" is never stored in database/college0.db.
    effective_role = fresh_role if fresh_role in _KNOWN_DB_ROLES else "visitor"

    # K-008: Rate limit — 20 queries per rolling hour
    if not check_rate_limit(user_id):
        return {
            "error": "Hourly query limit reached (20/hour). Please try again later.",
            "response": None, "source": None, "query_id": None,
        }

    # K-005: Role filter — uses effective_role derived from live DB value
    allowed, deny_reason = filter_query_by_role(query_text, effective_role)
    if not allowed:
        return {"error": deny_reason, "response": None, "source": None, "query_id": None}

    target_student_id = None
    if effective_role == "registrar":
        target_student_id = find_student_reference(query_text) or active_student_id

    # K-016/K-019/K-025: recommendation questions should be answered before
    # command parsing so "What else can I register him for?" does not execute.
    if effective_role == "student" and _is_recommendation_query(query_text):
        recs = generate_recommendations(user_id)
        if recs:
            lines = "\n".join(
                f"- {r['course']['course_name']}: {r['reason']}" for r in recs
            )
            response_text = f"Based on your academic profile, here are your recommended courses:\n{lines}"
            source = "vector_db"
        else:
            context = build_role_scoped_ai_context(user_id, effective_role)
            response_text, source = query_gemini_with_role_context(
                query_text, effective_role, context
            )
    elif effective_role == "registrar" and target_student_id and _is_recommendation_query(query_text):
        recs = generate_recommendations(target_student_id)
        student_name = get_student_username(target_student_id) or "that student"
        if recs:
            lines = "\n".join(
                f"- {r['course']['course_name']}: {r['reason']}" for r in recs
            )
            response_text = f"Based on {student_name}'s academic profile, these courses are available to register:\n{lines}"
        else:
            response_text = f"No available recommendations were found for {student_name}."
        source = "vector_db"
    else:
        enrollment_action = parse_enrollment_action(query_text, effective_role, target_student_id)
        drop_action = parse_drop_action(query_text, effective_role, target_student_id)
        if enrollment_action:
            if enrollment_action.get("error"):
                response_text = enrollment_action["error"]
                source = "vector_db"
            else:
                msg, ok = enroll_from_ai(enrollment_action["student_id"], enrollment_action["course_id"])
                response_text = msg
                source = "vector_db"
        elif drop_action:
            if drop_action.get("error"):
                response_text = drop_action["error"]
                source = "vector_db"
            else:
                msg, ok = drop_from_ai(drop_action["student_id"], drop_action["course_id"])
                response_text = msg
                source = "vector_db"
        else:
            context = build_role_scoped_ai_context(user_id, effective_role, target_student_id)
            response_text, source = query_gemini_with_role_context(
                query_text, effective_role, context
            )
    # K-013: Scrub taboo words from both sides before logging.
    # query_text was already used for RAG search above (original needed for accuracy).
    # logged_query is the sanitized version stored in ai_queries — DB always matches UI.
    raw_response_text = response_text
    response_text  = apply_taboo_filter(response_text)
    logged_query   = apply_taboo_filter(query_text)
    response_taboo_filtered = raw_response_text != response_text
    query_taboo_filtered = logged_query != query_text
    taboo_filtered = response_taboo_filtered or query_taboo_filtered
    taboo_count = response_text.count("****") + logged_query.count("****")

    query_id = log_query(user_id, logged_query, response_text, source, effective_role)
    return {
        "response": response_text,
        "display_query": logged_query,
        "source":   source,
        "query_id": query_id,
        "error":    None,
        "hallucination_warning": source == "llm",
        "taboo_filtered": taboo_filtered,
        "taboo_count": taboo_count,
        "target_student_id": target_student_id,
        "active_student_id": target_student_id,
        "debug":    _last_query_debug.copy(),  # distance scores for metadata panel
    }


def _is_recommendation_query(query_text):
    # Helper: True if the query is asking for course recommendations
    q = query_text.lower()
    keywords = [
        "recommend", "recommendation", "suggest", "suggestion",
        "what course should", "which course", "should i take",
        "what classes should", "what class should", "what courses should",
        "what else can i register", "what can i register", "can i register",
        "available to register",
    ]
    return any(kw in q for kw in keywords)


def find_student_reference(query_text):
    """Return a student id when a registrar names a student in the query."""
    q = (query_text or "").lower()
    db = get_db()
    try:
        rows = db.execute(
            """SELECT u.id, u.username, u.email
               FROM users u
               WHERE u.role = 'student'
               ORDER BY LENGTH(u.username) DESC"""
        ).fetchall()
        for row in rows:
            username = (row["username"] or "").lower()
            email_prefix = (row["email"] or "").split("@", 1)[0].lower()
            names = {username, email_prefix}
            for name in names:
                if name and re.search(r"\b" + re.escape(name) + r"\b", q):
                    return row["id"]
    finally:
        db.close()
    return None


def get_student_username(student_id):
    if not student_id:
        return None
    db = get_db()
    try:
        row = db.execute(
            "SELECT username FROM users WHERE id = ? AND role = 'student'",
            (student_id,),
        ).fetchone()
        return row["username"] if row else None
    finally:
        db.close()


def parse_enrollment_action(query_text, role, active_student_id=None):
    """Detect chat commands like 'enroll/register Nathan/him in CS310'.

    Returns:
        None              – query is not an enroll command
        {"error": str}    – enroll intent detected but something is missing
        {"student_id":…, "course_id":…} – ready to execute
    """
    q = (query_text or "").lower()
    is_enroll_command = (
        re.search(r"\b(enroll|register)\b", q) is not None
        or any(phrase in q for phrase in ("sign up", "add him", "add her", "add them", "add me"))
    )
    if not is_enroll_command:
        return None

    if role == "student":
        # student enrolls themselves — student_id filled by caller
        student_id = None
    elif role == "registrar":
        student_id = find_student_reference(query_text) or active_student_id
        if not student_id:
            return {"error": "Please specify which student to enroll (e.g., 'enroll Liam in CS101')."}
    else:
        return None

    course_id = find_course_reference(query_text)
    if not course_id:
        return {"error": "Please specify which course (e.g., 'enroll Liam in CS101')."}
    return {"student_id": student_id, "course_id": course_id}


_DROP_KEYWORDS = (
    "remove", "drop", "take out", "unenroll", "de-register",
    "deregister", "kick out", "withdraw", "pull out",
    "take him out", "take her out", "take them out",
)


def parse_drop_action(query_text, role, active_student_id=None):
    """Detect commands like 'remove/drop/take him out of MATH101'.

    Returns:
        None              – query is not a drop command
        {"error": str}    – drop intent detected but something is missing
        {"student_id":…, "course_id":…} – ready to execute
    """
    q = (query_text or "").lower()
    if not any(kw in q for kw in _DROP_KEYWORDS):
        return None  # not a drop query at all

    if role != "registrar":
        return None

    # Try to resolve student from the query first, then fall back to session context
    student_id = find_student_reference(query_text) or active_student_id
    if not student_id:
        return {"error": "Please specify which student to drop (e.g., 'remove Liam from CS101')."}

    course_id = find_course_reference(query_text)
    if not course_id:
        return {"error": "Please specify which course to drop them from (e.g., 'remove Liam from CS101')."}

    return {"student_id": student_id, "course_id": course_id}


def drop_from_ai(student_id, course_id):
    db = get_db()
    try:
        enrollment = db.execute(
            """SELECT id FROM enrollments
               WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
            (student_id, course_id),
        ).fetchone()
        if not enrollment:
            return "That student is not enrolled in this course.", False

        db.execute(
            "UPDATE enrollments SET status = 'cancelled' WHERE id = ?",
            (enrollment["id"],),
        )
        db.execute(
            "UPDATE courses SET enrolled_count = MAX(0, enrolled_count - 1) WHERE id = ?",
            (course_id,),
        )
        db.commit()

        student = db.execute(
            "SELECT username FROM users WHERE id = ?", (student_id,)
        ).fetchone()
        course = db.execute(
            "SELECT course_name FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        name = student["username"] if student else "Student"
        cname = course["course_name"] if course else "that course"
        return f"{name} has been removed from {cname}.", True
    except Exception as e:
        db.rollback()
        return f"Failed to drop course: {e}", False
    finally:
        db.close()


def find_course_reference(query_text):
    q = (query_text or "").lower()
    q_nospace = re.sub(r"[\s\-_]+", "", q)  # "math 101" → "math101" for code matching
    db = get_db()
    try:
        rows = db.execute(
            """SELECT id, course_name
               FROM courses
               ORDER BY LENGTH(course_name) DESC"""
        ).fetchall()
        for row in rows:
            course_name = row["course_name"] or ""
            code = _course_code(course_name).lower()          # e.g. "math101"
            title = course_name.lower()
            title_part = title.split(" - ", 1)[1] if " - " in title else title
            if (
                (code and (
                    re.search(r"\b" + re.escape(code) + r"\b", q)
                    or code in q_nospace
                ))
                or (title and title in q)
                or (title_part and len(title_part) > 3 and title_part in q)
            ):
                return row["id"]
    finally:
        db.close()
    return None


def build_role_scoped_ai_context(user_id, role, active_student_id=None):
    """Build the only database context Gemini is allowed to see.

    Student: only that student's profile, grades, enrollments, and public active courses.
    Instructor: only their assigned courses plus enrolled student names for those courses.
    Registrar: all students, grades, enrollments, courses, and AI moderation stats.
    Visitor/unknown: public active course catalog only.
    """
    db = get_db()
    try:
        lines = []

        if role == "student":
            user = db.execute(
                "SELECT id, username, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            student = db.execute(
                """SELECT semester_gpa, cumulative_gpa, credits_earned,
                          honor_roll, status, special_registration
                   FROM students WHERE id = ?""",
                (user_id,),
            ).fetchone()
            if not user or not student:
                return ["No student record exists for this logged-in account."]

            lines.append("ACCESS SCOPE: STUDENT_SELF_ONLY")
            lines.append(
                "Privacy rule: answer only about this logged-in student. "
                "If asked about any other student, say you do not have access."
            )
            lines.append(
                f"Logged-in student: {user['username']} (user_id {user['id']}, email {user['email']})."
            )
            lines.append(
                "Academic profile: "
                f"semester GPA {_fmt_num(student['semester_gpa'])}, "
                f"cumulative GPA {_fmt_num(student['cumulative_gpa'])}, "
                f"credits earned {student['credits_earned']}, "
                f"standing {student['status']}, "
                f"honor roll {'yes' if student['honor_roll'] else 'no'}, "
                f"special registration {'yes' if student['special_registration'] else 'no'}."
            )

            grades, enrollments = _fetch_student_grades(db, user_id)
            if grades:
                lines.append("Completed grades:")
                for grade in grades:
                    lines.append(
                        f"- {grade['course_name']}: {grade['letter_grade']} "
                        f"({_fmt_num(grade['numeric_value'])}/4.0)"
                    )
            else:
                lines.append("Completed grades: none on record.")

            if enrollments:
                lines.append("Current enrollments:")
                for enrollment in enrollments:
                    lines.append(
                        f"- {enrollment['course_name']} at {enrollment['time_slot']}"
                    )
            else:
                lines.append("Current enrollments: none.")

            _append_public_course_catalog(db, lines)
            return lines

        if role == "instructor":
            user = db.execute(
                "SELECT id, username, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            lines.append("ACCESS SCOPE: INSTRUCTOR_ASSIGNED_COURSES_ONLY")
            lines.append(
                "Privacy rule: answer only about this instructor's assigned courses "
                "and enrolled students in those courses. Do not reveal unrelated student records."
            )
            if user:
                lines.append(
                    f"Logged-in instructor: {user['username']} (user_id {user['id']}, email {user['email']})."
                )
            courses = db.execute(
                """SELECT id, course_name, time_slot, start_time, end_time,
                          capacity, enrolled_count, status
                   FROM courses
                   WHERE instructor_id = ?
                   ORDER BY course_name""",
                (user_id,),
            ).fetchall()
            if not courses:
                lines.append("Assigned courses: none.")
            for course in courses:
                lines.append(
                    f"Course {course['id']}: {course['course_name']}, "
                    f"schedule {course['time_slot'] or ''} {course['start_time'] or ''}-{course['end_time'] or ''}, "
                    f"status {course['status']}, enrollment {course['enrolled_count']}/{course['capacity']}."
                )
                students = db.execute(
                    """SELECT u.username, s.cumulative_gpa, s.status
                       FROM enrollments e
                       JOIN users u ON e.student_id = u.id
                       LEFT JOIN students s ON u.id = s.id
                       WHERE e.course_id = ? AND e.status = 'enrolled'
                       ORDER BY u.username""",
                    (course["id"],),
                ).fetchall()
                if students:
                    lines.append("  Enrolled students:")
                    for student in students:
                        lines.append(
                            f"  - {student['username']} "
                            f"(GPA {_fmt_num(student['cumulative_gpa'])}, standing {student['status']})"
                        )
                else:
                    lines.append("  Enrolled students: none.")
            _append_public_course_catalog(db, lines)
            return lines

        if role == "registrar":
            lines.append("ACCESS SCOPE: REGISTRAR_FULL_DATABASE")
            lines.append(
                "Privacy rule: registrar may access all student academic records, "
                "course enrollments, grades, AI logs, and flags."
            )
            students = db.execute(
                """SELECT u.id, u.username, u.email,
                          s.semester_gpa, s.cumulative_gpa, s.credits_earned,
                          s.honor_roll, s.special_registration, s.status
                   FROM users u
                   LEFT JOIN students s ON u.id = s.id
                   WHERE u.role = 'student'
                   ORDER BY u.username"""
            ).fetchall()
            lines.append(f"Student count: {len(students)}.")
            for student in students:
                lines.append(
                    f"Student {student['username']} (user_id {student['id']}, email {student['email']}): "
                    f"semester GPA {_fmt_num(student['semester_gpa'])}, "
                    f"cumulative GPA {_fmt_num(student['cumulative_gpa'])}, "
                    f"credits {student['credits_earned'] or 0}, "
                    f"standing {student['status'] or 'unknown'}, "
                    f"honor roll {'yes' if student['honor_roll'] else 'no'}, "
                    f"special registration {'yes' if student['special_registration'] else 'no'}."
                )
                grades, enrollments = _fetch_student_grades(db, student["id"])
                if grades:
                    lines.append("  Grades: " + "; ".join(
                        f"{g['course_name']}={g['letter_grade']}" for g in grades
                    ))
                else:
                    lines.append("  Grades: none.")
                if enrollments:
                    lines.append("  Enrollments: " + "; ".join(
                        f"{e['course_name']} ({e['time_slot']})" for e in enrollments
                    ))
                else:
                    lines.append("  Enrollments: none.")

            _append_public_course_catalog(db, lines)
            if active_student_id:
                focused = db.execute(
                    """SELECT u.id, u.username, u.email,
                              s.semester_gpa, s.cumulative_gpa, s.credits_earned,
                              s.honor_roll, s.special_registration, s.status
                       FROM users u
                       LEFT JOIN students s ON u.id = s.id
                       WHERE u.id = ? AND u.role = 'student'""",
                    (active_student_id,),
                ).fetchone()
                if focused:
                    lines.append(
                        f"ACTIVE REGISTRAR CHAT STUDENT: {focused['username']} "
                        f"(user_id {focused['id']}). Follow-up words like him/her/them/that student "
                        "refer to this student until another student is named."
                    )
                    grades, enrollments = _fetch_student_grades(db, focused["id"])
                    lines.append("Active student grades: " + (
                        "; ".join(f"{g['course_name']}={g['letter_grade']}" for g in grades)
                        if grades else "none"
                    ))
                    lines.append("Active student enrollments: " + (
                        "; ".join(f"{e['course_name']} ({e['time_slot']})" for e in enrollments)
                        if enrollments else "none"
                    ))
            total_queries = db.execute("SELECT COUNT(*) FROM ai_queries").fetchone()[0]
            pending_flags = db.execute(
                "SELECT COUNT(*) FROM ai_flags WHERE status = 'pending'"
            ).fetchone()[0]
            lines.append(f"AI query log count: {total_queries}. Pending AI flags: {pending_flags}.")
            return lines

        lines.append("ACCESS SCOPE: PUBLIC_COURSE_CATALOG_ONLY")
        lines.append("Privacy rule: do not reveal private student, grade, GPA, or enrollment records.")
        _append_public_course_catalog(db, lines)
        return lines
    finally:
        db.close()


def _append_public_course_catalog(db, lines):
    rows = db.execute(
        """SELECT c.id, c.course_name, c.time_slot, c.start_time, c.end_time,
                  c.capacity, c.enrolled_count, c.status,
                  u.username AS instructor_name
           FROM courses c
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE c.status = 'active'
           ORDER BY c.course_name"""
    ).fetchall()
    lines.append("Public active course catalog:")
    if not rows:
        lines.append("- No active courses.")
    for row in rows:
        seats = (row["capacity"] or 0) - (row["enrolled_count"] or 0)
        schedule = row["time_slot"] or "TBD"
        if row["start_time"] and row["end_time"]:
            schedule = f"{schedule} {row['start_time']}-{row['end_time']}"
        lines.append(
            f"- Course {row['id']}: {row['course_name']}; instructor {row['instructor_name'] or 'TBD'}; "
            f"schedule {schedule}; seats available {seats}/{row['capacity']}."
        )


def _fmt_num(value):
    return "N/A" if value is None else f"{value:.2f}"


def query_gemini_with_role_context(query_text, role, context_lines):
    """Ask Gemini using only role-scoped database context, with no vector search."""
    global _last_query_debug
    _last_query_debug = {
        "raw_distances": [],
        "docs_returned": len(context_lines),
        "docs_passed_threshold": len(context_lines),
    }
    context_block = "\n".join(f"- {line}" for line in context_lines)
    role_ctx = get_role_context(role)
    allowed_topics = ", ".join(role_ctx["topics"])

    prompt = "\n".join([
        "You are the College0 Academic Assistant.",
        f"The logged-in user's role is '{role}'. Allowed topics: {allowed_topics}.",
        "You must answer using ONLY the database context below.",
        "Do not use outside knowledge for College0 facts.",
        "Do not infer or invent grades, GPAs, enrollments, instructors, or student names.",
        "Respect the ACCESS SCOPE and Privacy rule exactly.",
        "If the user asks for information outside their scope, say they do not have access.",
        "If the answer is not present in the context, say the database does not contain that information.",
        "Keep the answer concise and use exact numbers from the context.",
        "",
        "DATABASE CONTEXT:",
        context_block,
        "",
        f"USER QUESTION: {query_text}",
    ])

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip(), "vector_db"
    except Exception:
        return _fallback_answer_from_context(query_text, role, context_lines), "vector_db"


def submit_public_query(query_text):
    """Visitor-safe query path: public catalog context only, no private records."""
    valid, error = validate_query(query_text)
    if not valid:
        return {"error": error, "response": None, "source": None, "query_id": None}
    allowed, deny_reason = filter_query_by_role(query_text, "visitor")
    if not allowed:
        return {"error": deny_reason, "response": None, "source": None, "query_id": None}
    context = build_role_scoped_ai_context(None, "visitor")
    response_text, source = query_gemini_with_role_context(query_text, "visitor", context)
    raw_response_text = response_text
    response_text = apply_taboo_filter(response_text)
    display_query = apply_taboo_filter(query_text)
    return {
        "response": response_text,
        "display_query": display_query,
        "source": source,
        "query_id": None,
        "error": None,
        "hallucination_warning": source == "llm",
        "taboo_filtered": raw_response_text != response_text or display_query != query_text,
        "taboo_count": response_text.count("****") + display_query.count("****"),
        "debug": _last_query_debug.copy(),
    }


def _fallback_answer_from_context(query_text, role, context_lines):
    q = query_text.lower()
    relevant = []
    if any(word in q for word in ("gpa", "grade", "grades", "standing", "credit")):
        relevant = [
            line for line in context_lines
            if any(token in line.lower() for token in ("gpa", "grade", "standing", "credit"))
        ]
    elif any(word in q for word in ("course", "class", "enrolled", "enrollment", "schedule")):
        relevant = [
            line for line in context_lines
            if any(token in line.lower() for token in ("course", "enrollment", "enrolled", "schedule"))
        ]
    if not relevant:
        relevant = context_lines[:12]
    return "Here is the relevant information from the database:\n" + "\n".join(relevant[:18])


def enroll_from_ai(student_id, course_id):
    """Chat-friendly enrollment used by recommendation cards.

    This keeps the user on the assistant page and validates the same important
    rules: active student, active course, not already enrolled, not already
    passed by course code/name, seat availability, max load, and time conflict.
    """
    db = get_db()
    try:
        user = db.execute(
            "SELECT role, status FROM users WHERE id = ?",
            (student_id,),
        ).fetchone()
        if not user or user["role"] != "student":
            return "Student access only.", False
        if user["status"] == "suspended":
            return "Your account is suspended. Please contact the registrar.", False

        course = db.execute(
            "SELECT * FROM courses WHERE id = ? AND status = 'active'",
            (course_id,),
        ).fetchone()
        if not course:
            return "That course is not available for enrollment.", False

        already = db.execute(
            """SELECT 1 FROM enrollments
               WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
            (student_id, course_id),
        ).fetchone()
        if already:
            return "You are already enrolled in this course.", False

        course_code = _course_code(course["course_name"])
        course_key = _course_identity_key(course["course_name"])

        enrolled = db.execute(
            """SELECT c.course_name
               FROM enrollments e
               JOIN courses c ON e.course_id = c.id
               WHERE e.student_id = ? AND e.status = 'enrolled'""",
            (student_id,),
        ).fetchall()
        for row in enrolled:
            if (
                _course_code(row["course_name"]) == course_code
                or _course_identity_key(row["course_name"]) == course_key
            ):
                return "You are already enrolled in an equivalent version of this course.", False

        passed = db.execute(
            """SELECT c.course_name, g.letter_grade
               FROM grades g
               JOIN courses c ON g.course_id = c.id
               WHERE g.student_id = ? AND g.letter_grade != 'F'""",
            (student_id,),
        ).fetchall()
        for row in passed:
            if (
                _course_code(row["course_name"]) == course_code
                or _course_identity_key(row["course_name"]) == course_key
            ):
                return "You already completed this course.", False

        load_count = db.execute(
            """SELECT COUNT(*)
               FROM enrollments e
               JOIN courses c ON e.course_id = c.id
               WHERE e.student_id = ? AND e.status = 'enrolled'
                 AND c.semester_id = ?""",
            (student_id, course["semester_id"]),
        ).fetchone()[0]
        if load_count >= 4:
            return "You already have the maximum of 4 enrolled courses.", False

        if (course["enrolled_count"] or 0) >= (course["capacity"] or 0):
            return "This course is full.", False

        conflict = db.execute(
            """SELECT c.course_name, c.time_slot, c.start_time, c.end_time
               FROM enrollments e
               JOIN courses c ON e.course_id = c.id
               WHERE e.student_id = ? AND e.status = 'enrolled'
                 AND c.semester_id = ?""",
            (student_id, course["semester_id"]),
        ).fetchall()
        new_days, new_start, new_end = _course_time_parts(course)
        for row in conflict:
            old_days, old_start, old_end = _course_time_parts(row)
            if (
                new_days and old_days and new_days & old_days
                and new_start < old_end and old_start < new_end
            ):
                return f"Time conflict with {row['course_name']}.", False

        db.execute(
            "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
            (student_id, course_id),
        )
        db.execute(
            "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
            (course_id,),
        )
        db.commit()
        return f"Enrolled in {course['course_name']}.", True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _course_time_parts(course):
    days = set((course["time_slot"] or "").split()[0].split("/")) if course["time_slot"] else set()
    start = course["start_time"]
    end = course["end_time"]
    if not start or not end:
        parts = (course["time_slot"] or "").split()
        if len(parts) > 1 and "-" in parts[1]:
            start, end = parts[1].split("-", 1)
    return days, _time_to_minutes(start), _time_to_minutes(end)


def _time_to_minutes(value):
    if not value or ":" not in value:
        return 0
    hours, minutes = value.split(":", 1)
    return int(hours) * 60 + int(minutes)


# Keywords that trigger personal-data fetch for students
_PRIVATE_DATA_KEYWORDS = [
    # Broad single-word triggers so natural phrasing like "my current GPA" still matches
    "gpa", "grade", "grades", "enrolled", "enrollment",
    "my course", "my courses", "my schedule",
    "my record", "my transcript", "credits",
    "how am i doing", "what did i get", "academic standing",
    "my standing", "academic summary",
]

# Keywords that trigger academic-data fetch for registrars
_REGISTRAR_DATA_KEYWORDS = [
    "gpa", "grade", "grades", "student", "academic standing",
    "transcript", "enrollment", "enrolled", "performance", "standing",
]

# Keywords that trigger the full student roster (registrar "floodlight" queries)
_REGISTRAR_LIST_KEYWORDS = [
    "list", "all students", "active students", "who is active",
    "who are active", "show all", "show me all", "full roster", "roster",
    "everyone", "every student",
]


def _extract_student_target(query_text, db=None):
    """Parse a registrar query for a specific student reference.

    Priority order:
    1. Numeric ID: "user_id 3", "student id 3", "user 7"
    2. Regex name patterns: "student alice", "alice's gpa", "about charlie", etc.
    3. DB scan fallback: any known student username appearing as a whole word in the query

    Returns (target_id: int|None, target_name: str|None).
    Both None means no specific student mentioned → use aggregate stats.
    """
    # 1. Numeric ID patterns
    id_match = re.search(
        r'\b(?:user_id|student[\s_]id|user)\s*[:#=]?\s*(\d+)',
        query_text, re.IGNORECASE,
    )
    if id_match:
        return int(id_match.group(1)), None

    # 2. Explicit name patterns (possessive expanded to more academic keywords)
    name_match = re.search(
        r"\bstudent\s+(?:named\s+)?([a-zA-Z]\w*)"
        r"|([a-zA-Z]\w*)'s\s+(?:gpa|grade|grades|record|transcript|standing|enrollment|status|info|academic)",
        query_text, re.IGNORECASE,
    )
    if name_match:
        return None, (name_match.group(1) or name_match.group(2))

    # 3. DB scan fallback: match any enrolled student's username as a whole word.
    # Handles bare-name queries like "Tell me about Charlie" or "What about Bob?".
    if db is not None:
        q_lower = query_text.lower()
        students = db.execute(
            "SELECT username FROM users WHERE role = 'student'"
        ).fetchall()
        for s in students:
            name = s["username"].lower()
            if len(name) >= 3 and re.search(r'\b' + re.escape(name) + r'\b', q_lower):
                return None, s["username"]

    return None, None


def _fetch_student_grades(db, student_id):
    """Shared helper: fetch grades and enrollments for one student."""
    grades = db.execute(
        """SELECT c.course_name, g.letter_grade, g.numeric_value
           FROM grades g JOIN courses c ON g.course_id = c.id
           WHERE g.student_id = ?""",
        (student_id,),
    ).fetchall()
    enrollments = db.execute(
        """SELECT c.course_name, c.time_slot
           FROM enrollments e JOIN courses c ON e.course_id = c.id
           WHERE e.student_id = ? AND e.status = 'enrolled'""",
        (student_id,),
    ).fetchall()
    return grades, enrollments


def _format_grades_lines(grades, enrollments, label="This student"):
    lines = []
    if grades:
        avg_gpa = sum(g["numeric_value"] for g in grades) / len(grades)
        grade_str = ", ".join(f"{g['course_name']}: {g['letter_grade']}" for g in grades)
        lines.append(f"{label}'s grades: {grade_str}. GPA: {avg_gpa:.2f}/4.0.")
    if enrollments:
        enroll_str = ", ".join(f"{e['course_name']} ({e['time_slot']})" for e in enrollments)
        lines.append(f"{label}'s current enrollments: {enroll_str}.")
    return lines


def _answer_student_private_query(user_id, role, query_text):
    """Answer student-owned facts directly from SQLite.

    GPA, grades, and enrollment are exact local facts. Sending them through the
    LLM can produce role confusion or policy-style answers, so these stay
    deterministic and use the same "vector_db" source badge as other local data.
    """
    q = query_text.lower()
    asks_private_fact = any(kw in q for kw in _PRIVATE_DATA_KEYWORDS)
    if not asks_private_fact:
        return None

    if role != "student":
        if any(kw in q for kw in ("my gpa", "gpa", "my grade", "my grades")):
            return "Only student accounts have a personal GPA in College0. Please log in as a student to view your GPA."
        return None

    db = get_db()
    try:
        student = db.execute(
            """SELECT semester_gpa, cumulative_gpa, credits_earned, status
               FROM students WHERE id = ?""",
            (user_id,),
        ).fetchone()
        grades, enrollments = _fetch_student_grades(db, user_id)
    finally:
        db.close()

    if not student:
        return "No student academic record was found for your account."

    wants_gpa = "gpa" in q or "how am i doing" in q or "academic summary" in q
    wants_grades = "grade" in q or "grades" in q or "transcript" in q or "what did i get" in q
    wants_enrollment = (
        "course" in q or "courses" in q or "schedule" in q
        or "enrolled" in q or "enrollment" in q
    )

    lines = []
    if wants_gpa or not (wants_grades or wants_enrollment):
        lines.append(
            f"Your cumulative GPA is {(student['cumulative_gpa'] or 0):.2f}/4.0."
        )
        lines.append(
            f"Your semester GPA is {(student['semester_gpa'] or 0):.2f}/4.0."
        )
        lines.append(f"Credits earned: {student['credits_earned'] or 0}.")
        standing = student["status"] or "active"
        lines.append(f"Academic standing: {standing}.")

    if wants_grades:
        if grades:
            lines.append("Your completed course grades:")
            for grade in grades:
                lines.append(f"- {grade['course_name']}: {grade['letter_grade']}")
        else:
            lines.append("No completed grades are on record yet.")

    if wants_enrollment:
        if enrollments:
            lines.append("You are currently enrolled in:")
            for enrollment in enrollments:
                lines.append(
                    f"- {enrollment['course_name']} ({enrollment['time_slot']})"
                )
        else:
            lines.append("You are not currently enrolled in any active courses.")

    return "\n".join(lines)


def _fetch_private_context(user_id, role, query_text):
    """Return a list of trusted fact strings to inject into the LLM prompt.

    Student scope  — strictly scoped to session user_id (cross-student leak impossible).
    Registrar scope — can look up any student by name/ID, or get aggregate stats.
    Data injected here bypasses ChromaDB entirely, so it is never retrievable by
    another user's similarity search.
    """
    if role not in ("student", "registrar", "instructor"):
        return []

    q = query_text.lower()

    # ── Student: own data only ────────────────────────────────────────────────
    if role == "student":
        if not any(kw in q for kw in _PRIVATE_DATA_KEYWORDS):
            return []
        db = get_db()
        try:
            student_rec = db.execute(
                "SELECT cumulative_gpa, status FROM students WHERE id = ?", (user_id,)
            ).fetchone()
            grades, enrollments = _fetch_student_grades(db, user_id)
            lines = []
            if student_rec is not None:
                gpa_val = student_rec["cumulative_gpa"]
                lines.append(f"Your cumulative GPA: {round(gpa_val, 2)}/4.0.")
            if grades:
                grade_str = ", ".join(
                    f"{g['course_name']}: {g['letter_grade']}" for g in grades
                )
                lines.append(f"Your completed course grades: {grade_str}.")
            if enrollments:
                enroll_str = ", ".join(
                    f"{e['course_name']} ({e['time_slot']})" for e in enrollments
                )
                lines.append(f"Your current enrollments: {enroll_str}.")
            else:
                lines.append("No active enrollments found for the current semester.")
            return lines
        finally:
            db.close()

    # ── Instructor: assigned courses and their enrolled students (K-006) ──────
    if role == "instructor":
        db = get_db()
        try:
            courses = db.execute(
                """SELECT id, course_name, time_slot, enrolled_count
                   FROM courses WHERE instructor_id = ? AND status = 'active'""",
                (user_id,),
            ).fetchall()
            if not courses:
                return ["You have no active courses assigned this semester."]
            lines = []
            for c in courses:
                students = db.execute(
                    """SELECT u.username FROM enrollments e
                       JOIN users u ON e.student_id = u.id
                       WHERE e.course_id = ? AND e.status = 'enrolled'""",
                    (c["id"],),
                ).fetchall()
                names = (
                    ", ".join(s["username"] for s in students)
                    if students else "no enrolled students yet"
                )
                lines.append(
                    f"Course '{c['course_name']}' ({c['time_slot']}): "
                    f"{c['enrolled_count']} enrolled. Students: {names}."
                )
            return lines
        finally:
            db.close()

    # ── Registrar: floodgate — always inject the full system snapshot ──────────
    # No keyword or name detection needed. Every registrar query gets the complete
    # student database pre-loaded into context so the LLM never has to "search."
    if role == "registrar":
        db = get_db()
        try:
            students = db.execute(
                """SELECT u.id, u.username,
                          s.cumulative_gpa, s.status AS academic_standing
                   FROM users u
                   LEFT JOIN students s ON u.id = s.id
                   WHERE u.role = 'student'
                   ORDER BY u.username"""
            ).fetchall()

            total_queries = db.execute(
                "SELECT COUNT(*) FROM ai_queries"
            ).fetchone()[0]
            open_flags = db.execute(
                "SELECT COUNT(*) FROM ai_flags WHERE status = 'pending'"
            ).fetchone()[0]

            lines = [f"=== FULL STUDENT DATABASE ({len(students)} students) ==="]
            for s in students:
                sid      = s["id"]
                gpa      = s["cumulative_gpa"]
                # str(round()) avoids trailing zeros (3.90 → 3.9) that tempt rounding
                gpa_str  = str(round(gpa, 2)) if gpa is not None else "N/A"
                standing = s["academic_standing"] or "unknown"

                grades = db.execute(
                    """SELECT c.course_name, g.letter_grade
                       FROM grades g JOIN courses c ON g.course_id = c.id
                       WHERE g.student_id = ?""",
                    (sid,),
                ).fetchall()
                enrollments = db.execute(
                    """SELECT c.course_name, c.time_slot
                       FROM enrollments e JOIN courses c ON e.course_id = c.id
                       WHERE e.student_id = ? AND e.status = 'enrolled'""",
                    (sid,),
                ).fetchall()

                grade_str  = (
                    ", ".join(f"{g['course_name']}: {g['letter_grade']}" for g in grades)
                    if grades else "no grade records"
                )
                enroll_str = (
                    ", ".join(f"{e['course_name']} ({e['time_slot']})" for e in enrollments)
                    if enrollments else "No active enrollments this semester"
                )

                lines.append(
                    f"Student: {s['username']} (ID {sid}) | "
                    f"GPA: {gpa_str}/4.0 | Standing: {standing} | "
                    f"Grades: {grade_str} | Enrollments: {enroll_str}"
                )

            lines.append(
                f"=== SYSTEM STATS: {len(students)} students | "
                f"{total_queries} total AI queries | {open_flags} open flags ==="
            )
            return lines
        finally:
            db.close()

    return []


def get_query_history(user_id, limit=20):
    # L-025: Returns last N ai_queries rows for a user, newest first
    db = get_db()
    try:
        rows = db.execute(
            """SELECT id, query_text, response_text, source, role_at_query, created_at
               FROM ai_queries
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


# ── BLOCK 2: Security & Role-Based Permissions ────────────────────────────────

# "visitor" is a Python-only concept — never stored in database/college0.db.
# Any DB role not in _KNOWN_DB_ROLES is mapped to "visitor" inside submit_query.
_KNOWN_DB_ROLES = {"student", "instructor", "registrar", "suspended", "terminated", "graduated"}

ROLE_CONTEXTS = {
    # Visitor — public-only: course descriptions, available seats, general info
    "visitor": {
        "topics": ["public course descriptions", "available seats", "general college information"],
        "can_see_grades": False, "can_see_enrollment": False,
    },
    # Student — personal scope only: their own GPA/grades, enrolled courses, general academic topics
    "student": {
        "topics": [
            "their own GPA and grades", "their enrolled courses",
            "available courses this semester", "general academic concepts",
            "course recommendations based on their history",
        ],
        "can_see_grades": True, "can_see_enrollment": True,
    },
    # Instructor — academic access: course details, student lists for their classes, grading policies
    "instructor": {
        "topics": [
            "course details and schedules", "student lists for their assigned courses",
            "grading policies", "general academic concepts",
        ],
        "can_see_grades": True, "can_see_enrollment": True,
    },
    # Registrar — full administrative access: any student GPA, all course logs, system exports
    # Matches planning doc: "automatic GPA > 3.0 check" + "full-access dashboard"
    "registrar": {
        "topics": [
            "any student's GPA and academic standing", "all course enrollment logs",
            "system-wide statistics", "AI query exports", "approval and graduation workflows",
        ],
        "can_see_grades": True, "can_see_enrollment": True,
    },
}


def get_role_context(role):
    # K-004: Unknown roles fall back to visitor (most restrictive)
    return ROLE_CONTEXTS.get(role, ROLE_CONTEXTS["visitor"])


_ADMIN_ONLY_PHRASES = [
    "all users", "all students", "delete", "drop table",
    "admin panel", "user list", "all records",
]

# K-004: Private academic keywords — visitors may not query these
_VISITOR_BLOCKED_KEYWORDS = [
    "gpa", "grade", "grades", "my grade",
    "enrollment", "enrolled", "my enrollment",
    "transcript", "my courses", "my schedule",
    "withdraw", "waitlist", "financial aid", "tuition balance",
]

_STUDENT_BULK_BLOCKED = ["list all grades", "dump all", "export all"]


def filter_query_by_role(query_text, role):
    # K-005: Returns (allowed: bool, reason: str).
    # `role` is always effective_role from submit_query — never the raw session value.
    q = query_text.lower()

    if role == "registrar":
        return True, ""

    for phrase in _ADMIN_ONLY_PHRASES:
        if phrase in q:
            return False, "That query is restricted to administrators."

    # K-004: Visitor restriction — only the course catalog, no personal/staff records
    if role == "visitor":
        for keyword in _VISITOR_BLOCKED_KEYWORDS:
            if keyword in q:
                return (
                    False,
                    f"Access restricted: visitors can only query the course catalog and general "
                    f"program information (blocked keyword: '{keyword}'). "
                    f"Please log in with a student or instructor account.",
                )

    if role == "student":
        for phrase in _STUDENT_BULK_BLOCKED:
            if phrase in q:
                return False, "That query is not permitted for student accounts."

    return True, ""


def apply_taboo_filter(text):
    # K-013: Scrub response text using whole-word, case-insensitive regex.
    # Merges the hardcoded TABOO_WORDS baseline with the registrar-managed DB table.
    # Filtered words are replaced with **** so the UI never shows raw taboo content.
    # The filtered string is what gets logged — logs always match the UI.
    db = get_db()
    try:
        db_words = [r["word"] for r in db.execute("SELECT word FROM taboo_words").fetchall()]
    finally:
        db.close()

    all_words = set(w.lower() for w in TABOO_WORDS) | set(w.lower() for w in db_words)
    for word in all_words:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        text = pattern.sub("****", text)
    return text


def filter_taboo_words(text):
    # Legacy alias — kept so any external callers don't break.
    return apply_taboo_filter(text)


def check_user_ai_eligibility(user_id):
    # K-007: Standalone eligibility check (called from routes outside submit_query)
    db = get_db()
    try:
        user = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, "User not found."
        if user["role"] in ("suspended", "terminated", "graduated"):
            return False, f"Access Denied: Your account status '{user['role']}' does not permit AI queries."
        return True, ""
    finally:
        db.close()


def check_rate_limit(user_id, max_per_hour=20):
    # K-008: Returns True if the user is within the hourly query cap
    db = get_db()
    try:
        one_hour_ago = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        count = db.execute(
            "SELECT COUNT(*) FROM ai_queries WHERE user_id = ? AND created_at >= ?",
            (user_id, one_hour_ago),
        ).fetchone()[0]
        return count < max_per_hour
    finally:
        db.close()


def get_all_flags(status_filter=None):
    # K-020: Returns ai_flags rows for the registrar view
    db = get_db()
    try:
        if status_filter:
            rows = db.execute(
                """SELECT f.*, u.username AS flagged_by_name,
                          q.query_text, q.response_text, q.source, q.role_at_query,
                          q.created_at AS query_created_at,
                          owner.username AS query_owner_name
                   FROM ai_flags f
                   JOIN users u ON f.flagged_by = u.id
                   JOIN ai_queries q ON f.query_id = q.id
                   LEFT JOIN users owner ON q.user_id = owner.id
                   WHERE f.status = ?
                   ORDER BY f.created_at DESC""",
                (status_filter,),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT f.*, u.username AS flagged_by_name,
                          q.query_text, q.response_text, q.source, q.role_at_query,
                          q.created_at AS query_created_at,
                          owner.username AS query_owner_name
                   FROM ai_flags f
                   JOIN users u ON f.flagged_by = u.id
                   JOIN ai_queries q ON f.query_id = q.id
                   LEFT JOIN users owner ON q.user_id = owner.id
                   ORDER BY f.created_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def resolve_flag(flag_id, _resolver_user_id):
    # K-022: Marks an ai_flags row as 'reviewed'
    db = get_db()
    try:
        db.execute("BEGIN")
        db.execute("UPDATE ai_flags SET status = 'reviewed' WHERE id = ?", (flag_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── BLOCK 3: The Brain — ChromaDB + Google Gemini ────────────────────────────

_chroma_collection = None
_chroma_ef = None   # stored globally so query_vector_db uses embed_query() task type

# Populated by query_vector_db on every call — read by submit_query for the metadata panel.
# NOT thread-safe under multi-worker deployments; fine for single-threaded dev server.
_last_query_debug = {"raw_distances": [], "docs_returned": 0, "docs_passed_threshold": 0}

# ChromaDB persist dir — resolved from DB_PATH at the top of this file
_CHROMA_PERSIST_DIR = DB_PATH

class SimpleGoogleEmbeddingFunction:
    """Manual wrapper for Google Embeddings to ensure compatibility with Gemini."""
    def __init__(self, api_key, model_name="models/gemini-embedding-001"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self._genai = genai

    def __call__(self, input):
        # Called by ChromaDB for batch document embedding during upsert
        # input is a list of strings; returns a list of embedding vectors
        docs = input if isinstance(input, list) else [input]
        embeddings = []
        for doc in docs:
            response = self._genai.embed_content(
                model="models/gemini-embedding-001",
                content=doc,
                task_type="RETRIEVAL_DOCUMENT",
            )
            embeddings.append(response['embedding'])
        return embeddings

    def embed_query(self, input):
        # Called explicitly for a single query string — returns one flat list of floats
        response = self._genai.embed_content(
            model="models/gemini-embedding-001",
            content=input,
            task_type="RETRIEVAL_QUERY",
        )
        return response['embedding']

    def name(self) -> str:
        return "SimpleGoogleEmbeddingFunction"


def init_vector_db():
    # K-009: Creates/loads ChromaDB collection at app startup.
    # Absolute path used here to guarantee it matches seed_chroma.py exactly,
    # regardless of the working directory at launch time.
    global _chroma_collection, _chroma_ef
    try:
        import chromadb

        os.makedirs(_CHROMA_PERSIST_DIR, exist_ok=True)

        ef = SimpleGoogleEmbeddingFunction(api_key=os.getenv("GOOGLE_API_KEY"))
        _chroma_ef = ef

        client = chromadb.PersistentClient(path=_CHROMA_PERSIST_DIR)
        _chroma_collection = client.get_or_create_collection(
            name="college0_knowledge",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        return True
    except Exception as e:
        _chroma_collection = None
        _chroma_ef = None
        return False


def seed_vector_db():
    # K-010: Reads active courses from database/college0.db and upserts to ChromaDB.
    if _chroma_collection is None:
        return False
    db = get_db()
    try:
        courses = db.execute(
            """SELECT id, course_name, time_slot, day_of_week,
                      start_time, end_time, capacity, enrolled_count
               FROM courses WHERE status = 'active'"""
        ).fetchall()
        docs, ids, metas = [], [], []
        for c in courses:
            seats_left = c["capacity"] - c["enrolled_count"]
            doc = (
                f"Course: {c['course_name']}. "
                f"Schedule: {c['time_slot']}, day {c['day_of_week']}, "
                f"{c['start_time']}–{c['end_time']}. "
                f"Capacity: {c['capacity']} seats, {seats_left} available. "
                f"Course ID: {c['id']}."
            )
            docs.append(doc)
            ids.append(f"course_{c['id']}")
            metas.append({"type": "course", "course_id": c["id"]})
        if docs:
            _chroma_collection.upsert(documents=docs, ids=ids, metadatas=metas)
        return len(docs)
    finally:
        db.close()


def is_relevant_result(distance, max_distance=0.7):
    # K-010: cosine distance threshold — only return high-confidence local answers
    return distance < max_distance


def query_vector_db(query_text, _role, n_results=3):
    global _last_query_debug
    if _chroma_collection is None:
        _last_query_debug = {"raw_distances": [], "docs_returned": 0, "docs_passed_threshold": 0}
        return []
    try:
        # Use embed_query() (retrieval_query task type) for better similarity scores.
        # ChromaDB's __call__ uses retrieval_document task type — wrong for queries.
        if _chroma_ef is not None:
            query_embedding = _chroma_ef.embed_query(query_text)
            results = _chroma_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
            )
        else:
            results = _chroma_collection.query(
                query_texts=[query_text],
                n_results=n_results,
            )
        docs      = results.get("documents", [[]])[0]
        distances = results.get("distances",  [[]])[0]
        relevant_docs = [
            doc for doc, dist in zip(docs, distances) if is_relevant_result(dist)
        ]
        _last_query_debug = {
            "raw_distances":       [round(d, 4) for d in distances],
            "docs_returned":       len(docs),
            "docs_passed_threshold": len(relevant_docs),
        }
        return relevant_docs
    except Exception:
        return []


def query_llm(query_text, context, role, private_context=None):
    # K-012: gemini-2.5-flash — always called, even when ChromaDB returns nothing.
    # private_context: list of strings fetched locally from DB (grades, enrollments).
    # These are injected as trusted facts and never pass through ChromaDB, preventing
    # one student from retrieving another student's data via similarity search.
    all_context = list(context) + (private_context or [])

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        role_ctx       = get_role_context(role)
        allowed_topics = ", ".join(role_ctx["topics"])

        if all_context:
            context_block = "\n".join(f"- {c}" for c in all_context)
            if role == "registrar":
                accuracy_line = (
                    "ROLE: You are the Registrar's Executive Assistant. "
                    "The full student database has been pre-loaded into the context below. "
                    "Use it to answer any question about specific students, lists of students, "
                    "or system-wide statistics with 100% numerical accuracy. "
                    "CRITICAL: Never round GPA values — if the database shows 3.9, "
                    "you must report exactly 3.9, never 4.0."
                )
            else:
                accuracy_line = (
                    "PRECISION REQUIREMENT: Report all numerical values (GPA, grades, scores) "
                    "exactly as given in the context — never round or alter them. "
                    "If context states GPA is 3.9, report exactly 3.9."
                )
            prompt = "\n".join([
                "You are the College0 Academic Assistant.",
                f"The user's role is '{role}'. You may discuss: {allowed_topics}.",
                accuracy_line,
                "Use the verified context below to answer. Do not invent course names, "
                "grades, or seat counts not present in the context.",
                "If the context contains schedule or seat availability, state it explicitly.",
                f"\nContext:\n{context_block}",
                f"\nUser question: {query_text}",
            ])
        else:
            # K-011: No catalog match — intent recognition determines behavior.
            # The LLM is the judge: it must tell a "General Concept" query (e.g.
            # "what is recursion?", "explain GPA calculation") from a "Local Fact"
            # query (e.g. "when is CS101?", "what is my GPA?").
            # General concepts → answer fully from training data.
            # Local facts with no data → defer to registrar office.
            prompt = "\n".join([
                "You are the College0 Academic Assistant.",
                f"The user's role is '{role}'. You may discuss: {allowed_topics}.",
                "",
                "The local course catalog returned no specific results for this query.",
                "Apply the following intent classification to decide how to respond:",
                "",
                "GENERAL CONCEPT (answer fully from training knowledge):",
                "  - Programming topics: recursion, data structures, algorithms, OOP, etc.",
                "  - Math or science concepts: calculus, statistics, etc.",
                "  - Study strategies, academic integrity, how GPAs work in general.",
                "  - General grading scales, academic policies at a high level.",
                "",
                "LOCAL FACT (no data found — defer to registrar):",
                "  - Specific course schedules or office hours at College0.",
                "  - A specific student's grade, GPA, or enrollment status.",
                "  - Exact seat availability or waitlist position.",
                "",
                "Rules:",
                "  - NEVER invent College0-specific data (course names, student names, grades).",
                "  - If it is a general concept, explain it clearly and helpfully.",
                "  - If it is a local fact you cannot find, say so and suggest "
                "contacting the registrar's office.",
                f"\nUser question: {query_text}",
            ])

        model    = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip(), "llm"
    except Exception:
        return (
            "The requested answer could not be generated from the available database context. "
            "Please try a more specific question.",
            "llm",
        )


def attach_hallucination_warning(response_text, source):
    # K-021: Appends disclaimer for LLM responses
    if source == "llm":
        return (
            response_text
            + "\n\n⚠ Note: This response was generated by an AI language model and may not be "
            "fully accurate. Please verify important information with the registrar."
        )
    return response_text


def run_rag_pipeline(query_text, role, private_context=None):
    # K-013: Full RAG pipeline — ChromaDB retrieval then Gemini generation.
    # private_context is pre-fetched personal data (grades/enrollments) injected
    # directly into the prompt — never stored in or retrieved from the vector DB.
    vector_results = query_vector_db(query_text, role)
    response_text, _ = query_llm(query_text, vector_results, role, private_context=private_context)
    source = "vector_db" if vector_results else "llm"
    response_text = attach_hallucination_warning(response_text, source)
    return response_text, source


def refresh_vector_db():
    # K-024: Clears and re-seeds ChromaDB
    if _chroma_collection is None:
        return False
    try:
        existing = _chroma_collection.get()
        if existing["ids"]:
            _chroma_collection.delete(ids=existing["ids"])
        return seed_vector_db()
    except Exception:
        return False


# ── BLOCK 4: Feedback Loop ────────────────────────────────────────────────────

def flag_query(query_id, flagged_by_user_id, reason):
    # K-014: Inserts into ai_flags — returns new flag_id
    db = get_db()
    try:
        db.execute("BEGIN")
        cursor = db.execute(
            "INSERT INTO ai_flags (query_id, flagged_by, reason) VALUES (?, ?, ?)",
            (query_id, flagged_by_user_id, reason.strip()),
        )
        flag_id = cursor.lastrowid
        db.commit()
        return flag_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_flags_for_query(query_id):
    # K-015: Returns ai_flags rows for a specific query
    db = get_db()
    try:
        rows = db.execute(
            """SELECT f.*, u.username AS flagged_by_name
               FROM ai_flags f JOIN users u ON f.flagged_by = u.id
               WHERE f.query_id = ?""",
            (query_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


# ── BLOCK 5: Recommender & Final Testing ─────────────────────────────────────

def _is_intro_course(course_name):
    """True if course name suggests introductory level — used for probation-tier roadmapping."""
    n = course_name.lower()
    return any(kw in n for kw in ["intro", "introduction", "101", "100", "fundamentals", "basic"])


def _infer_difficulty_str(course_name):
    """Returns 'Introductory', 'Intermediate', or 'Advanced' based on course name keywords."""
    n = course_name.lower()
    if any(k in n for k in ["intro", "101", "100", "fundamentals", "basic"]):
        return "Introductory"
    if any(k in n for k in ["20", "21", "22", "23"]):
        return "Intermediate"
    return "Advanced"


def score_courses_for_student(student_id, available_courses):
    # K-019: Returns sorted list of (course_dict, score, reason)
    db = get_db()
    try:
        enrolled_rows = db.execute(
            """SELECT c.id, c.course_name
               FROM enrollments e
               JOIN courses c ON e.course_id = c.id
               WHERE e.student_id = ? AND e.status = 'enrolled'""",
            (student_id,),
        ).fetchall()
        enrolled_ids = {r["id"] for r in enrolled_rows}
        enrolled_keys = {_course_identity_key(r["course_name"]) for r in enrolled_rows}
        enrolled_codes = {_course_code(r["course_name"]) for r in enrolled_rows}

        completed_rows = db.execute(
            """SELECT c.id, c.course_name
               FROM grades g
               JOIN courses c ON g.course_id = c.id
               WHERE g.student_id = ? AND g.letter_grade != 'F'""",
                (student_id,),
        ).fetchall()
        # K-019: also exclude courses the student already passed (grade != F).
        # Use both id and normalized course identity so duplicate seed rows like
        # "CS101" and "CS101 - Intro to Computing" do not get recommended again.
        completed_ids = {r["id"] for r in completed_rows}
        completed_keys = {_course_identity_key(r["course_name"]) for r in completed_rows}
        completed_codes = {_course_code(r["course_name"]) for r in completed_rows}
        grades = db.execute(
            "SELECT numeric_value FROM grades WHERE student_id = ?", (student_id,)
        ).fetchall()
        # numeric_value is on 0.0–4.0 GPA scale (A=4.0, B=3.0, C=2.0, D=1.0, F=0.0)
        avg_gpa = (
            sum(g["numeric_value"] for g in grades) / len(grades) if grades else 2.5
        )
        scored = []
        seen_recommendation_keys = set()
        seen_recommendation_codes = set()
        for course in available_courses:
            course_key = _course_identity_key(course["course_name"])
            course_code = _course_code(course["course_name"])
            if (
                course["id"] in enrolled_ids
                or course["id"] in completed_ids
                or course_key in enrolled_keys
                or course_key in completed_keys
                or course_code in enrolled_codes
                or course_code in completed_codes
                or course_key in seen_recommendation_keys
                or course_code in seen_recommendation_codes
            ):
                continue
            seen_recommendation_keys.add(course_key)
            seen_recommendation_codes.add(course_code)
            # Skip cancelled courses and full courses (belt-and-suspenders — generate_recommendations
            # already filters by status='active', but scenario toggles can change state mid-session)
            if course.get("status") == "cancelled":
                continue
            if course.get("enrolled_count", 0) >= course.get("capacity", 30):
                continue
            score = 50
            if avg_gpa >= 3.5:
                score  += 20
                reason  = "Strong academic record (GPA ≥ 3.5) — challenging course recommended"
            elif avg_gpa >= 2.5:
                score  += 10
                reason  = "Good standing (GPA ≥ 2.5) — course matches your level"
            elif avg_gpa >= 2.0:
                score  += 5
                reason  = "Course available — consider strengthening foundational skills this semester"
            else:
                # Academic probation tier (avg_gpa < 2.0): prioritise introductory courses
                if _is_intro_course(course["course_name"]):
                    score  += 25
                    reason  = (
                        "Academic probation standing — this introductory course is strongly "
                        "recommended to rebuild your GPA. Visit the tutoring center for support."
                    )
                else:
                    score  += 0
                    reason  = (
                        "Academic probation standing — this advanced course may be difficult at "
                        "your current GPA. Introductory courses and tutoring are recommended first."
                    )
            if course.get("enrolled_count", 0) < course.get("capacity", 30):
                score += 5
            scored.append((dict(course), score, reason))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    finally:
        db.close()


def _course_code(course_name):
    return (course_name or "").split(" - ")[0].strip().upper()


def _course_identity_key(course_name):
    name = (course_name or "").lower().strip()
    if " - " in name:
        code, title = name.split(" - ", 1)
        return f"{code.strip()}::{title.strip()}"
    return _course_code(name).lower()


def generate_recommendations(student_id):
    # K-016 / L-027: Scores active courses in the current semester only.
    # Uses the most recently created semester as "current" until get_current_semester() is available.
    db = get_db()
    try:
        # Use the semester that actually contains active courses (not necessarily the latest one).
        # Avoids the case where a newly created setup-period semester has no courses yet.
        sem_row = db.execute(
            "SELECT semester_id FROM courses WHERE status='active' GROUP BY semester_id ORDER BY semester_id DESC LIMIT 1"
        ).fetchone()
        if not sem_row:
            return []
        courses = db.execute(
            """SELECT id, course_name,
                      CASE
                        WHEN start_time IS NOT NULL AND end_time IS NOT NULL
                          THEN time_slot || ' ' || start_time || '-' || end_time
                        ELSE time_slot
                      END AS time_slot,
                      capacity, enrolled_count, status
               FROM courses
               WHERE status = 'active' AND semester_id = ?
               ORDER BY
                 CASE WHEN course_name LIKE '% - %' THEN 0 ELSE 1 END,
                 course_name""",
            (sem_row["semester_id"],),
        ).fetchall()
        scored = score_courses_for_student(student_id, [dict(c) for c in courses])
        return [
            {"course": course, "score": score, "reason": reason}
            for course, score, reason in scored[:5]
        ]
    finally:
        db.close()


def save_recommendations(student_id, recommendations):
    # K-017: Persists recommendations to DB, clearing old ones first
    db = get_db()
    try:
        db.execute("BEGIN")
        db.execute("DELETE FROM recommendations WHERE student_id = ?", (student_id,))
        for rec in recommendations:
            db.execute(
                "INSERT INTO recommendations (student_id, course_id, reason) VALUES (?, ?, ?)",
                (student_id, rec["course"]["id"], rec["reason"]),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_recommendations(student_id):
    # K-018: Returns saved recommendations joined with course info
    db = get_db()
    try:
        rows = db.execute(
            """SELECT r.id, r.reason, r.generated_at,
                      c.id AS course_id, c.course_name, c.time_slot
               FROM recommendations r
               JOIN courses c ON r.course_id = c.id
               WHERE r.student_id = ?
               ORDER BY r.generated_at DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def export_query_log_csv(output_path):
    # K-025: Writes all ai_queries to CSV
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, user_id, query_text, response_text, source, role_at_query, created_at FROM ai_queries"
        ).fetchall()
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "user_id", "query_text", "response_text",
                "source", "role_at_query", "created_at",
            ])
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])
        return len(rows)
    finally:
        db.close()


def scrub_existing_query_log():
    # One-time retroactive cleanup — applies apply_taboo_filter to every existing
    # ai_queries row so historical records match the current filter rules.
    db = get_db()
    try:
        rows = db.execute("SELECT id, query_text, response_text FROM ai_queries").fetchall()
        updated = 0
        db.execute("BEGIN")
        for row in rows:
            clean_query    = apply_taboo_filter(row["query_text"])
            clean_response = apply_taboo_filter(row["response_text"] or "")
            if clean_query != row["query_text"] or clean_response != (row["response_text"] or ""):
                db.execute(
                    "UPDATE ai_queries SET query_text = ?, response_text = ? WHERE id = ?",
                    (clean_query, clean_response, row["id"]),
                )
                updated += 1
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_smoke_tests():
    # L-027: Quick sanity check on all AI functions
    results = {}
    checks = {
        "validate_query":      lambda: validate_query("test query")[0],
        "get_query_history":   lambda: bool(get_query_history(1, limit=1) is not None),
        "get_role_context":    lambda: bool(get_role_context("student")),
        "filter_query_by_role":lambda: filter_query_by_role("What courses?", "student")[0],
        "visitor_block":       lambda: not filter_query_by_role("What is my GPA?", "visitor")[0],
    }
    for name, fn in checks.items():
        try:
            results[name] = "pass" if fn() else "fail"
        except Exception as e:
            results[name] = f"error: {e}"
    return results


def test_rag_pipeline_integration():
    # L-028: Submits a test query end-to-end and verifies DB row created
    db = get_db()
    try:
        student = db.execute("SELECT id FROM users WHERE role='student' LIMIT 1").fetchone()
    finally:
        db.close()

    if not student:
        return {"status": "fail", "error": "No student user in database/college0.db"}

    result = submit_query(student["id"], "student", "What computer science courses are available?")
    if result.get("query_id"):
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM ai_queries WHERE id = ?", (result["query_id"],)
            ).fetchone()
            return {
                "status": "pass",
                "query_id": result["query_id"],
                "source":   result["source"],
                "db_row":   row is not None,
            }
        finally:
            db.close()
    return {"status": "fail", "error": result.get("error")}


def test_query_throughput(n=10):
    # L-029: Returns average response time in ms over N queries
    db = get_db()
    try:
        student = db.execute("SELECT id FROM users WHERE role='student' LIMIT 1").fetchone()
        uid = student["id"] if student else 1
    finally:
        db.close()

    times = []
    for i in range(n):
        t0 = time.time()
        submit_query(uid, "student", f"Test query number {i}")
        times.append((time.time() - t0) * 1000)
    return round(sum(times) / len(times), 2)


# ── Modular Routing ───────────────────────────────────────────────────────────

def register_ai_routes(app):
    """Plug-and-play: call once with any Flask app to mount all /ai/* routes.

    Importing Flask utilities locally keeps this module usable without Flask
    (e.g. in unit tests or the seeder). All AI business-logic functions called
    from inside the route closures are resolved from this module's own global
    scope — no imports needed inside the closures.
    """
    from flask import (
        render_template, request, redirect, url_for,
        session, send_file, after_this_request,
    )
    import tempfile
    import os as _os
    from datetime import datetime as _dt

    # Runtime migration: add helpful column to ai_queries if not yet present
    _db = get_db()
    try:
        _db.execute("ALTER TABLE ai_queries ADD COLUMN helpful INTEGER DEFAULT NULL")
        _db.commit()
    except Exception:
        pass  # column already exists; safe to ignore
    finally:
        _db.close()

    # ── Main assistant route (ChatGPT-style) ─────────────────────────────────

    @app.route('/ai/assistant')
    def ai_assistant():
        if 'user_id' not in session:
            return render_template('ai/assistant.html',
                role='visitor', username='Guest',
                history=[], pending_flags=[],
                access_denied=False,
            )
        user_id  = session['user_id']
        role     = session.get('role', 'visitor')
        username = session.get('username', '')

        eligible, _ = check_user_ai_eligibility(user_id)
        if not eligible:
            return render_template('ai/assistant.html',
                role=role, username=username,
                history=[], pending_flags=[],
                access_denied=True,
            ), 403

        history       = get_query_history(user_id, limit=15)
        pending_flags = get_all_flags(status_filter='pending') if role == 'registrar' else []

        return render_template('ai/assistant.html',
            role=role, username=username,
            history=history, pending_flags=pending_flags,
            access_denied=False,
        )

    # Legacy /ai/query → redirect
    @app.route('/ai/query', methods=['GET', 'POST'])
    def ai_query():
        return redirect(url_for('ai_assistant'))

    @app.route('/ai/history')
    def ai_history():
        if 'user_id' not in session:
            return redirect(url_for('home'))
        return redirect(url_for('ai_assistant'))

    @app.route('/ai/query/submit', methods=['POST'])
    def ai_query_submit():
        from flask import jsonify
        if 'user_id' not in session:
            data = request.get_json(silent=True) or {}
            query_text = data.get('query_text', request.form.get('query_text', '')).strip()
            return jsonify(submit_public_query(query_text))
        eligible, deny_reason = check_user_ai_eligibility(session['user_id'])
        if not eligible:
            return jsonify({'error': deny_reason}), 403
        data = request.get_json(silent=True) or {}
        query_text = data.get('query_text', request.form.get('query_text', '')).strip()
        user_id = session['user_id']
        role    = session.get('role', 'visitor')
        active_student_id = None
        if role == 'registrar':
            mentioned = find_student_reference(query_text)
            if mentioned:
                session['ai_active_student_id'] = mentioned
            active_student_id = session.get('ai_active_student_id')
        result  = submit_query(user_id, role, query_text, active_student_id=active_student_id)
        if role == 'registrar' and result.get('active_student_id'):
            session['ai_active_student_id'] = result['active_student_id']
        # Attach structured recommendation cards when applicable
        if role == 'student' and _is_recommendation_query(query_text) and not result.get('error'):
            raw_recs = generate_recommendations(user_id)
            result['recommendation_cards'] = [
                {
                    'id':          r['course']['id'],
                    'course_name': r['course']['course_name'],
                    'time_slot':   r['course'].get('time_slot') or 'TBD',
                    'reason':      r['reason'],
                    'difficulty':  _infer_difficulty_str(r['course']['course_name']),
                }
                for r in raw_recs
            ]
        elif role == 'registrar' and session.get('ai_active_student_id') and _is_recommendation_query(query_text) and not result.get('error'):
            reg_student_id = session['ai_active_student_id']
            raw_recs = generate_recommendations(reg_student_id)
            active_name = get_student_username(reg_student_id)
            result['recommendation_cards'] = [
                {
                    'id':          r['course']['id'],
                    'course_name': r['course']['course_name'],
                    'time_slot':   r['course'].get('time_slot') or 'TBD',
                    'reason':      f"For {active_name}: {r['reason']}" if active_name else r['reason'],
                    'difficulty':  _infer_difficulty_str(r['course']['course_name']),
                    'student_id':  reg_student_id,
                }
                for r in raw_recs
            ]
        return jsonify(result)

    @app.route('/ai/query/<int:query_id>/feedback', methods=['POST'])
    def ai_query_feedback(query_id):
        from flask import jsonify
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        data = request.get_json(silent=True) or {}
        try:
            helpful_val = int(data.get('helpful', request.form.get('helpful', '')))
        except (ValueError, TypeError):
            return jsonify({'error': 'helpful must be 0 or 1'}), 400
        if helpful_val not in (0, 1):
            return jsonify({'error': 'helpful must be 0 or 1'}), 400
        _db = get_db()
        try:
            _db.execute("BEGIN")
            _db.execute(
                "UPDATE ai_queries SET helpful = ? WHERE id = ? AND user_id = ?",
                (helpful_val, query_id, session['user_id']),
            )
            _db.commit()
        except Exception:
            _db.rollback()
            return jsonify({'error': 'DB error'}), 500
        finally:
            _db.close()
        return jsonify({'ok': True, 'query_id': query_id, 'helpful': helpful_val})

    # ── Flagging ──────────────────────────────────────────────────────────────

    @app.route('/ai/flag/<int:query_id>')
    def ai_flag_page(query_id):
        if 'user_id' not in session:
            return redirect(url_for('home'))
        _db = get_db()
        try:
            q = _db.execute(
                "SELECT id, query_text, source FROM ai_queries WHERE id = ? AND user_id = ?",
                (query_id, session['user_id']),
            ).fetchone()
        finally:
            _db.close()
        if not q:
            return redirect(url_for('ai_assistant'))
        return render_template('ai/flag.html',
            query=dict(q),
            role=session.get('role', 'visitor'),
            username=session.get('username', ''),
        )

    @app.route('/ai/query/<int:query_id>/flag', methods=['POST'])
    def ai_flag_query(query_id):
        if 'user_id' not in session:
            return redirect(url_for('home'))
        reason = request.form.get('reason', '').strip()
        if reason:
            flag_query(query_id, session['user_id'], reason)
        return redirect(url_for('ai_assistant'))

    @app.route('/ai/flags')
    def ai_flags():
        if 'user_id' not in session or session.get('role') != 'registrar':
            return redirect(url_for('home'))
        status_filter = request.args.get('status') or 'pending'
        if status_filter not in ('pending', 'reviewed', 'all'):
            status_filter = 'pending'
        flags = get_all_flags(None if status_filter == 'all' else status_filter)
        return render_template('ai/flags.html',
            role=session.get('role', 'visitor'),
            username=session.get('username', ''),
            flags=flags,
            status_filter=status_filter,
        )

    @app.route('/ai/flags/<int:flag_id>/resolve', methods=['POST'])
    def ai_resolve_flag(flag_id):
        if 'user_id' not in session or session.get('role') != 'registrar':
            return redirect(url_for('home'))
        resolve_flag(flag_id, session['user_id'])
        return redirect(url_for('ai_flags'))

    # ── K-025: Registrar CSV Export ───────────────────────────────────────────

    @app.route('/ai/export')
    def ai_export_queries():
        if 'user_id' not in session or session.get('role') != 'registrar':
            return redirect(url_for('home'))
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.csv', prefix='ai_queries_')
        _os.close(tmp_fd)

        @after_this_request
        def _cleanup(response):
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass
            return response

        export_query_log_csv(tmp_path)
        filename = f"ai_queries_{_dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(tmp_path, mimetype='text/csv',
                         as_attachment=True, download_name=filename)

    # ── Recommendations ───────────────────────────────────────────────────────

    @app.route('/ai/recommendations')
    def ai_recommendations():
        if 'user_id' not in session or session.get('role') != 'student':
            return redirect(url_for('home'))
        user_id = session['user_id']
        recs = generate_recommendations(user_id)

        db = get_db()
        try:
            student = db.execute(
                "SELECT cumulative_gpa, status FROM students WHERE id = ?",
                (user_id,),
            ).fetchone()
            completed = db.execute(
                "SELECT COUNT(*) FROM grades WHERE student_id = ? AND letter_grade != 'F'",
                (user_id,),
            ).fetchone()[0]
            total = db.execute(
                "SELECT COUNT(*) FROM courses WHERE status = 'active'",
            ).fetchone()[0]
        finally:
            db.close()

        gpa = student["cumulative_gpa"] if student else 0.0
        standing = "Good Standing" if gpa >= 2.0 else "Academic Probation"
        decorated_recs = []
        for rec in recs:
            item = dict(rec)
            item["difficulty"] = _infer_difficulty_str(rec["course"]["course_name"])
            item["instructor"] = "TBD"
            decorated_recs.append(item)

        return render_template(
            'ai/recommendations.html',
            username=session.get('username', ''),
            recommendations=decorated_recs,
            profile={
                "gpa": gpa,
                "completed": completed,
                "total": max(total, completed),
                "standing": standing,
            },
        )

    @app.route('/ai/recommendations/refresh', methods=['POST'])
    def ai_recommendations_refresh():
        if 'user_id' not in session or session.get('role') != 'student':
            return redirect(url_for('home'))
        refresh_vector_db()
        recs = generate_recommendations(session['user_id'])
        save_recommendations(session['user_id'], recs)
        return redirect(url_for('ai_assistant'))

    @app.route('/ai/recommendations/inline')
    def ai_recommendations_inline():
        from flask import jsonify
        if 'user_id' not in session or session.get('role') != 'student':
            return jsonify({'error': 'Student access only'}), 403
        raw_recs = generate_recommendations(session['user_id'])
        cards = [
            {
                'id':          r['course']['id'],
                'course_name': r['course']['course_name'],
                'time_slot':   r['course'].get('time_slot') or 'TBD',
                'reason':      r['reason'],
                'difficulty':  _infer_difficulty_str(r['course']['course_name']),
            }
            for r in raw_recs
        ]
        return jsonify({'cards': cards})

    @app.route('/ai/enroll/<int:course_id>', methods=['POST'])
    def ai_enroll_course(course_id):
        from flask import jsonify
        if 'user_id' not in session:
            return jsonify({'error': 'Student or registrar access only'}), 403
        role = session.get('role')
        if role == 'student':
            target_student_id = session['user_id']
        elif role == 'registrar':
            data = request.get_json(silent=True) or {}
            target_student_id = data.get('student_id') or session.get('ai_active_student_id')
            if not target_student_id:
                return jsonify({'error': 'No student specified — mention a student name in your query first'}), 400
        else:
            return jsonify({'error': 'Student or registrar access only'}), 403
        msg, ok = enroll_from_ai(target_student_id, course_id)
        return jsonify({'message': msg, 'ok': ok}), (200 if ok else 400)
