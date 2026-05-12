import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), 'college0.db')
SCHEMA = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # lets you access columns by name e.g. row['email']
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

    # ── USERS ────────────────────────────────────────────────────────────────
    # registrar1, instructor1, student1, student2
    users = [
        ('registrar1',  'registrar1@college0.com',  'password123', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password123', 'instructor'),
        ('student1',    'student1@college0.com',    'password123', 'student'),
        ('student2',    'student2@college0.com',    'password123', 'student'),
    ]
    for username, email, password, role in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            (username, email, password, role)
        )
        if role == 'student':
            user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if user:
                conn.execute('INSERT OR IGNORE INTO students (id) VALUES (?)', (user['id'],))

    instructor = conn.execute("SELECT id FROM users WHERE role = 'instructor' LIMIT 1").fetchone()
    s1 = conn.execute("SELECT id FROM users WHERE username = 'student1'").fetchone()
    s2 = conn.execute("SELECT id FROM users WHERE username = 'student2'").fetchone()

    # ── SEMESTER ─────────────────────────────────────────────────────────────
    conn.execute(
        "INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'setup')"
    )

    # ── COURSES ──────────────────────────────────────────────────────────────
    # Columns: course_name, time_slot, day_of_week, start_time, end_time, capacity, enrolled_count, status
    #
    # Scenario guide:
    #   [NORMAL]    CS101, CS201, MATH101, ENG101  — 10 seats, 5 already filled (phantom),
    #                                                  student1 enrolls → 6/10, survives cancellation check (≥3)
    #   [NORMAL-S2] BUS101                          — same as above but student2's normal course
    #   [WAITLIST]  CS999                           — capacity=1, enrolled_count=1 (full),
    #                                                  student1 tries to register → goes on waitlist
    #   [CANCEL]    CS150                           — 10 seats, only student1+student2 (count=2 < 3),
    #                                                  gets cancelled during class-running period
    #   [CONFLICT]  PHYS101                         — same time slot as CS101 (Mon/Wed 08:00-09:30),
    #                                                  student1 already in CS101 → conflict blocked
    #   [SPECIAL]   CS220, CS230                    — open seats, not enrolled,
    #                                                  available for special re-registration after CS150 cancellation

    courses = [
        # name                              slot        day  start    end     cap  enrolled  status
        # ── Normal courses (student1 registers into these) ──────────────────────────────────────
        ('CS101 - Intro to Computing',     'Mon/Wed',  1,  '08:00', '09:30', 10,  5, 'active'),
        ('CS201 - Data Structures',        'Tue/Thu',  3,  '10:00', '11:30', 10,  5, 'active'),
        ('MATH101 - Calculus I',           'Wed/Fri',  4,  '13:00', '14:30', 10,  5, 'active'),
        ('ENG101 - English Composition',   'Fri',      5,  '09:00', '11:00', 10,  5, 'active'),
        # ── Normal course (student2 registers into this) ────────────────────────────────────────
        ('BUS101 - Business Writing',      'Tue/Thu',  3,  '08:00', '09:30', 10,  5, 'active'),
        # ── [WAITLIST] capacity=1, already full — joining puts student on waitlist ─────────────
        ('CS999 - Special Topics',         'Tue/Thu',  3,  '15:00', '16:30',  1,  1, 'active'),
        # ── [CANCEL] only 2 real enrollments → gets cancelled in class-running period ──────────
        ('CS150 - Intro to Python',        'Mon/Wed',  1,  '11:00', '12:30', 10,  2, 'active'),
        # ── [CONFLICT] same slot as CS101 (Mon/Wed 08:00-09:30) → blocks student1 ───────────
        ('PHYS101 - Physics I',            'Mon/Wed',  1,  '08:00', '09:30', 10,  5, 'active'),
        # ── [SPECIAL REG] open courses for re-registration after CS150 is cancelled ───────────
        ('CS220 - Database Systems',       'Mon/Wed',  1,  '10:00', '11:30', 10,  0, 'active'),
        ('CS230 - Web Development',        'Fri',      5,  '13:00', '16:00', 10,  0, 'active'),
    ]

    for name, time_slot, day, start, end, cap, enrolled_count, status in courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (name, instructor['id'], time_slot, day, start, end, cap, enrolled_count, status)
        )

    # ── ENROLLMENTS ──────────────────────────────────────────────────────────
    # student1 → CS101, CS201, MATH101, ENG101  (4 normal courses, max allowed)
    # student2 → BUS101, CS150                  (CS150 will be cancelled later)
    # student1 + student2 → CS150               (to reach enrolled_count=2 for cancel test)

    def get_course_id(name):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = 1", (name,)
        ).fetchone()
        return row['id'] if row else None

    enrollments = [
        # student1's 4 normal enrollments
        (s1['id'], get_course_id('CS101 - Intro to Computing')),
        (s1['id'], get_course_id('CS201 - Data Structures')),
        (s1['id'], get_course_id('MATH101 - Calculus I')),
        (s1['id'], get_course_id('ENG101 - English Composition')),
        # student2's normal enrollment
        (s2['id'], get_course_id('BUS101 - Business Writing')),
        # both in CS150 → enrolled_count=2, triggers cancellation
        (s1['id'], get_course_id('CS150 - Intro to Python')),
        (s2['id'], get_course_id('CS150 - Intro to Python')),
    ]

    for student_id, course_id in enrollments:
        if course_id:
            conn.execute(
                """INSERT OR IGNORE INTO enrollments (student_id, course_id, status)
                   VALUES (?, ?, 'enrolled')""",
                (student_id, course_id)
            )

    # ── WAITLIST ─────────────────────────────────────────────────────────────
    # CS999 is full (capacity=1, enrolled_count=1).
    # Pre-seed student2 on the waitlist so the feature is visible immediately.
    cs999_id = get_course_id('CS999 - Special Topics')
    if cs999_id:
        conn.execute(
            """INSERT OR IGNORE INTO waitlist (student_id, course_id, position)
               VALUES (?, ?, 1)""",
            (s2['id'], cs999_id)
        )

    # ── TABOO WORDS ──────────────────────────────────────────────────────────
    for word in ['hate', 'stupid', 'idiot']:
        conn.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,))

    conn.commit()
    conn.close()
    print("Seed data inserted successfully.")


if __name__ == "__main__":
    init_db()
    seed_data()
    print("\nDone! Run 'python app.py' to start the website.")
    print("Login at http://127.0.0.1:5000")
    print("\nTest accounts:")
    print("  registrar1  / password123")
    print("  instructor1 / password123")
    print("  student1    / password123")
    print("  student2    / password123")
    print()
    print("Scenario map:")
    print("  [NORMAL]   student1 enrolled in CS101, CS201, MATH101, ENG101")
    print("  [NORMAL]   student2 enrolled in BUS101")
    print("  [CANCEL]   CS150 has only 2 enrollments → gets cancelled in class-running period")
    print("  [WAITLIST] CS999 is full (cap=1) → student1 joining goes to waitlist")
    print("  [CONFLICT] PHYS101 = same slot as CS101 → blocks student1")
    print("  [SPECIAL]  CS220, CS230 open for special re-reg after CS150 cancellation")