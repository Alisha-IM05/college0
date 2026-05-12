import os
import re
import csv
import time
from datetime import datetime, timedelta, timezone
from database.db import get_db

# K-013: Hardcoded baseline — always filtered regardless of DB table contents.
# The DB taboo_words table adds to this list at runtime (managed by the registrar).
TABOO_WORDS = [
    "stupid", "idiot", "dumb", "moron", "hate",
    "worthless", "incompetent", "cheat", "cheater",
    "plagiarize", "plagiarism", "expel", "expelled",
    "loser", "failure",
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


def submit_query(user_id, _session_role, query_text):
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
            "error": f"AI access is not available for {fresh_role} accounts.",
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

    # K-016/K-019: If a student asks for recommendations, generate them inline
    if effective_role == "student" and _is_recommendation_query(query_text):
        recs = generate_recommendations(user_id)
        if recs:
            lines = "\n".join(
                f"- {r['course']['course_name']}: {r['reason']}" for r in recs
            )
            response_text = f"Based on your academic profile, here are your recommended courses:\n{lines}"
            source = "vector_db"
        else:
            response_text, source = run_rag_pipeline(query_text, effective_role)
    else:
        # Privacy: fetch the caller's own private data locally and inject it as
        # trusted context — it bypasses the vector DB so cross-user leakage is impossible.
        private_ctx = _fetch_private_context(user_id, effective_role, query_text)
        response_text, source = run_rag_pipeline(query_text, effective_role, private_context=private_ctx)

    # K-013: Scrub taboo words from both sides before logging.
    # query_text was already used for RAG search above (original needed for accuracy).
    # logged_query is the sanitized version stored in ai_queries — DB always matches UI.
    response_text  = apply_taboo_filter(response_text)
    logged_query   = apply_taboo_filter(query_text)

    query_id = log_query(user_id, logged_query, response_text, source, effective_role)
    return {"response": response_text, "source": source, "query_id": query_id, "error": None}


def _is_recommendation_query(query_text):
    # Helper: True if the query is asking for course recommendations
    q = query_text.lower()
    keywords = ["recommend", "suggestion", "what course should", "which course", "should i take"]
    return any(kw in q for kw in keywords)


_PRIVATE_DATA_KEYWORDS = [
    "my gpa", "my grade", "my grades", "my course", "my courses",
    "my schedule", "my enrollment", "my record", "my transcript",
    "how am i doing", "what did i get",
]


def _fetch_private_context(user_id, role, query_text):
    # Privacy enforcement: fetch the logged-in student's own data from DB and return it
    # as trusted context strings. This data is injected directly into the LLM prompt —
    # it NEVER enters ChromaDB, so it is invisible to other users' similarity searches.
    # Registrars get aggregate access; students are strictly scoped to their own user_id.
    if role not in ("student", "registrar"):
        return []
    q = query_text.lower()
    if role == "student" and not any(kw in q for kw in _PRIVATE_DATA_KEYWORDS):
        return []

    db = get_db()
    try:
        if role == "student":
            grades = db.execute(
                """SELECT c.course_name, g.letter_grade, g.numeric_value
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ?""",
                (user_id,),
            ).fetchall()
            enrollments = db.execute(
                """SELECT c.course_name, c.time_slot, e.status
                   FROM enrollments e JOIN courses c ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'""",
                (user_id,),
            ).fetchall()
            lines = []
            if grades:
                avg_gpa = sum(g["numeric_value"] for g in grades) / len(grades)
                grade_str = ", ".join(
                    f"{g['course_name']}: {g['letter_grade']}" for g in grades
                )
                lines.append(
                    f"This student's grades (their own data only): {grade_str}. "
                    f"GPA: {avg_gpa:.2f}/4.0."
                )
            if enrollments:
                enroll_str = ", ".join(
                    f"{e['course_name']} ({e['time_slot']})" for e in enrollments
                )
                lines.append(f"This student's current enrollments: {enroll_str}.")
            return lines

        # Registrar: aggregate stats only — no individual student names/IDs exposed
        if role == "registrar":
            count = db.execute("SELECT COUNT(*) FROM ai_queries").fetchone()[0]
            flags = db.execute(
                "SELECT COUNT(*) FROM ai_flags WHERE status = 'pending'"
            ).fetchone()[0]
            return [
                f"AI query log: {count} total queries recorded.",
                f"Open flags awaiting review: {flags}.",
            ]
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
    "visitor":    {"topics": ["courses", "programs", "campus info"],                       "can_see_grades": False, "can_see_enrollment": False},
    "student":    {"topics": ["courses", "grades", "enrollment", "recommendations"],       "can_see_grades": True,  "can_see_enrollment": True},
    "instructor": {"topics": ["courses", "grades", "students", "schedules"],               "can_see_grades": True,  "can_see_enrollment": True},
    "registrar":  {"topics": ["all"],                                                       "can_see_grades": True,  "can_see_enrollment": True},
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
            return False, f"AI access is not available for {user['role']} accounts."
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
                """SELECT f.*, u.username AS flagged_by_name, q.query_text
                   FROM ai_flags f
                   JOIN users u ON f.flagged_by = u.id
                   JOIN ai_queries q ON f.query_id = q.id
                   WHERE f.status = ?
                   ORDER BY f.created_at DESC""",
                (status_filter,),
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
        print(f"Vector DB loaded: {_chroma_collection.count()} docs in collection.")
        return True
    except Exception as e:
        print(f"Vector DB Init Error: {e}")
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


def is_relevant_result(distance, max_distance=0.9):
    # K-023: cosine distance < 0.9 — emergency-wide threshold to confirm data is reachable
    return distance < max_distance


def query_vector_db(query_text, _role, n_results=3):
    if _chroma_collection is None:
        print("DEBUG: ChromaDB collection is None — init_vector_db() may have failed.")
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
        print(f"DEBUG: Raw Distances found: {results['distances']}")
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        print(f"DEBUG: ChromaDB raw distances for query '{query_text[:60]}': {distances}")
        relevant_docs = []
        for doc, dist in zip(docs, distances):
            if is_relevant_result(dist):
                relevant_docs.append(doc)
            else:
                print(f"DEBUG: Filtered out (dist={dist:.4f} > 0.6): {doc[:60]}...")
        print(f"DEBUG: {len(relevant_docs)}/{len(docs)} docs passed threshold.")
        return relevant_docs
    except Exception as e:
        print(f"ChromaDB Query Error: {e}")
        return []


def query_llm(query_text, context, role, private_context=None):
    # K-012: gemini-2.5-flash — always called, even when ChromaDB returns nothing.
    # private_context: list of strings fetched locally from DB (grades, enrollments).
    # These are injected as trusted facts and never pass through ChromaDB, preventing
    # one student from retrieving another student's data via similarity search.
    all_context = list(context) + (private_context or [])
    print(f"DEBUG: Context sent to LLM ({len(all_context)} docs): {all_context}")

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        role_ctx       = get_role_context(role)
        allowed_topics = ", ".join(role_ctx["topics"])

        if all_context:
            context_block = "\n".join(f"- {c}" for c in all_context)
            prompt = "\n".join([
                "You are the College0 Academic Assistant.",
                f"The user's role is '{role}'. You may discuss: {allowed_topics}.",
                "Use the verified context below to answer. Do not invent course names, "
                "grades, or seat counts not present in the context.",
                "If the context contains schedule or seat availability, state it explicitly.",
                f"\nContext:\n{context_block}",
                f"\nUser question: {query_text}",
            ])
        else:
            # K-011: No catalog match — answer from general academic knowledge but
            # explicitly forbid the LLM from inventing institution-specific facts.
            prompt = "\n".join([
                "You are the College0 Academic Assistant.",
                f"The user's role is '{role}'. You may discuss: {allowed_topics}.",
                "No specific course catalog data was found for this query.",
                "Answer from general academic knowledge only. Do NOT invent course names, "
                "grades, enrollment numbers, or policies specific to College0.",
                "If you cannot answer without institution-specific data, say so clearly "
                "and suggest the user contact the registrar's office.",
                f"\nUser question: {query_text}",
            ])

        model    = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip(), "llm"
    except Exception as e:
        print(f"LLM Error: {e}")
        return "AI service is temporarily unavailable. Please try again later.", "llm"


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

def score_courses_for_student(student_id, available_courses):
    # K-019: Returns sorted list of (course_dict, score, reason)
    db = get_db()
    try:
        enrolled_ids = {
            r["course_id"] for r in db.execute(
                "SELECT course_id FROM enrollments WHERE student_id = ? AND status = 'enrolled'",
                (student_id,),
            ).fetchall()
        }
        # K-019: also exclude courses the student already passed (grade != F)
        completed_ids = {
            r["course_id"] for r in db.execute(
                "SELECT course_id FROM grades WHERE student_id = ? AND letter_grade != 'F'",
                (student_id,),
            ).fetchall()
        }
        grades = db.execute(
            "SELECT numeric_value FROM grades WHERE student_id = ?", (student_id,)
        ).fetchall()
        # numeric_value is on 0.0–4.0 GPA scale (A=4.0, B=3.0, C=2.0, D=1.0, F=0.0)
        avg_gpa = (
            sum(g["numeric_value"] for g in grades) / len(grades) if grades else 2.5
        )
        scored = []
        for course in available_courses:
            if course["id"] in enrolled_ids or course["id"] in completed_ids:
                continue
            score = 50
            if avg_gpa >= 3.5:
                score  += 20
                reason  = "Strong academic record (GPA ≥ 3.5) — challenging course recommended"
            elif avg_gpa >= 2.5:
                score  += 10
                reason  = "Good standing (GPA ≥ 2.5) — course matches your level"
            else:
                score  += 5
                reason  = "Course available — consider strengthening your GPA first"
            if course.get("enrolled_count", 0) < course.get("capacity", 30):
                score += 5
            scored.append((dict(course), score, reason))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    finally:
        db.close()


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
            """SELECT id, course_name, time_slot, capacity, enrolled_count
               FROM courses
               WHERE status = 'active' AND semester_id = ?""",
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
        print(f"scrub_existing_query_log: {updated}/{len(rows)} rows cleaned.")
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