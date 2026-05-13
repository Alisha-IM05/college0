import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), 'college0.db')
SCHEMA   = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# alias so Alisha's code works too
get_connection = get_db


def init_db():
    conn = get_db()
    with open(SCHEMA, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database tables created successfully.")


def seed_data():
    conn = get_db()

    # ── WIPE EXISTING DATA ────────────────────────────────────────────────────
    for tbl in [
        'graduation_applications', 'flagged_course_gpas', 'grades',
        'waitlist', 'enrollments', 'courses', 'semesters',
        'warnings', 'complaints', 'reviews', 'taboo_words',
        'students', 'users'
    ]:
        try:
            conn.execute(f"DELETE FROM {tbl}")
        except:
            pass
    conn.commit()
    print("Existing data cleared.")

    # ── USERS ─────────────────────────────────────────────────────────────────
    users = [
        ('registrar1',    'registrar1@college0.com',  'password123', 'registrar'),
        ('prof_smith',    'smith@college0.com',        'password123', 'instructor'),
        ('prof_jones',    'jones@college0.com',        'password123', 'instructor'),
        ('demo_student1', 'demo1@college0.com',        'password123', 'student'),
        ('demo_student2', 'demo2@college0.com',        'password123', 'student'),
        ('alice',         'alice@college0.com',        'password123', 'student'),
        ('bob',           'bob@college0.com',          'password123', 'student'),
        ('carol',         'carol@college0.com',        'password123', 'student'),
        ('david',         'david@college0.com',        'password123', 'student'),
        ('eve',           'eve@college0.com',          'password123', 'student'),
        ('frank',         'frank@college0.com',        'password123', 'student'),
        ('grace',         'grace@college0.com',        'password123', 'student'),
        ('henry',         'henry@college0.com',        'password123', 'student'),
    ]

    for username, email, password, role in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            (username, email, password, role)
        )
        if role == 'student':
            user = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user:
                conn.execute(
                    "INSERT OR IGNORE INTO students (id) VALUES (?)", (user['id'],)
                )
    conn.commit()

    def uid(username):
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row['id'] if row else None

    smith_id = uid('prof_smith')
    jones_id = uid('prof_jones')

    # ── SPRING 2026 SEMESTER ──────────────────────────────────────────────────
    conn.execute(
        "INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'setup')"
    )
    conn.commit()

    spring_courses = [
        ('CS101 - Intro to Computing',   'Mon/Wed', 1, '08:00', '09:30', 10, 4, 'active', smith_id),
        ('CS201 - Data Structures',      'Tue/Thu', 3, '10:00', '11:30', 10, 4, 'active', smith_id),
        ('MATH101 - Calculus I',         'Wed/Fri', 4, '13:00', '14:30', 10, 4, 'active', jones_id),
        ('ENG101 - English Comp',        'Fri',     5, '09:00', '11:00', 10, 4, 'active', jones_id),
        ('BUS101 - Business Writing',    'Tue/Thu', 3, '08:00', '09:30', 10, 4, 'active', jones_id),
        ('PHYS201 - Physics II',         'Mon/Wed', 1, '13:00', '14:30', 10, 4, 'active', smith_id),
        ('CS999 - Special Topics',       'Tue/Thu', 3, '15:00', '16:30',  1, 1, 'active', smith_id),
        ('CS150 - Intro to Python',      'Mon/Wed', 1, '11:00', '12:30', 10, 2, 'active', jones_id),
        ('PHYS101 - Physics I',          'Mon/Wed', 1, '08:00', '09:30', 10, 4, 'active', jones_id),
        ('CS220 - Database Systems',     'Mon/Wed', 1, '10:00', '11:30', 10, 0, 'active', smith_id),
    ]

    for name, slot, day, start, end, cap, enrolled, status, inst_id in spring_courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (name, inst_id, slot, day, start, end, cap, enrolled, status)
        )
    conn.commit()

    def cid_spring(name):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = 1", (name,)
        ).fetchone()
        return row['id'] if row else None

    # ── SPRING 2026 BACKGROUND ENROLLMENTS ───────────────────────────────────
    spring_background = [
        ('alice', 'CS101 - Intro to Computing'),
        ('alice', 'CS201 - Data Structures'),
        ('alice', 'MATH101 - Calculus I'),
        ('alice', 'ENG101 - English Comp'),
        ('bob',   'CS101 - Intro to Computing'),
        ('bob',   'CS201 - Data Structures'),
        ('bob',   'BUS101 - Business Writing'),
        ('bob',   'PHYS201 - Physics II'),
        ('carol', 'MATH101 - Calculus I'),
        ('carol', 'ENG101 - English Comp'),
        ('carol', 'BUS101 - Business Writing'),
        ('carol', 'PHYS201 - Physics II'),
        ('david', 'CS101 - Intro to Computing'),
        ('david', 'PHYS101 - Physics I'),
        ('david', 'PHYS201 - Physics II'),
        ('david', 'BUS101 - Business Writing'),
        ('eve',   'CS150 - Intro to Python'),
        ('frank', 'CS150 - Intro to Python'),
        ('grace', 'CS999 - Special Topics'),
        ('alice', 'PHYS101 - Physics I'),
        ('bob',   'PHYS101 - Physics I'),
        ('carol', 'PHYS101 - Physics I'),
    ]

    for username, course_name in spring_background:
        student_id = uid(username)
        course_id  = cid_spring(course_name)
        if student_id and course_id:
            conn.execute(
                """INSERT OR IGNORE INTO enrollments (student_id, course_id, status)
                   VALUES (?, ?, 'enrolled')""",
                (student_id, course_id)
            )

    # ── SPRING 2026 WAITLIST ──────────────────────────────────────────────────
    cs999 = cid_spring('CS999 - Special Topics')
    if cs999:
        conn.execute(
            "INSERT OR IGNORE INTO waitlist (student_id, course_id, position) VALUES (?, ?, 1)",
            (uid('henry'), cs999)
        )

