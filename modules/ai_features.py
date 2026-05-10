import os
import csv
import time
from datetime import datetime, timedelta, timezone
from database.db import get_db

# ── BLOCK 1: UI, Query Logging & Rollback Safety ──────────────────────────────

def validate_query(query_text):
    # K-001: Input validation — returns (True, None) or (False, error_message)
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
            (user_id, query_text.strip(), response_text, source, role_at_query)
        )
        query_id = cursor.lastrowid
        db.commit()
        return query_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def submit_query(user_id, _role, query_text):
    # K-003: Single entry point — all security gates run here before the RAG pipeline.
    # `role` is accepted from the caller for API compatibility but is NEVER trusted for
    # security decisions — we always fetch the current role from the DB (K-007 fix).

    # K-001: Input validation first — cheapest check, no DB hit
    valid, error = validate_query(query_text)
    if not valid:
        return {"error": error, "response": None, "source": None, "query_id": None}

    # K-007 / Source-of-Truth fix: fetch live role from DB, ignore session-passed role
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
    _BLOCKED = ("suspended", "terminated", "graduated")
    if fresh_role in _BLOCKED:
        return {
            "error": f"AI access is not available for {fresh_role} accounts.",
            "response": None, "source": None, "query_id": None,
        }

    # K-008: Rate limit — 20 queries per rolling hour
    if not check_rate_limit(user_id):
        return {
            "error": "Hourly query limit reached (20/hour). Please try again later.",
            "response": None, "source": None, "query_id": None,
        }

    # K-005: Role filter — uses fresh_role, NOT the session-passed role
    allowed, deny_reason = filter_query_by_role(query_text, fresh_role)
    if not allowed:
        return {"error": deny_reason, "response": None, "source": None, "query_id": None}

    # Block 3 RAG pipeline (wired in Block 3; stub response for now)
    response_text = f"[AI stub] You asked: {query_text.strip()}"
    source = "vector_db"

    # K-006: Strip taboo words from response before logging or displaying
    response_text = filter_taboo_words(response_text)

    query_id = log_query(user_id, query_text, response_text, source, fresh_role)
    return {"response": response_text, "source": source, "query_id": query_id, "error": None}


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
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


# ── BLOCK 2: Security & Role-Based Permissions ────────────────────────────────

ROLE_CONTEXTS = {
    "visitor":    {"topics": ["courses", "programs", "campus info"], "can_see_grades": False, "can_see_enrollment": False},
    "student":    {"topics": ["courses", "grades", "enrollment", "recommendations"], "can_see_grades": True, "can_see_enrollment": True},
    "instructor": {"topics": ["courses", "grades", "students", "schedules"], "can_see_grades": True, "can_see_enrollment": True},
    "registrar":  {"topics": ["all"], "can_see_grades": True, "can_see_enrollment": True},
}


def get_role_context(role):
    # K-004: Returns allowed topic dict for the given role
    return ROLE_CONTEXTS.get(role, ROLE_CONTEXTS["visitor"])


_ADMIN_ONLY_PHRASES = [
    "all users", "all students", "delete", "drop table",
    "admin panel", "user list", "all records",
]

# K-005: Private academic keywords visitors must never see
_VISITOR_PRIVATE_KEYWORDS = [
    "gpa", "grade", "grades", "my grade",
    "enrollment", "enrolled", "my enrollment",
    "transcript", "my courses", "my schedule",
    "withdraw", "waitlist", "financial aid", "tuition balance",
]

# Topics that students/instructors cannot bulk-export
_STUDENT_BULK_BLOCKED = [
    "list all grades", "dump all", "export all",
]


def filter_query_by_role(query_text, role):
    # K-005: Returns (allowed: bool, reason: str).
    # fresh_role from the DB is passed in — never the session value.
    # Any unrecognised role is treated as visitor (most restrictive).
    q = query_text.lower()

    # Registrar has unrestricted AI access
    if role == "registrar":
        return True, ""

    # Block admin-only operations for every non-registrar role
    for phrase in _ADMIN_ONLY_PHRASES:
        if phrase in q:
            return False, "That query is restricted to administrators."

    # Visitor (or any unrecognised role) — block all private academic data keywords
    known_roles = ("student", "instructor", "registrar", "suspended", "terminated", "graduated")
    if role not in known_roles or role == "visitor":
        for keyword in _VISITOR_PRIVATE_KEYWORDS:
            if keyword in q:
                return (
                    False,
                    f"Role restricted: visitors cannot query private academic data "
                    f"(matched keyword: '{keyword}'). Please log in with a student or instructor account.",
                )

    # Students cannot bulk-export data
    if role == "student":
        for phrase in _STUDENT_BULK_BLOCKED:
            if phrase in q:
                return False, "That query is not permitted for student accounts."

    return True, ""


