"""
almasur/sandbox.py — AI Subsystem 5 Development Console

Run:
    cd /Users/almasur/college0
    python almasur/sandbox.py

Visit: http://localhost:5001/ai/test  (Command Center)
       http://localhost:5001/ai/query (Production AI Interface)

Persona shortcuts (set session, redirect to /ai/query):
    /login/student/101   → Alice   (GPA 3.9, Dean's List)
    /login/student/102   → Bob     (GPA 1.8, Academic Probation)
    /login/student/103   → Charlie (GPA 3.2, no enrollments)
    /login/suspended/104 → Dave    (K-007 hard-block test)
    /login/graduated/105 → Eve     (eligibility block test)
    /login/registrar/1   → Registrar (full access)
    /login/instructor/2  → Dr. Smith
    /logout
"""

import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from flask import (
    Flask, session, redirect, url_for,
    render_template_string, jsonify,
)

from database.db import init_db, get_db
from modules.ai_features import init_vector_db, register_ai_routes

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(
    __name__,
    template_folder=os.path.join(_PROJECT_ROOT, "templates"),
    static_folder=os.path.join(_PROJECT_ROOT, "static"),
)
app.secret_key = "sandbox-secret-key-subsystem5"

# ── Seed: Class of 2026 ───────────────────────────────────────────────────────

