"""
seed_chroma.py — Populate ChromaDB with course catalog + policy documents.

Run once (or after any course catalog change):
    python seed_chroma.py
"""

import os
import sys
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on sys.path so we can import modules.ai_features
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

# Import the shared class — do NOT redefine it here.
# Both the seeder and the app must use the identical embedding logic.
from modules.ai_features import SimpleGoogleEmbeddingFunction

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH     = os.path.expanduser("~/college0/database/chroma_db")  # absolute chroma path — matches DB_PATH in ai_features.py
_DB_PATH    = os.path.join(_BASE_DIR, "database", "college0.db")
_CHROMA_DIR = DB_PATH
_COLLECTION = "college0_knowledge"


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_course_docs():
    db = get_db()
    try:
        courses = db.execute(
            """SELECT id, course_name, time_slot, day_of_week,
                      start_time, end_time, capacity, enrolled_count, status
               FROM courses WHERE status = 'active'"""
        ).fetchall()
    finally:
        db.close()

    docs, ids, metas = [], [], []
    for c in courses:
        seats_left = c["capacity"] - c["enrolled_count"]
        doc = (
            f"Course: {c['course_name']}. "
            f"Schedule: {c['time_slot']}, day {c['day_of_week']}, "
            f"{c['start_time']}–{c['end_time']}. "
            f"Capacity: {c['capacity']} seats, {seats_left} currently available. "
            f"Status: {c['status']}. Course ID: {c['id']}."
        )
        docs.append(doc)
        ids.append(f"course_{c['id']}")
        metas.append({"type": "course", "course_id": c["id"]})

    return docs, ids, metas


def build_policy_docs():
    policies = [
        (
            "pol_grading",
            "Grading Policy: Grades are awarded as A, B, C, D, or F. "
            "A = 90–100 (4.0 GPA points), B = 80–89 (3.0), C = 70–79 (2.0), "
            "D = 60–69 (1.0), F = below 60 (0.0).",
            {"type": "policy", "topic": "grading"},
        ),
        (
            "pol_registration",
            "Registration Policy: Students may register during the registration period. "
            "Minimum of 3 students required for a course to run.",
            {"type": "policy", "topic": "registration"},
        ),
        (
            "pol_withdrawal",
            "Withdrawal Policy: Students may withdraw before the deadline without a failing grade. "
            "Contact the registrar to process.",
            {"type": "policy", "topic": "withdrawal"},
        ),
    ]
    return (
        [p[1] for p in policies],
        [p[0] for p in policies],
        [p[2] for p in policies],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY is missing from .env")
        sys.exit(1)

    try:
        import chromadb
    except ImportError:
        print("ERROR: Run 'pip install chromadb google-generativeai'")
        sys.exit(1)

    os.makedirs(_CHROMA_DIR, exist_ok=True)

    # Shared embedding function — same class the app uses, same model, same task types
    ef = SimpleGoogleEmbeddingFunction(api_key=api_key)

    client = chromadb.PersistentClient(path=_CHROMA_DIR)

    # Delete and recreate so cosine metric is enforced.
    # get_or_create_collection cannot change the metric of an existing collection.
    try:
        client.delete_collection(name=_COLLECTION)
        print(f"Deleted existing '{_COLLECTION}' collection.")
    except Exception:
        pass  # collection didn't exist yet — nothing to delete

    collection = client.create_collection(
        name=_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Created '{_COLLECTION}' with cosine distance metric.")

    # Upsert courses
    course_docs, course_ids, course_metas = build_course_docs()
    if course_docs:
        collection.upsert(documents=course_docs, ids=course_ids, metadatas=course_metas)
        print(f"✓ {len(course_docs)} courses upserted.")
    else:
        print("WARNING: No active courses found in the database.")

    # Upsert policies
    policy_docs, policy_ids, policy_metas = build_policy_docs()
    collection.upsert(documents=policy_docs, ids=policy_ids, metadatas=policy_metas)
    print(f"✓ {len(policy_docs)} policies upserted.")

    total = collection.count()
    print(f"Confirmed: {total} rows added to collection 'college0_knowledge'")

    # Smoke test — use embed_query (retrieval_query task type) to mirror app behaviour
    print("\nSmoke test — querying 'What CS courses are available?'")
    query_embedding = ef.embed_query("What CS courses are available?")
    results = collection.query(query_embeddings=[query_embedding], n_results=2)
    docs      = results.get("documents", [[]])[0]
    distances = results.get("distances",  [[]])[0]
    if docs:
        for i, (doc, dist) in enumerate(zip(docs, distances)):
            status = "PASS" if dist <= 0.6 else "filtered (dist > 0.6)"
            print(f"  Match {i+1} [{status}] dist={dist:.4f}: {doc[:80]}...")
    else:
        print("  WARNING: No results returned — check that courses exist in the DB.")

    print(f"\n✓ seed_chroma.py complete. Collection has {collection.count()} total docs.")


if __name__ == "__main__":
    main()
