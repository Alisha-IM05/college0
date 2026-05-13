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

    #    --- Zhuolin's users ---

    users = [
        ('registrar1', 'registrar1@college0.com', 'password', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password', 'instructor'),
        ('student1', 'student1@college0.com', 'password', 'student'),
        ('student2', 'student2@college0.com', 'password', 'student'),
        ('nathan', 'nathan@college0.com', 'password', 'student'),
        ('maya', 'maya@college0.com', 'password', 'student'),
        ('liam', 'liam@college0.com', 'password', 'student'),
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


        # --- Tanzina's semester and courses ---

    # ── SPRING 2026 ──────────────────────────────────────────────────────────


    conn.execute("INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'setup')")

    # name, time_slot, day_of_week, start, end, capacity
    spring_courses = [
        # [A] Normal courses — student1 enrolled, filled to 3+ to survive cancellation
        ('CS101 - Intro to Computing',      'Mon/Wed', 1, '08:00', '09:30', 30),
        ('CS201 - Data Structures',         'Tue/Thu', 3, '10:00', '11:30', 30),
        ('ENG101 - English Composition',    'Fri',     5, '09:00', '11:00', 30),
        # [B] Conflict testers — both Mon/Wed 13:00-14:30, registering second = conflict
        ('MATH101 - Calculus I',            'Mon/Wed', 1, '13:00', '14:30', 30),
        ('PHYS101 - Physics I',             'Mon/Wed', 1, '13:00', '14:30', 30),
        # [C] Waitlist tester — capacity 1, already has 1 enrolled, join = waitlist
        ('CS999 - Special Topics',          'Tue/Thu', 3, '15:00', '16:30',  1),
        # [D] Cancel tester — only student1+student2 enrolled (count=2 < 3), gets cancelled
        ('CS150 - Intro to Python',         'Wed/Fri', 4, '11:00', '12:30', 30),
        # [F] Bonus normal survivor
        ('BUS101 - Business Writing',       'Tue/Thu', 3, '08:00', '09:30', 30),
        # [E] Special reg replacements — NOT enrolled, active, open seats
        ('CS220 - Database Systems',        'Mon/Wed', 1, '10:00', '11:30', 30),
        ('CS230 - Web Development',         'Fri',     5, '13:00', '16:00', 30),
    ]
    for name, time_slot, day, start, end, cap in spring_courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'active')""",
            (name, instructor['id'], time_slot, day, start, end, cap)
        )

    # Helper to get course id
    def get_course(name, sem_id):
        return conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = ?",
            (name, sem_id)
        ).fetchone()

    def get_student(username):
        return conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()

    s1 = get_student('student1')
    s2 = get_student('student2')


    # ── FALL 2026 ─────────────────────────────────────────────────────────────
    # Same structure as Spring for consistency
    conn.execute("INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (2, 'Fall 2026', 'setup')")

    fall_courses = [
        # [A] Normal courses — 3+ enrolled, survive
        ('CS310 - Algorithms',              'Mon/Wed', 1, '08:00', '09:30', 30),
        ('CS320 - Operating Systems',       'Tue/Thu', 3, '10:00', '11:30', 30),
        ('ENG201 - Technical Writing',      'Fri',     5, '09:00', '11:00', 30),
        # [B] Conflict testers — both Tue/Thu 13:00-14:30
        ('MATH201 - Linear Algebra',        'Tue/Thu', 3, '13:00', '14:30', 30),
        ('PHYS201 - Physics II',            'Tue/Thu', 3, '13:00', '14:30', 30),
        # [C] Waitlist tester — capacity 1, full
        ('CS888 - Advanced Topics',         'Mon/Wed', 1, '15:00', '16:30',  1),
        # [D] Cancel tester — only 2 enrolled, gets cancelled
        ('CS350 - Computer Networks',       'Wed/Fri', 4, '11:00', '12:30', 30),
        # [F] Bonus normal survivor
        ('BUS201 - Project Management',     'Tue/Thu', 3, '08:00', '09:30', 30),
        # [E] Special reg replacements — open seats, not enrolled
        ('CS410 - Machine Learning',        'Mon/Wed', 1, '10:00', '11:30', 30),
        ('CS420 - Cloud Computing',         'Fri',     5, '13:00', '16:00', 30),
    ]
    for name, time_slot, day, start, end, cap in fall_courses:
        conn.execute(
            """INSERT OR IGNORE INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 2, 0, 'active')""",
            (name, instructor['id'], time_slot, day, start, end, cap)
        )



    # Taboo words
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
    print("  registrar1 / password")
    print("  student1   / password")
    print("  instructor1 / password")
