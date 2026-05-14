import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), 'college0.db')
SCHEMA   = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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
    # 1 registrar, 3 instructors (prof_demo is demo-accessible),
    # 10 students (demo_student1 & demo_student2 are demo-accessible)
    users = [
        ('registrar1',    'registrar1@college0.com',  'password123', 'registrar'),
        ('prof_smith',    'smith@college0.com',        'password123', 'instructor'),
        ('prof_jones',    'jones@college0.com',        'password123', 'instructor'),
        # demo students — NOT pre-enrolled, enroll live during demo
        ('demo_student1', 'demo1@college0.com',        'password123', 'student'),  # freshman, 0 credits
        ('demo_student2', 'demo2@college0.com',        'password123', 'student'),  # senior, 112 credits, needs 8 to graduate
        # background students — pre-enrolled, scattered academic careers
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
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if user:
                conn.execute("INSERT OR IGNORE INTO students (id) VALUES (?)", (user['id'],))
    conn.commit()

    def uid(username):
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return row['id'] if row else None

    demo_prof_id = uid('prof_demo')
    smith_id     = uid('prof_smith')
    jones_id     = uid('prof_jones')
    demo1_id     = uid('demo_student1')
    demo2_id     = uid('demo_student2')
    alice_id     = uid('alice')
    bob_id       = uid('bob')
    carol_id     = uid('carol')
    david_id     = uid('david')
    eve_id       = uid('eve')
    frank_id     = uid('frank')
    grace_id     = uid('grace')
    henry_id     = uid('henry')

    # ── SIX SEMESTERS (all start at setup) ───────────────────────────────────
    semesters = [
        (1, 'Fall 2024',   'setup'),
        (2, 'Spring 2025', 'setup'),
        (3, 'Summer 2025', 'setup'),
        (4, 'Fall 2025',   'setup'),
        (5, 'Spring 2026', 'setup'),
        (6, 'Fall 2026',   'setup'),
    ]
    for sem_id, name, period in semesters:
        conn.execute(
            "INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (?, ?, ?)",
            (sem_id, name, period)
        )
    conn.commit()

    # ── SPRING 2026 COURSES ───────────────────────────────────────────────────
    # Scenarios demonstrated:
    # [NORMAL]    CS101, MATH101          — regular enrollment, seats available
    # [CANCEL]    CS201, MATH201          — under-enrolled (<3), will be cancelled
    # [WAITLIST]  CS301, ENG101           — cap=5, 8 students want in → waitlist
    # [CONFLICT]  CS401 & CS450           — Smith's two classes, same time slot (Mon/Wed 9am)
    # [CONFLICT]  PHYS101 & PHYS201       — Jones's two classes, same time slot (Tue/Thu 11am)
    #
    # (name, time_slot, day_of_week, start_time, end_time, capacity, instructor_id)
    courses = [
        # Prof Smith
        ('CS101 - Intro to Computing',      'Mon/Wed', 1, '08:00', '09:30', 10, smith_id),  # NORMAL
        ('CS201 - Discrete Math',           'Tue/Thu', 3, '10:00', '11:30', 10, smith_id),  # CANCEL (2 enrolled)
        ('CS301 - Algorithms',              'Fri',     5, '13:00', '14:30',  5, smith_id),  # WAITLIST (cap=5, 8 want in)
        ('CS401 - Operating Systems',       'Mon/Wed', 1, '09:00', '10:30', 10, smith_id),  # CONFLICT with CS450
        ('CS450 - Computer Networks',       'Mon/Wed', 1, '09:00', '10:30', 10, smith_id),  # CONFLICT with CS401
        # Prof Jones
        ('MATH101 - Calculus I',            'Tue/Thu', 3, '08:00', '09:30', 10, jones_id),  # NORMAL
        ('MATH201 - Calculus II',           'Wed/Fri', 4, '08:00', '09:30', 10, jones_id),  # CANCEL (2 enrolled)
        ('ENG101 - English Comp',           'Mon/Wed', 1, '14:00', '15:30',  5, jones_id),  # WAITLIST (cap=5, 8 want in)
        ('PHYS101 - Physics I',             'Tue/Thu', 3, '11:00', '12:30', 10, jones_id),  # CONFLICT with PHYS201
        ('PHYS201 - Physics II',            'Tue/Thu', 3, '11:00', '12:30', 10, jones_id),  # CONFLICT with PHYS101
    ]

    for name, slot, day, start, end, cap, inst_id in courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'active')""",
            (name, inst_id, slot, day, start, end, cap)
        )
    conn.commit()

    def cid(name):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = ?",
            (course_name, sem_id)
        ).fetchone()
        return row['id'] if row else None

    def enroll(username, course_name):
        student_id = uid(username)
        course_id  = cid(course_name)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                (student_id, course_id)
            )
            conn.execute(
                "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
                (course_id,)
            )

    def waitlist(username, course_name, position):
        student_id = uid(username)
        course_id  = cid(course_name)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO waitlist (student_id, course_id, position) VALUES (?, ?, ?)",
                (student_id, course_id, position)
            )

    # ── DEMO STUDENTS: NOT enrolled — enroll live during demo ─────────────────
    demo1_id = uid('demo_student1')
    demo2_id = uid('demo_student2')
    conn.execute("UPDATE students SET semester_gpa=0.0, cumulative_gpa=0.0, credits_earned=0,  honor_roll=0 WHERE id=?", (demo1_id,))
    conn.execute("UPDATE students SET semester_gpa=3.8, cumulative_gpa=3.6, credits_earned=4, honor_roll=1 WHERE id=?", (demo2_id,))

    # ── NORMAL CLASSES: CS101 and MATH101 — 3-4 background students ───────────
    enroll('alice', 'CS101 - Intro to Computing')
    enroll('bob',   'CS101 - Intro to Computing')
    enroll('carol', 'CS101 - Intro to Computing')
    enroll('david', 'CS101 - Intro to Computing')

    enroll('alice', 'MATH101 - Calculus I')
    enroll('bob',   'MATH101 - Calculus I')
    enroll('carol', 'MATH101 - Calculus I')

    # ── CANCEL CLASSES: CS201 and MATH201 — only 2 students enrolled ──────────
    enroll('eve',   'CS201 - Discrete Math')
    enroll('frank', 'CS201 - Discrete Math')

    enroll('eve',   'MATH201 - Calculus II')
    enroll('frank', 'MATH201 - Calculus II')

    # ── WAITLIST CLASSES: CS301 and ENG101 — cap=5, 8 students want in ────────
    # First 5 get enrolled, last 3 go to waitlist
    enroll('alice', 'CS301 - Algorithms')
    enroll('bob',   'CS301 - Algorithms')
    enroll('carol', 'CS301 - Algorithms')
    enroll('david', 'CS301 - Algorithms')
    enroll('grace', 'CS301 - Algorithms')
    # waitlist positions 1-3
    waitlist('henry', 'CS301 - Algorithms', 1)
    waitlist('eve',   'CS301 - Algorithms', 2)
    waitlist('frank', 'CS301 - Algorithms', 3)

    enroll('alice', 'ENG101 - English Comp')
    enroll('bob',   'ENG101 - English Comp')
    enroll('carol', 'ENG101 - English Comp')
    enroll('david', 'ENG101 - English Comp')
    enroll('grace', 'ENG101 - English Comp')
    waitlist('henry', 'ENG101 - English Comp', 1)
    waitlist('eve',   'ENG101 - English Comp', 2)
    waitlist('frank', 'ENG101 - English Comp', 3)

    # ── CONFLICT CLASSES: CS401 & CS450 — same time, background students in both
    enroll('alice', 'CS401 - Operating Systems')
    enroll('bob',   'CS401 - Operating Systems')
    enroll('carol', 'CS401 - Operating Systems')
    enroll('david', 'CS450 - Computer Networks')
    enroll('grace', 'CS450 - Computer Networks')
    enroll('henry', 'CS450 - Computer Networks')

    enroll('alice', 'PHYS101 - Physics I')
    enroll('bob',   'PHYS101 - Physics I')
    enroll('carol', 'PHYS101 - Physics I')
    enroll('david', 'PHYS201 - Physics II')
    enroll('grace', 'PHYS201 - Physics II')
    enroll('henry', 'PHYS201 - Physics II')

    # ── BACKGROUND STUDENT STATS ──────────────────────────────────────────────
    background_stats = [
        # (username, sem_gpa, cum_gpa, credits_earned, honor_roll)
        ('alice', 3.8, 3.6, 60,  1),
        ('bob',   3.2, 3.0, 45,  0),
        ('carol', 2.9, 2.8, 30,  0),
        ('david', 3.5, 3.3, 75,  1),
        ('eve',   2.5, 2.6, 15,  0),
        ('frank', 3.0, 2.9, 20,  0),
        ('grace', 3.9, 3.8, 90,  1),
        ('henry', 2.8, 2.7, 10,  0),
    ]
    for username, sem_gpa, cum_gpa, credits, honor in background_stats:
        sid = uid(username)
        if sid:
            conn.execute(
                "UPDATE students SET semester_gpa=?, cumulative_gpa=?, credits_earned=?, honor_roll=? WHERE id=?",
                (sem_gpa, cum_gpa, credits, honor, sid)
            )

    # ── TABOO WORDS ───────────────────────────────────────────────────────────
    for word in ['hate', 'stupid', 'idiot', 'terrible', 'awful']:
        conn.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,))

    conn.commit()
    conn.close()
    print("Seed data inserted successfully.")


if __name__ == "__main__":
    init_db()
    seed_data()
    print("\nDone! Run 'python3 app.py' to start the website.")
    print("Login at http://127.0.0.1:5000")
    print("\nAccounts (all password: password123):")
    print("  registrar1    — registrar")
    print("  prof_demo     — demo instructor (2 courses per semester)")
    print("  prof_smith    — instructor")
    print("  prof_jones    — instructor")
    print("  demo_student1 — FRESHMAN: 0 credits, NOT enrolled (enroll live)")
    print("  demo_student2 — SENIOR: 112 credits, needs 4 more credits to hit 8 and graduate, NOT enrolled (enroll live)")
    print("  alice/bob/carol/david/eve/frank/grace/henry — background students")
    print("\nSpring 2026 scenario map:")
    print("  [NORMAL]   CS101, MATH101    — open seats, regular enrollment")
    print("  [CANCEL]   CS201, MATH201    — only 2 enrolled, will cancel when semester runs")
    print("  [WAITLIST] CS301, ENG101     — cap=5, full + 3 on waitlist")
    print("  [CONFLICT] CS401 & CS450     — Smith's classes, same slot Mon/Wed 9am")
    print("  [CONFLICT] PHYS101 & PHYS201 — Jones's classes, same slot Tue/Thu 11am")