def _seed_class_of_2026(db):
    """Idempotent seed — INSERT OR IGNORE throughout. Safe on every restart.

    Uses user IDs 101-103 (students), 104-105 (blocked personas), 201 (instructor).
    No collision with team data at IDs 1-4. Single transaction with rollback on failure.
    """
    try:
        db.execute("BEGIN")

        # ── Users ─────────────────────────────────────────────────────────────
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (101,'alice','alice@college0.com','password123','student','active')""")
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (102,'bob','bob@college0.com','password123','student','active')""")
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (103,'charlie','charlie@college0.com','password123','student','active')""")
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (201,'dr_smith','drsmith@college0.com','password123','instructor','active')""")
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (104,'dave','dave@college0.com','password123','suspended','suspended')""")
        db.execute("""INSERT OR IGNORE INTO users (id, username, email, password, role, status)
            VALUES (105,'eve','eve@college0.com','password123','graduated','graduated')""")

        # ── Students (GPA metadata) ───────────────────────────────────────────
        db.execute("""INSERT OR IGNORE INTO students
            (id, semester_gpa, cumulative_gpa, honor_roll, credits_earned, special_registration, status)
            VALUES (101, 3.9, 3.9, 1, 60, 0, 'active')""")
        db.execute("""INSERT OR IGNORE INTO students
            (id, semester_gpa, cumulative_gpa, honor_roll, credits_earned, special_registration, status)
            VALUES (102, 1.8, 1.8, 0, 30, 0, 'probation')""")
        db.execute("""INSERT OR IGNORE INTO students
            (id, semester_gpa, cumulative_gpa, honor_roll, credits_earned, special_registration, status)
            VALUES (103, 3.2, 3.2, 0, 45, 0, 'active')""")

        # ── Courses ───────────────────────────────────────────────────────────
        db.execute("""INSERT OR IGNORE INTO courses
            (course_name, semester_id, time_slot, day_of_week, start_time, end_time,
             capacity, enrolled_count, status, instructor_id)
            VALUES ('MAT200 - Calculus II', 1, 'Tue/Thu', 3, '10:00', '11:30',
                    30, 0, 'cancelled', 2)""")
        db.execute("""INSERT OR IGNORE INTO courses
            (course_name, semester_id, time_slot, day_of_week, start_time, end_time,
             capacity, enrolled_count, status, instructor_id)
            VALUES ('ENG300 - Advanced Writing', 1, 'Mon/Wed', 1, '14:00', '15:30',
                    30, 30, 'active', 2)""")
        db.execute("UPDATE courses SET enrolled_count=28, capacity=30 WHERE id=1")

        mat200 = db.execute(
            "SELECT id FROM courses WHERE course_name='MAT200 - Calculus II'"
        ).fetchone()
        mat200_id = mat200["id"] if mat200 else None

        # ── Grades ────────────────────────────────────────────────────────────
        db.execute("""INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
            SELECT 101, 1, 'A', 4.0
            WHERE NOT EXISTS (SELECT 1 FROM grades WHERE student_id=101 AND course_id=1)""")
        if mat200_id:
            db.execute("""INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
                SELECT 101, ?, 'A', 4.0
                WHERE NOT EXISTS (SELECT 1 FROM grades WHERE student_id=101 AND course_id=?)""",
                (mat200_id, mat200_id))
        db.execute("""INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
            SELECT 102, 1, 'D', 1.0
            WHERE NOT EXISTS (SELECT 1 FROM grades WHERE student_id=102 AND course_id=1)""")
        db.execute("""INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
            SELECT 103, 1, 'B', 3.0
            WHERE NOT EXISTS (SELECT 1 FROM grades WHERE student_id=103 AND course_id=1)""")
        db.execute("""INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
            SELECT 103, 2, 'B', 3.0
            WHERE NOT EXISTS (SELECT 1 FROM grades WHERE student_id=103 AND course_id=2)""")

        # ── Enrollments ───────────────────────────────────────────────────────
        db.execute("""INSERT INTO enrollments (student_id, course_id, status)
            SELECT 101, 1, 'enrolled'
            WHERE NOT EXISTS (SELECT 1 FROM enrollments WHERE student_id=101 AND course_id=1)""")
        if mat200_id:
            db.execute("""INSERT INTO enrollments (student_id, course_id, status)
                SELECT 101, ?, 'enrolled'
                WHERE NOT EXISTS (SELECT 1 FROM enrollments WHERE student_id=101 AND course_id=?)""",
                (mat200_id, mat200_id))
        db.execute("""INSERT INTO enrollments (student_id, course_id, status)
            SELECT 102, 1, 'enrolled'
            WHERE NOT EXISTS (SELECT 1 FROM enrollments WHERE student_id=102 AND course_id=1)""")

        # ── Pre-seeded queries + flags ─────────────────────────────────────────
        alice_q_count = db.execute(
            "SELECT COUNT(*) FROM ai_queries WHERE user_id=101"
        ).fetchone()[0]

        if alice_q_count == 0:
            db.execute("""INSERT INTO ai_queries
                (user_id, query_text, response_text, source, role_at_query) VALUES
                (101, 'What is my GPA?',
                 'Your current GPA is 3.9/4.0. You are on the Dean''s List — excellent work!',
                 'llm', 'student')""")
            q1_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute("""INSERT INTO ai_queries
                (user_id, query_text, response_text, source, role_at_query) VALUES
                (1, 'What is student alice''s GPA?',
                 'Student alice (ID 101): GPA 3.9/4.0. Grades: CS101: A, MAT200: A.',
                 'llm', 'registrar')""")
            q2_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute("""INSERT INTO ai_queries
                (user_id, query_text, response_text, source, role_at_query) VALUES
                (102, 'What courses should I take to improve my GPA?',
                 'Based on your academic standing, introductory courses are strongly recommended.',
                 'llm', 'student')""")
            db.execute("""INSERT INTO ai_queries
                (user_id, query_text, response_text, source, role_at_query) VALUES
                (103, 'What computer science courses are available this semester?',
                 'Available CS courses include CS101, CS201, CS150, CS220, and CS230.',
                 'vector_db', 'student')""")
            db.execute("""INSERT INTO ai_queries
                (user_id, query_text, response_text, source, role_at_query) VALUES
                (101, 'What courses am I currently enrolled in?',
                 'You are enrolled in CS101 - Intro to Computing and MAT200 - Calculus II.',
                 'llm', 'student')""")

            db.execute("""INSERT INTO ai_flags (query_id, flagged_by, reason, status)
                VALUES (?, 1, 'Test: verifying student data access', 'pending')""", (q1_id,))
            db.execute("""INSERT INTO ai_flags (query_id, flagged_by, reason, status)
                VALUES (?, 1, 'Test: registrar omniscience check', 'pending')""", (q2_id,))

        db.commit()

    except Exception:
        db.rollback()
        raise


# ── App context init ──────────────────────────────────────────────────────────

with app.app_context():
    init_db()
    init_vector_db()
    _seed_db = get_db()
    try:
        _seed_class_of_2026(_seed_db)
    finally:
        _seed_db.close()

register_ai_routes(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_system_status():
    """Live sidebar stats fetched on every Command Center request."""
    db = get_db()
    try:
        period_row = db.execute(
            "SELECT current_period FROM semesters WHERE id=1"
        ).fetchone()
        period = period_row["current_period"] if period_row else "unknown"
        open_flags = db.execute(
            "SELECT COUNT(*) FROM ai_flags WHERE status='pending'"
        ).fetchone()[0]
        total_queries = db.execute(
            "SELECT COUNT(*) FROM ai_queries"
        ).fetchone()[0]
        return {"period": period, "open_flags": open_flags, "total_queries": total_queries}
    finally:
        db.close()


# ── Mock auth ─────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("ai_test"))


@app.route("/dashboard")
def dashboard():
    return redirect(url_for("ai_test"))


@app.route("/login")
def login():
    return redirect(url_for("ai_test"))


@app.route("/login/student/<int:user_id>")
def mock_login_student(user_id):
    session["user_id"] = user_id
    session["role"] = "student"
    return redirect(url_for("ai_query"))


@app.route("/login/registrar/<int:user_id>")
def mock_login_registrar(user_id):
    session["user_id"] = user_id
    session["role"] = "registrar"
    return redirect(url_for("ai_query"))


@app.route("/login/instructor/<int:user_id>")
def mock_login_instructor(user_id):
    session["user_id"] = user_id
    session["role"] = "instructor"
    return redirect(url_for("ai_query"))


@app.route("/login/suspended/<int:user_id>")
def mock_login_suspended(user_id):
    session["user_id"] = user_id
    session["role"] = "suspended"
    return redirect(url_for("ai_query"))


@app.route("/login/graduated/<int:user_id>")
def mock_login_graduated(user_id):
    session["user_id"] = user_id
    session["role"] = "graduated"
    return redirect(url_for("ai_query"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("ai_test"))


# ── Scenario toggles ─────────────────────────────────────────────────────────

@app.route("/ai/scenario/<action>", methods=["POST"])
def scenario_toggle(action):
    db = get_db()
    try:
        if action == "special_reg":
            db.execute("UPDATE semesters SET current_period='special_registration' WHERE id=1")
        elif action == "cancel_cs101":
            db.execute("UPDATE courses SET status='cancelled' WHERE course_name LIKE '%CS101%'")
        elif action == "fill_seats":
            db.execute("UPDATE courses SET enrolled_count=capacity WHERE status='active'")
        elif action == "reset":
            db.execute("UPDATE semesters SET current_period='running' WHERE id=1")
            db.execute("UPDATE courses SET status='active' WHERE course_name LIKE '%CS101%'")
            db.execute("UPDATE courses SET enrolled_count=28 WHERE id=1")
            mat200 = db.execute(
                "SELECT id FROM courses WHERE course_name='MAT200 - Calculus II'"
            ).fetchone()
            if mat200:
                db.execute("UPDATE courses SET enrolled_count=0 WHERE id=?", (mat200["id"],))
            eng300 = db.execute(
                "SELECT id FROM courses WHERE course_name='ENG300 - Advanced Writing'"
            ).fetchone()
            if eng300:
                db.execute("UPDATE courses SET enrolled_count=30 WHERE id=?", (eng300["id"],))
        else:
            db.close()
            return jsonify({"success": False, "error": f"Unknown action: {action}"}), 400

        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for("ai_test"))


# ── Command Center HTML ───────────────────────────────────────────────────────

_CMD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Dev Console — Subsystem 5</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; background: #f0f4f8; }

  .navbar {
    background: #1a2f52; color: white; padding: 0 20px;
    height: 52px; display: flex; align-items: center; justify-content: space-between;
  }
  .navbar h1 { font-size: 15px; font-weight: bold; }
  .navbar a { color: #c8d8f0; text-decoration: none; font-size: 13px; margin-left: 16px; }
  .navbar a:hover { color: white; }
  .dev-badge {
    background: #f0ad4e; color: #333; font-size: 10px; font-weight: bold;
    padding: 2px 8px; border-radius: 10px; margin-left: 10px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }

  .layout { display: flex; min-height: calc(100vh - 52px); }

  /* Sidebar */
  .sidebar {
    width: 220px; background: white; border-right: 1px solid #dce8f0;
    padding: 16px 12px; flex-shrink: 0; overflow-y: auto;
  }
  .sidebar h3 { font-size: 11px; text-transform: uppercase; color: #888;
                letter-spacing: 0.8px; margin-bottom: 10px; }
  .persona-card {
    display: block; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px;
    text-decoration: none; color: #222; border: 2px solid #e0e8f0;
    background: #f7fafd; transition: border-color 0.15s;
  }
  .persona-card:hover { border-color: #2E4A7A; }
  .persona-card.active { border-color: #2E4A7A; background: #dceeff; }
  .persona-name { font-weight: bold; font-size: 14px; }
  .persona-meta { font-size: 11px; color: #555; margin-top: 3px; }
  .pill { display: inline-block; padding: 2px 7px; border-radius: 10px;
          font-size: 10px; font-weight: bold; margin-left: 4px; }
  .pill-green  { background: #d4edda; color: #155724; }
  .pill-red    { background: #f8d7da; color: #721c24; }
  .pill-yellow { background: #fff3cd; color: #856404; }
  .pill-blue   { background: #cce5ff; color: #004085; }
  .pill-gray   { background: #e2e3e5; color: #383d41; }

  .status-block { margin-top: 16px; padding: 10px; background: #f7fafd;
                  border-radius: 8px; border: 1px solid #e0e8f0; }
  .status-row { font-size: 12px; color: #444; padding: 3px 0; }
  .status-label { color: #888; }

  /* Main */
  .main { flex: 1; padding: 24px 28px; overflow-y: auto; }

  .launch-card {
    background: #2E4A7A; color: white; border-radius: 12px;
    padding: 28px 32px; margin-bottom: 24px; text-align: center;
  }
  .launch-card h2 { font-size: 20px; margin-bottom: 8px; }
  .launch-card p { font-size: 14px; color: #c8d8f0; margin-bottom: 20px; }
  .launch-btn {
    display: inline-block; background: white; color: #2E4A7A;
    font-size: 15px; font-weight: bold; padding: 12px 32px;
    border-radius: 8px; text-decoration: none;
  }
  .launch-btn:hover { opacity: 0.88; }

  .box {
    background: white; border-radius: 10px; border: 1px solid #e0e8f0;
    padding: 18px 20px; margin-bottom: 18px;
  }
  .box h3 { color: #2E4A7A; font-size: 14px; margin-bottom: 14px; }

  .sc-grid { display: flex; flex-wrap: wrap; gap: 8px; }
  .sc-btn {
    background: #f0f4f8; border: 1px solid #c8d8f0; color: #2E4A7A;
    padding: 7px 16px; border-radius: 5px; cursor: pointer;
    font-size: 12px; font-weight: bold;
  }
  .sc-btn:hover { background: #dceeff; }
  .sc-btn.reset { background: #fff3cd; border-color: #ffc107; color: #856404; }
  .sc-btn.reset:hover { background: #ffeaa7; }

  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .info-item { background: #f7fafd; border: 1px solid #e0e8f0;
               border-radius: 8px; padding: 12px 14px; }
  .info-label { font-size: 11px; color: #888; text-transform: uppercase;
                letter-spacing: 0.5px; }
  .info-val { font-size: 22px; font-weight: bold; color: #2E4A7A; margin-top: 4px; }

  table { width: 100%; font-size: 13px; border-collapse: collapse; }
  th { background: #f0f4f8; padding: 7px 10px; text-align: left; color: #2E4A7A; }
  td { padding: 7px 10px; border-top: 1px solid #e0e8f0; }
</style>
</head>
<body>

<div class="navbar">
  <div style="display:flex; align-items:center;">
    <h1>AI Subsystem 5</h1>
    <span class="dev-badge">DEV CONSOLE</span>
  </div>
  <div>
    <a href="/ai/query">Open AI Assistant</a>
    <a href="/ai/export">Export CSV</a>
    {% if session.get('user_id') %}<a href="/logout">[Logout]</a>{% endif %}
  </div>
</div>

<div class="layout">

  <!-- Sidebar -->
  <div class="sidebar">
    <h3>Personas</h3>

    <a href="/login/student/101"
       class="persona-card {% if session.get('user_id')==101 %}active{% endif %}">
      <div class="persona-name">Alice <span class="pill pill-green">3.9</span></div>
      <div class="persona-meta">Dean's List &nbsp;<span class="pill pill-green">Active</span></div>
    </a>

    <a href="/login/student/102"
       class="persona-card {% if session.get('user_id')==102 %}active{% endif %}">
      <div class="persona-name">Bob <span class="pill pill-red">1.8</span></div>
      <div class="persona-meta"><span class="pill pill-red">Probation</span></div>
    </a>

    <a href="/login/student/103"
       class="persona-card {% if session.get('user_id')==103 %}active{% endif %}">
      <div class="persona-name">Charlie <span class="pill pill-yellow">3.2</span></div>
      <div class="persona-meta">No enrollments &nbsp;<span class="pill pill-yellow">Active</span></div>
    </a>

    <a href="/login/suspended/104"
       class="persona-card {% if session.get('user_id')==104 %}active{% endif %}">
      <div class="persona-name">Dave <span class="pill pill-red">Suspended</span></div>
      <div class="persona-meta">K-007 hard-block test</div>
    </a>

    <a href="/login/graduated/105"
       class="persona-card {% if session.get('user_id')==105 %}active{% endif %}">
      <div class="persona-name">Eve <span class="pill pill-gray">Graduated</span></div>
      <div class="persona-meta">Eligibility block test</div>
    </a>

    <a href="/login/registrar/1"
       class="persona-card {% if session.get('user_id')==1 %}active{% endif %}">
      <div class="persona-name">Registrar <span class="pill pill-blue">Admin</span></div>
      <div class="persona-meta">Full access</div>
    </a>

    <a href="/login/instructor/2"
       class="persona-card {% if session.get('user_id')==2 %}active{% endif %}">
      <div class="persona-name">Dr. Smith <span class="pill pill-blue">Instructor</span></div>
      <div class="persona-meta">Course view</div>
    </a>

    <div class="status-block">
      <h3 style="margin-bottom:8px;">System Status</h3>
      <div class="status-row">
        <span class="status-label">Period: </span><strong>{{ status.period }}</strong>
      </div>
      <div class="status-row">
        <span class="status-label">Open flags: </span><strong>{{ status.open_flags }}</strong>
      </div>
      <div class="status-row">
        <span class="status-label">Queries: </span><strong>{{ status.total_queries }}</strong>
      </div>
      <div class="status-row">
        <span class="status-label">Role: </span>
        <strong>{{ session.get('role', 'none') }}</strong>
      </div>
    </div>
  </div>

  <!-- Main -->
  <div class="main">

    <div class="launch-card">
      <h2>AI Assistant — Production Interface</h2>
      <p>
        Select a persona from the sidebar, then open the AI Assistant to test the live experience.
        The chat, recommendations, and flag review are all consolidated at <strong>/ai/query</strong>.
      </p>
      {% if session.get('user_id') %}
      <a href="/ai/query" class="launch-btn">
        Open as {{ session.get('role', 'visitor') }} &rarr;
      </a>
      {% else %}
      <a href="/ai/query" class="launch-btn">Open AI Assistant &rarr;</a>
      {% endif %}
    </div>

    <div class="box">
      <h3>Scenario Controls</h3>
      <div class="sc-grid">
        <form method="POST" action="/ai/scenario/special_reg">
          <button class="sc-btn" type="submit">Set: Special Registration</button>
        </form>
        <form method="POST" action="/ai/scenario/cancel_cs101">
          <button class="sc-btn" type="submit">Cancel CS101</button>
        </form>
        <form method="POST" action="/ai/scenario/fill_seats">
          <button class="sc-btn" type="submit">Fill All Seats</button>
        </form>
        <form method="POST" action="/ai/scenario/reset">
          <button class="sc-btn reset" type="submit">&#8635; Reset All</button>
        </form>
      </div>
      <p style="font-size:11px; color:#856404; margin-top:10px;">
        Scenarios affect the live database. Reset before switching personas for a clean run.
      </p>
    </div>

    <div class="box">
      <h3>Live System Stats</h3>
      <div class="info-grid">
        <div class="info-item">
          <div class="info-label">Semester Period</div>
          <div class="info-val" style="font-size:16px;">{{ status.period }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Open Flags</div>
          <div class="info-val">{{ status.open_flags }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Total AI Queries</div>
          <div class="info-val">{{ status.total_queries }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Active Persona</div>
          <div class="info-val" style="font-size:15px;">{{ session.get('role', '—') }}</div>
        </div>
      </div>
    </div>

    <div class="box">
      <h3>Verification Checklist</h3>
      <table>
        <thead>
          <tr>
            <th>Test</th><th>Persona</th><th>Query</th><th>Expected Result</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>K-012 Precision</strong></td>
            <td>Alice</td>
            <td style="color:#555;">What is my GPA?</td>
            <td style="color:#155724;">Exactly 3.9</td>
          </tr>
          <tr>
            <td><strong>K-007 Hard-block</strong></td>
            <td>Dave (Suspended)</td>
            <td style="color:#555;">Any query</td>
            <td style="color:#721c24;">Access Denied immediately</td>
          </tr>
          <tr>
            <td><strong>K-020 Registrar</strong></td>
            <td>Registrar</td>
            <td style="color:#555;">Give me Bob's GPA</td>
            <td style="color:#155724;">1.8, probation standing</td>
          </tr>
          <tr>
            <td><strong>K-016 Recs sidebar</strong></td>
            <td>Charlie</td>
            <td style="color:#555;">(page load)</td>
            <td style="color:#155724;">Recommendations sidebar auto-populates</td>
          </tr>
          <tr>
            <td><strong>K-025 Export</strong></td>
            <td>Registrar</td>
            <td style="color:#555;">Click Download CSV</td>
            <td style="color:#155724;">CSV file downloads</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</div>
</body>
</html>
"""


# ── Command Center route ───────────────────────────────────────────────────────

@app.route("/ai/test", methods=["GET"])
def ai_test():
    """Dev-only launch pad. Chat lives at /ai/query."""
    return render_template_string(
        _CMD_HTML,
        session=session,
        status=_get_system_status(),
    )


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("AI Subsystem 5 — Dev Console: http://localhost:5001/ai/test")
    print("AI Assistant (production): http://localhost:5001/ai/query")
    app.run(debug=True, port=5001)