def filter_taboo_words(text):
    # K-006: Replaces taboo words (from DB) with [FILTERED] in AI responses
    db = get_db()
    try:
        rows = db.execute("SELECT word FROM taboo_words").fetchall()
        for row in rows:
            word = row["word"]
            text = text.replace(word, "[FILTERED]")
            text = text.replace(word.capitalize(), "[FILTERED]")
            text = text.replace(word.upper(), "[FILTERED]")
        return text
    finally:
        db.close()


def check_user_ai_eligibility(user_id):
    # K-007: Blocks suspended/terminated/graduated users from AI access
    db = get_db()
    try:
        user = db.execute("SELECT role, status FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, "User not found."
        blocked_roles = ("suspended", "terminated", "graduated")
        if user["role"] in blocked_roles:
            return False, f"AI access is not available for {user['role']} accounts."
        return True, ""
    finally:
        db.close()


def check_rate_limit(user_id, max_per_hour=20):
    # K-008: Returns (allowed: bool) — max N queries per rolling hour
    db = get_db()
    try:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        count = db.execute(
            "SELECT COUNT(*) FROM ai_queries WHERE user_id = ? AND created_at >= ?",
            (user_id, one_hour_ago)
        ).fetchone()[0]
        return count < max_per_hour
    finally:
        db.close()


def get_all_flags(status_filter=None):
    # K-020: Returns ai_flags rows; registrar/admin view
    db = get_db()
    try:
        if status_filter:
            rows = db.execute(
                """SELECT f.*, u.username AS flagged_by_name, q.query_text
                   FROM ai_flags f
                   JOIN users u ON f.flagged_by = u.id
                   JOIN ai_queries q ON f.query_id = q.id
                   WHERE f.status = ?
                   ORDER BY f.created_at DESC""",
                (status_filter,)
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT f.*, u.username AS flagged_by_name, q.query_text
                   FROM ai_flags f
                   JOIN users u ON f.flagged_by = u.id
                   JOIN ai_queries q ON f.query_id = q.id
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
        db.execute(
            "UPDATE ai_flags SET status = 'reviewed' WHERE id = ?",
            (flag_id,)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── BLOCK 3: The Brain — ChromaDB + OpenAI + Filters ─────────────────────────

_chroma_collection = None


def init_vector_db():
    # K-009: Creates/loads the ChromaDB collection (call once at app startup)
    global _chroma_collection
    try:
        import chromadb
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        client = chromadb.PersistentClient(path=persist_dir)
        _chroma_collection = client.get_or_create_collection("college0_knowledge")
        return True
    except Exception:
        _chroma_collection = None
        return False


def seed_vector_db():
    # K-010: Reads courses from DB and upserts embeddings into ChromaDB
    if _chroma_collection is None:
        return False
    db = get_db()
    try:
        courses = db.execute(
            "SELECT id, course_name, time_slot, day_of_week FROM courses WHERE status = 'active'"
        ).fetchall()
        docs, ids, metas = [], [], []
        for c in courses:
            doc = (
                f"Course: {c['course_name']}. "
                f"Schedule: {c['time_slot']} (day {c['day_of_week']}). "
                f"Course ID: {c['id']}."
            )
            docs.append(doc)
            ids.append(f"course_{c['id']}")
            metas.append({"type": "course", "course_id": c["id"]})
        if docs:
            _chroma_collection.upsert(documents=docs, ids=ids, metadatas=metas)
        return True
    finally:
        db.close()


def is_relevant_result(similarity_score, threshold=0.75):
    # K-023: True if vector result meets quality threshold (ChromaDB returns distance, lower = better)
    return similarity_score <= (1.0 - threshold)


def query_vector_db(query_text, _role, n_results=3):
    # K-011: Returns list of relevant document strings or empty list
    if _chroma_collection is None:
        return []
    try:
        results = _chroma_collection.query(query_texts=[query_text], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        relevant = [doc for doc, dist in zip(docs, distances) if is_relevant_result(dist)]
        return relevant
    except Exception:
        return []


def query_llm(query_text, context, role):
    # K-012: OpenAI fallback when vector DB has no good match
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        role_context = get_role_context(role)
        system_prompt = (
            f"You are an academic assistant for College0. "
            f"The user is a {role}. "
            f"Answer only about: {', '.join(role_context['topics'])}. "
            f"Be concise and factual."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{chr(10).join(context)}"})
        messages.append({"role": "user", "content": query_text})
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages, max_tokens=400)
        return response.choices[0].message.content.strip(), "llm"
    except Exception:
        return "AI service is temporarily unavailable. Please try again later.", "llm"


def attach_hallucination_warning(response_text, source):
    # K-021: Appends disclaimer when response came from LLM fallback
    if source == "llm":
        return (
            response_text
            + "\n\n⚠ Note: This response was generated by an AI language model and may not be "
            "fully accurate. Please verify important information with the registrar."
        )
    return response_text


def run_rag_pipeline(query_text, role):
    # K-013: Full pipeline — vector DB first, LLM fallback
    vector_results = query_vector_db(query_text, role)
    if vector_results:
        response = "Based on our course catalog:\n" + "\n".join(f"- {r}" for r in vector_results)
        return response, "vector_db"
    response, source = query_llm(query_text, [], role)
    return response, source


# ── BLOCK 4: Feedback Loop ────────────────────────────────────────────────────

def flag_query(query_id, flagged_by_user_id, reason):
    # K-014: Inserts into ai_flags — returns new flag_id
    db = get_db()
    try:
        db.execute("BEGIN")
        cursor = db.execute(
            "INSERT INTO ai_flags (query_id, flagged_by, reason) VALUES (?, ?, ?)",
            (query_id, flagged_by_user_id, reason.strip())
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
            (query_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def refresh_vector_db():
    # K-024: Clears and re-seeds ChromaDB after course catalog changes
    if _chroma_collection is None:
        return False
    try:
        existing = _chroma_collection.get()
        if existing["ids"]:
            _chroma_collection.delete(ids=existing["ids"])
        return seed_vector_db()
    except Exception:
        return False


# ── BLOCK 5: Recommender & Final Testing ─────────────────────────────────────

def score_courses_for_student(student_id, available_courses):
    # K-019: Returns sorted list of (course_dict, score, reason) — avoid duplicates, grade-appropriate
    db = get_db()
    try:
        enrolled_ids = {
            r["course_id"] for r in db.execute(
                "SELECT course_id FROM enrollments WHERE student_id = ? AND status = 'enrolled'",
                (student_id,)
            ).fetchall()
        }
        grades = db.execute(
            "SELECT numeric_value FROM grades WHERE student_id = ?", (student_id,)
        ).fetchall()
        avg_grade = (
            sum(g["numeric_value"] for g in grades) / len(grades) if grades else 75.0
        )
        scored = []
        for course in available_courses:
            if course["id"] in enrolled_ids:
                continue
            score = 50
            reason = "Available course"
            if avg_grade >= 90:
                score += 20
                reason = "Strong academic record — challenging course recommended"
            elif avg_grade >= 75:
                score += 10
                reason = "Good standing — course matches your level"
            else:
                score += 5
                reason = "Course available for your enrollment"
            if course.get("enrolled_count", 0) < course.get("capacity", 30):
                score += 5
            scored.append((dict(course), score, reason))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    finally:
        db.close()


def generate_recommendations(student_id):
    # K-016: Queries active courses and scores them for the student
    db = get_db()
    try:
        courses = db.execute(
            """SELECT id, course_name, time_slot, capacity, enrolled_count
               FROM courses WHERE status = 'active'"""
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
                (student_id, rec["course"]["id"], rec["reason"])
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
            (student_id,)
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
            writer = csv.DictWriter(f, fieldnames=["id", "user_id", "query_text", "response_text", "source", "role_at_query", "created_at"])
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])
        return len(rows)
    finally:
        db.close()


def run_smoke_tests():
    # L-027: Returns dict of {route_name: status} for all AI routes
    results = {}
    try:
        valid, _ = validate_query("test query")
        results["validate_query"] = "pass" if valid else "fail"
    except Exception as e:
        results["validate_query"] = f"error: {e}"
    try:
        get_query_history(1, limit=1)
        results["get_query_history"] = "pass"
    except Exception as e:
        results["get_query_history"] = f"error: {e}"
    try:
        context = get_role_context("student")
        results["get_role_context"] = "pass" if context else "fail"
    except Exception as e:
        results["get_role_context"] = f"error: {e}"
    return results


def test_rag_pipeline_integration():
    # L-028: Submits a test query end-to-end and verifies DB row created
    test_user_id = 1
    test_role = "student"
    test_query = "What computer science courses are available?"
    result = submit_query(test_user_id, test_role, test_query)
    if result.get("query_id"):
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM ai_queries WHERE id = ?", (result["query_id"],)
            ).fetchone()
            return {"status": "pass", "query_id": result["query_id"], "source": result["source"], "db_row_found": row is not None}
        finally:
            db.close()
    return {"status": "fail", "error": result.get("error")}


def test_query_throughput(n=10):
    # L-029: Submits N test queries and returns average response time in ms
    times = []
    for i in range(n):
        start = time.time()
        submit_query(1, "student", f"Test query number {i}")
        times.append((time.time() - start) * 1000)
    return round(sum(times) / len(times), 2)
