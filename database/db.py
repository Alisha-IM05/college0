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
    _ensure_runtime_columns(conn)
    conn.commit()
    conn.close()
    print("Database tables created successfully.")


def _ensure_runtime_columns(conn):
    """SQLite CREATE TABLE IF NOT EXISTS does not add columns to old dev DBs."""
    migrations = [
        ("users", "must_change_password", "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"),
        ("users", "clerk_user_id", "ALTER TABLE users ADD COLUMN clerk_user_id TEXT"),
        ("applications", "clerk_user_id", "ALTER TABLE applications ADD COLUMN clerk_user_id TEXT"),
    ]
    for table, column, sql in migrations:
        existing = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing:
            conn.execute(sql)


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
        ('registrar1',    'registrar1@college0.com', 'password123', 'registrar'),
        ('prof_demo',     'demo_prof@college0.com',  'password123', 'instructor'),
        ('prof_smith',    'smith@college0.com',       'password123', 'instructor'),
        ('prof_jones',    'jones@college0.com',       'password123', 'instructor'),
        ('demo_student1', 'demo1@college0.com',       'password123', 'student'),
        ('demo_student2', 'demo2@college0.com',       'password123', 'student'),
        ('alice',         'alice@college0.com',       'password123', 'student'),
        ('bob',           'bob@college0.com',         'password123', 'student'),
        ('carol',         'carol@college0.com',       'password123', 'student'),
        ('david',         'david@college0.com',       'password123', 'student'),
        ('eve',           'eve@college0.com',         'password123', 'student'),
        ('frank',         'frank@college0.com',       'password123', 'student'),
        ('grace',         'grace@college0.com',       'password123', 'student'),
        ('henry',         'henry@college0.com',       'password123', 'student'),
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

    # ── COURSES ───────────────────────────────────────────────────────────────
    # Columns: course_name, instructor_id, time_slot, day_of_week,
    #          start_time, end_time, capacity, semester_id, enrolled_count, status
    #
    # SEMESTER 1 & 2 SCENARIO MAP (same pattern both semesters):
    #
    #  [NORMAL]       CS101/CS202     — demo_student1 enrolls here to show normal flow
    #  [CONFLICT A]   CS101+MATH101 / CS202+MATH201  → Mon/Wed 08:00-09:30
    #  [CONFLICT B]   CS201+BUS101  / CS301+PHYS101  → Tue/Thu 10:00-11:30
    #  [FULL+WAITLIST] ENG101 (sem1) / ENG201 (sem2) → cap=3, filled by background students
    #                  demo_student2 pre-waitlisted (pos 1), enrolled in conflicting Fri course
    #                  → instructor blocked when trying to admit demo_student2 (UC-18 exception)
    #                  → demo_student1 joins waitlist naturally during demo (pos 2)
    #  [UNDER-ENROLL] BUS101 (sem1) / PHYS101 (sem2) → demo_student1 + 1 other = 2 total → cancels
    #                  → triggers UC-19 special registration for demo_student1
    #  [UC-18 BLOCK]  SOC101 (sem1) / SOC201 (sem2) → same Fri slot as ENG101/ENG201
    #                  → demo_student2 enrolled here; causes conflict block on waitlist admit
    #
    # enrolled_count matches exactly the number of enrollment rows seeded below.
    #
    # SEMESTERS 3-6: all normal, 3-5 background students per course, no edge cases.

    all_courses = [
        # ── Semester 1: Fall 2024 ─────────────────────────────────────────────
        # CS101: demo_student1 enrolls here during demo (normal flow). 3 background students pre-seeded.
        ('CS101 - Intro to Computing',  demo_prof_id, 'Mon/Wed', 1, '08:00', '09:30',  5, 1, 3, 'active'),
        # CS201: conflict B partner (same Tue/Thu 10:00 slot as BUS101). 4 background students.
        ('CS201 - Data Structures',     demo_prof_id, 'Tue/Thu', 3, '10:00', '11:30',  5, 1, 4, 'active'),
        # MATH101: conflict A partner (same Mon/Wed 08:00 slot as CS101). 4 background students.
        ('MATH101 - Calculus I',        smith_id,     'Mon/Wed', 1, '08:00', '09:30',  5, 1, 4, 'active'),
        # ENG101: FULL (cap=3). demo_student2 on waitlist pos 1 with Fri conflict. demo_student1 joins pos 2 during demo.
        ('ENG101 - English Comp',       jones_id,     'Fri',     5, '09:00', '11:00',  3, 1, 3, 'active'),
        # BUS101: UNDER-ENROLL. demo_student1 + eve = 2 students → cancels → UC-19 special reg.
        ('BUS101 - Business Writing',   jones_id,     'Tue/Thu', 3, '10:00', '11:30',  5, 1, 2, 'active'),
        # SOC101: UC-18 BLOCK. Same Fri slot as ENG101. demo_student2 enrolled here.
        ('SOC101 - Intro to Sociology', smith_id,     'Fri',     5, '09:00', '11:00',  5, 1, 1, 'active'),

        # ── Semester 2: Spring 2025 ───────────────────────────────────────────
        # CS202: demo_student1 enrolls here during demo (normal flow). 3 background students pre-seeded.
        ('CS202 - Algorithms',          demo_prof_id, 'Mon/Wed', 1, '08:00', '09:30',  5, 2, 3, 'active'),
        # CS301: conflict B partner (same Tue/Thu 10:00 slot as PHYS101). 4 background students.
        ('CS301 - Operating Systems',   demo_prof_id, 'Tue/Thu', 3, '10:00', '11:30',  5, 2, 4, 'active'),
        # MATH201: conflict A partner (same Mon/Wed 08:00 slot as CS202). 4 background students.
        ('MATH201 - Calculus II',       smith_id,     'Mon/Wed', 1, '08:00', '09:30',  5, 2, 4, 'active'),
        # ENG201: FULL (cap=3). demo_student2 on waitlist pos 1 with Fri conflict. demo_student1 joins pos 2 during demo.
        ('ENG201 - Technical Writing',  jones_id,     'Fri',     5, '13:00', '15:00',  3, 2, 3, 'active'),
        # PHYS101: UNDER-ENROLL. demo_student1 + eve = 2 students → cancels → UC-19 special reg.
        ('PHYS101 - Physics I',         smith_id,     'Tue/Thu', 3, '10:00', '11:30',  5, 2, 2, 'active'),
        # SOC201: UC-18 BLOCK. Same Fri slot as ENG201. demo_student2 enrolled here.
        ('SOC201 - Social Theory',      smith_id,     'Fri',     5, '13:00', '15:00',  5, 2, 1, 'active'),

        # ── Semester 3: Summer 2025 (all normal) ──────────────────────────────
        ('CS150 - Intro to Python',     demo_prof_id, 'Mon/Wed', 1, '09:00', '10:30', 30, 3, 5, 'active'),
        ('CS220 - Database Systems',    demo_prof_id, 'Tue/Thu', 3, '11:00', '12:30', 30, 3, 5, 'active'),
        ('MATH150 - Discrete Math',     jones_id,     'Mon/Wed', 1, '13:00', '14:30', 30, 3, 4, 'active'),
        ('BUS201 - Marketing Basics',   jones_id,     'Tue/Thu', 3, '08:00', '09:30', 30, 3, 4, 'active'),
        ('PHYS201 - Physics II',        smith_id,     'Wed/Fri', 4, '10:00', '11:30', 30, 3, 3, 'active'),

        # ── Semester 4: Fall 2025 (all normal) ───────────────────────────────
        ('CS302 - Computer Networks',   demo_prof_id, 'Mon/Wed', 1, '08:00', '09:30', 30, 4, 5, 'active'),
        ('CS401 - Software Engineering',demo_prof_id, 'Tue/Thu', 3, '10:00', '11:30', 30, 4, 5, 'active'),
        ('MATH301 - Linear Algebra',    smith_id,     'Wed/Fri', 4, '13:00', '14:30', 30, 4, 4, 'active'),
        ('ENG301 - Advanced Writing',   jones_id,     'Fri',     5, '09:00', '11:00', 30, 4, 4, 'active'),
        ('BUS301 - Business Analytics', smith_id,     'Tue/Thu', 3, '08:00', '09:30', 30, 4, 3, 'active'),

        # ── Semester 5: Spring 2026 (all normal) ─────────────────────────────
        ('CS402 - Machine Learning',    demo_prof_id, 'Mon/Wed', 1, '10:00', '11:30', 30, 5, 5, 'active'),
        ('CS450 - Cybersecurity',       demo_prof_id, 'Tue/Thu', 3, '13:00', '14:30', 30, 5, 5, 'active'),
        ('MATH401 - Statistics',        smith_id,     'Mon/Wed', 1, '08:00', '09:30', 30, 5, 4, 'active'),
        ('PHYS301 - Quantum Mechanics', jones_id,     'Wed/Fri', 4, '11:00', '12:30', 30, 5, 4, 'active'),
        ('ENG401 - Creative Writing',   jones_id,     'Fri',     5, '13:00', '15:00', 30, 5, 3, 'active'),

        # ── Semester 6: Fall 2026 (all normal) ───────────────────────────────
        ('CS501 - AI Foundations',      demo_prof_id, 'Mon/Wed', 1, '10:00', '11:30', 30, 6, 5, 'active'),
        ('CS520 - Cloud Computing',     demo_prof_id, 'Tue/Thu', 3, '13:00', '14:30', 30, 6, 5, 'active'),
        ('MATH501 - Real Analysis',     smith_id,     'Wed/Fri', 4, '08:00', '09:30', 30, 6, 4, 'active'),
        ('BUS401 - Entrepreneurship',   jones_id,     'Tue/Thu', 3, '11:00', '12:30', 30, 6, 4, 'active'),
        ('ENG501 - Literature Survey',  smith_id,     'Fri',     5, '09:00', '11:00', 30, 6, 3, 'active'),
    ]

    for (name, inst_id, slot, day, start, end, cap, sem_id, enrolled, status) in all_courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, inst_id, slot, day, start, end, cap, sem_id, enrolled, status)
        )
    conn.commit()

    def cid(course_name, sem_id):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = ?",
            (course_name, sem_id)
        ).fetchone()
        return row['id'] if row else None

    # ── SEMESTER 1 ENROLLMENTS ────────────────────────────────────────────────

    # CS101 [NORMAL] — 3 background students pre-seeded; demo_student1 enrolls during demo
    for sid in [alice_id, bob_id, carol_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('CS101 - Intro to Computing', 1)))

    # CS201 [CONFLICT B] — 4 background students (same slot as BUS101)
    for sid in [alice_id, bob_id, carol_id, david_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('CS201 - Data Structures', 1)))

    # MATH101 [CONFLICT A] — 4 background students (same slot as CS101)
    for sid in [eve_id, frank_id, grace_id, henry_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('MATH101 - Calculus I', 1)))

    # ENG101 [FULL cap=3] — alice, bob, carol fill it; demo_student2 on waitlist pos 1 (blocked by conflict)
    for sid in [alice_id, bob_id, carol_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('ENG101 - English Comp', 1)))

    # BUS101 [UNDER-ENROLL] — demo_student1 + eve = 2 → cancels → UC-19 special reg for demo_student1
    for sid in [demo1_id, eve_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('BUS101 - Business Writing', 1)))

    # SOC101 [UC-18 BLOCK] — demo_student2 only; same Fri 09:00-11:00 slot as ENG101
    conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                 (demo2_id, cid('SOC101 - Intro to Sociology', 1)))

    # Waitlist: demo_student2 at pos 1 on ENG101 — instructor gets blocked due to SOC101 conflict
    conn.execute("INSERT OR IGNORE INTO waitlist (student_id, course_id, position) VALUES (?, ?, 1)",
                 (demo2_id, cid('ENG101 - English Comp', 1)))

    conn.commit()

    # ── SEMESTER 2 ENROLLMENTS ────────────────────────────────────────────────

    # CS202 [NORMAL] — 3 background students pre-seeded; demo_student1 enrolls during demo
    for sid in [alice_id, bob_id, carol_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('CS202 - Algorithms', 2)))

    # CS301 [CONFLICT B] — 4 background students (same slot as PHYS101)
    for sid in [alice_id, bob_id, carol_id, david_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('CS301 - Operating Systems', 2)))

    # MATH201 [CONFLICT A] — 4 background students (same slot as CS202)
    for sid in [eve_id, frank_id, grace_id, henry_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('MATH201 - Calculus II', 2)))

    # ENG201 [FULL cap=3] — alice, bob, carol fill it; demo_student2 on waitlist pos 1 (blocked by conflict)
    for sid in [alice_id, bob_id, carol_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('ENG201 - Technical Writing', 2)))

    # PHYS101 [UNDER-ENROLL] — demo_student1 + eve = 2 → cancels → UC-19 special reg for demo_student1
    for sid in [demo1_id, eve_id]:
        conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                     (sid, cid('PHYS101 - Physics I', 2)))

    # SOC201 [UC-18 BLOCK] — demo_student2 only; same Fri 13:00-15:00 slot as ENG201
    conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                 (demo2_id, cid('SOC201 - Social Theory', 2)))

    # Waitlist: demo_student2 at pos 1 on ENG201 — instructor gets blocked due to SOC201 conflict
    conn.execute("INSERT OR IGNORE INTO waitlist (student_id, course_id, position) VALUES (?, ?, 1)",
                 (demo2_id, cid('ENG201 - Technical Writing', 2)))

    conn.commit()

    # ── SEMESTERS 3-6 ENROLLMENTS (all normal, actual rows) ──────────────────
    # enrolled_count in courses table above matches these row counts exactly
    normal_enrollments = [
        # Semester 3
        ('CS150 - Intro to Python',      3, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('CS220 - Database Systems',     3, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('MATH150 - Discrete Math',      3, [frank_id, grace_id, henry_id, alice_id]),         # 4
        ('BUS201 - Marketing Basics',    3, [frank_id, grace_id, henry_id, bob_id]),           # 4
        ('PHYS201 - Physics II',         3, [carol_id, david_id, eve_id]),                     # 3
        # Semester 4
        ('CS302 - Computer Networks',    4, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('CS401 - Software Engineering', 4, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('MATH301 - Linear Algebra',     4, [frank_id, grace_id, henry_id, alice_id]),         # 4
        ('ENG301 - Advanced Writing',    4, [frank_id, grace_id, henry_id, bob_id]),           # 4
        ('BUS301 - Business Analytics',  4, [carol_id, david_id, eve_id]),                     # 3
        # Semester 5
        ('CS402 - Machine Learning',     5, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('CS450 - Cybersecurity',        5, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('MATH401 - Statistics',         5, [frank_id, grace_id, henry_id, alice_id]),         # 4
        ('PHYS301 - Quantum Mechanics',  5, [frank_id, grace_id, henry_id, bob_id]),           # 4
        ('ENG401 - Creative Writing',    5, [carol_id, david_id, eve_id]),                     # 3
        # Semester 6
        ('CS501 - AI Foundations',       6, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('CS520 - Cloud Computing',      6, [alice_id, bob_id, carol_id, david_id, eve_id]),  # 5
        ('MATH501 - Real Analysis',      6, [frank_id, grace_id, henry_id, alice_id]),         # 4
        ('BUS401 - Entrepreneurship',    6, [frank_id, grace_id, henry_id, bob_id]),           # 4
        ('ENG501 - Literature Survey',   6, [carol_id, david_id, eve_id]),                     # 3
    ]

    for course_name, sem_id, students in normal_enrollments:
        course_id = cid(course_name, sem_id)
        for sid in students:
            if sid and course_id:
                conn.execute(
                    "INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                    (sid, course_id)
                )
    conn.commit()

    # ── DEMO STUDENT ACADEMIC RECORDS ───────────────────────────────────────────
    demo_grade_seeds = [
        (demo1_id, cid('BUS101 - Business Writing', 1), 'A', 4.0),
        (demo1_id, cid('PHYS101 - Physics I', 2), 'B', 3.0),
        (demo2_id, cid('SOC101 - Intro to Sociology', 1), 'B', 3.0),
        (demo2_id, cid('SOC201 - Social Theory', 2), 'C', 2.0),
    ]
    for student_id, course_id, letter, numeric in demo_grade_seeds:
        if student_id and course_id:
            conn.execute(
                """INSERT OR IGNORE INTO grades
                   (student_id, course_id, letter_grade, numeric_value)
                   VALUES (?, ?, ?, ?)""",
                (student_id, course_id, letter, numeric),
            )

    conn.execute(
        """UPDATE students
           SET semester_gpa = 3.67, cumulative_gpa = 3.67,
               credits_earned = 5, honor_roll = 0, status = 'active'
           WHERE id = ?""",
        (demo1_id,),
    )
    conn.execute(
        """UPDATE students
           SET semester_gpa = 2.50, cumulative_gpa = 2.50,
               credits_earned = 2, honor_roll = 0, status = 'active'
           WHERE id = ?""",
        (demo2_id,),
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
    print("Login at http://127.0.0.1:5001")
    print("\nAccounts (all password: password123):")
    print("  registrar1    — registrar")
    print("  prof_demo     — demo instructor (2 courses per semester)")
    print("  prof_smith    — instructor")
    print("  prof_jones    — instructor")
    print("  demo_student1 — demo student #1")
    print("  demo_student2 — demo student #2")
    print("  alice/bob/carol/david/eve/frank/grace/henry — background students")
    print("")
    print("Semester 1 & 2 scenario map (same pattern both semesters):")
    print("  [NORMAL]        CS101 (sem1) / CS202 (sem2)")
    print("                  3 background students pre-seeded; demo_student1 enrolls here during demo")
    print("  [CONFLICT A]    CS101 + MATH101 / CS202 + MATH201  → Mon/Wed 08:00-09:30")
    print("                  demo_student1 tries MATH101/MATH201 after enrolling in CS101/CS202 → blocked")
    print("  [CONFLICT B]    CS201 + BUS101 (sem1) / CS301 + PHYS101 (sem2)  → Tue/Thu 10:00-11:30")
    print("  [FULL+WAITLIST] ENG101 (sem1) / ENG201 (sem2)  cap=3, filled by alice/bob/carol")
    print("                  demo_student2 pre-waitlisted pos 1, enrolled in conflicting SOC101/SOC201")
    print("                  → instructor blocked admitting demo_student2 (UC-18 exceptional)")
    print("                  → demo_student1 joins waitlist pos 2 naturally during demo")
    print("  [UNDER-ENROLL]  BUS101 (sem1) / PHYS101 (sem2)  demo_student1 + eve = 2 students")
    print("                  → cancels when advancing to running → UC-19 special reg for demo_student1")
    print("  [UC-18 BLOCK]   SOC101 (sem1) / SOC201 (sem2)  same Fri slot as ENG101/ENG201")
    print("                  demo_student2 enrolled here → causes conflict block on waitlist admit")
    print("")
    print("Semesters 3-6: all normal, 3-5 background students enrolled per course, no edge cases.")