# ── DEMO STUDENT ENROLLMENTS & GRADES ────────────────────────────────────
    demo1_id = uid('demo_student1')
    demo2_id = uid('demo_student2')

    demo_enrollments = [
        ('demo_student1', 'CS101 - Intro to Computing'),
        ('demo_student1', 'CS201 - Data Structures'),
        ('demo_student1', 'MATH101 - Calculus I'),
        ('demo_student1', 'ENG101 - English Comp'),
        ('demo_student2', 'CS201 - Data Structures'),
        ('demo_student2', 'BUS101 - Business Writing'),
        ('demo_student2', 'PHYS201 - Physics II'),
        ('demo_student2', 'ENG101 - English Comp'),
    ]

    for username, course_name in demo_enrollments:
        student_id = uid(username)
        course_id  = cid_spring(course_name)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                (student_id, course_id)
            )

    grade_seeds = [
        (demo1_id, cid_spring('CS101 - Intro to Computing'), 'A',  4.0),
        (demo1_id, cid_spring('CS201 - Data Structures'),    'B+', 3.3),
        (demo1_id, cid_spring('MATH101 - Calculus I'),       'A-', 3.7),
        (demo1_id, cid_spring('ENG101 - English Comp'),      'B',  3.0),
        (demo2_id, cid_spring('CS201 - Data Structures'),    'B',  3.0),
        (demo2_id, cid_spring('BUS101 - Business Writing'),  'A',  4.0),
        (demo2_id, cid_spring('PHYS201 - Physics II'),       'C+', 2.3),
        (demo2_id, cid_spring('ENG101 - English Comp'),      'B-', 2.7),
    ]

    for student_id, course_id, letter, numeric in grade_seeds:
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO grades (student_id, course_id, letter_grade, numeric_value) VALUES (?, ?, ?, ?)",
                (student_id, course_id, letter, numeric)
            )

    conn.execute("UPDATE students SET semester_gpa=3.5, cumulative_gpa=3.5, credits_earned=4 WHERE id=?", (demo1_id,))
    conn.execute("UPDATE students SET semester_gpa=3.0, cumulative_gpa=3.0, credits_earned=4 WHERE id=?", (demo2_id,))

    # ── TABOO WORDS ───────────────────────────────────────────────────────────
    for word in ['hate', 'stupid', 'idiot', 'terrible', 'awful']:
        conn.execute(
            "INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,)
        )

    conn.commit()
    conn.close()
    print("Seed data inserted successfully.")


if __name__ == "__main__":
    init_db()
    seed_data()
    print("\nDone! Run 'python3 app.py' to start the website.")
    print("Login at http://127.0.0.1:5001")
    print("\nAccounts (all password: password123):")
    print("  registrar1    — registrar")
    print("  prof_smith    — instructor")
    print("  prof_jones    — instructor")
    print("  demo_student1 — clean demo student #1")
    print("  demo_student2 — clean demo student #2")
    print("  alice/bob/carol/david/eve/frank/grace/henry — background students")
    print("\nSpring 2026 scenario map:")
    print("  [NORMAL]   CS101, CS201, MATH101, ENG101, BUS101, PHYS201 — open seats")
    print("  [WAITLIST] CS999 — full (cap=1), henry already waitlisted")
    print("  [CANCEL]   CS150 — only 2 enrollments, cancels when advancing to running")
    print("  [CONFLICT] PHYS101 — same slot as CS101, blocks demo if in CS101")
    print("  [SPECIAL]  CS220 — empty, available for special re-reg")
    print("\nFall 2026 scenario map:")
    print("  [NORMAL]   CS301, CS401, MATH201, ENG201, BUS201, PHYS301, CS450 — 3+ enrolled")
    print("  [CANCEL]   CS350 — only 2 enrollments, cancels when advancing to running")