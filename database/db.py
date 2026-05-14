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
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if user:
                conn.execute("INSERT OR IGNORE INTO students (id) VALUES (?)", (user['id'],))
    conn.commit()

    def uid(username):
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return row['id'] if row else None

    smith_id = uid('prof_smith')
    jones_id = uid('prof_jones')
    demo1_id = uid('demo_student1')
    demo2_id = uid('demo_student2')

    # ── TWO SEMESTERS ─────────────────────────────────────────────────────────
    conn.execute("INSERT INTO semesters (id, name, current_period) VALUES (1, 'Fall 2025',   'grading')")
    conn.execute("INSERT INTO semesters (id, name, current_period) VALUES (2, 'Spring 2026', 'setup')")
    conn.commit()

    # ── FALL 2025 COURSES (10 courses — completed semester) ───────────────────
    fall_courses = [
        ('CS100 - Intro to CS',       'Mon/Wed', 1, '08:00', '09:30', 10, smith_id),
        ('CS110 - Web Dev Basics',    'Tue/Thu', 3, '08:00', '09:30', 10, smith_id),
        ('CS120 - Data Structures',   'Mon/Wed', 1, '10:00', '11:30', 10, smith_id),
        ('CS130 - Databases',         'Tue/Thu', 3, '10:00', '11:30', 10, smith_id),
        ('CS140 - Software Eng',      'Fri',     5, '09:00', '10:30', 10, smith_id),
        ('MATH100 - Pre-Calculus',    'Mon/Wed', 1, '12:00', '13:30', 10, jones_id),
        ('MATH110 - Statistics',      'Tue/Thu', 3, '12:00', '13:30', 10, jones_id),
        ('ENG100 - Academic Writing', 'Mon/Wed', 1, '14:00', '15:30', 10, jones_id),
        ('PHYS100 - Physics I',       'Tue/Thu', 3, '14:00', '15:30', 10, jones_id),
        ('HIST100 - World History',   'Fri',     5, '11:00', '12:30', 10, jones_id),
    ]
    for name, slot, day, start, end, cap, inst_id in fall_courses:
        conn.execute(
            """INSERT INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'active')""",
            (name, inst_id, slot, day, start, end, cap)
        )
    conn.commit()

    def cid(course_name, sem_id):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = ?",
            (course_name, sem_id)
        ).fetchone()
        return row['id'] if row else None

    def enroll(username, course_name, sem_id):
        student_id = uid(username)
        course_id  = cid(course_name, sem_id)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                (student_id, course_id)
            )
            conn.execute(
                "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
                (course_id,)
            )

    def add_grade(username, course_name, sem_id, letter, numeric):
        student_id = uid(username)
        course_id  = cid(course_name, sem_id)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO grades (student_id, course_id, letter_grade, numeric_value) VALUES (?, ?, ?, ?)",
                (student_id, course_id, letter, numeric)
            )

    def waitlist(username, course_name, sem_id, position):
        student_id = uid(username)
        course_id  = cid(course_name, sem_id)
        if student_id and course_id:
            conn.execute(
                "INSERT OR IGNORE INTO waitlist (student_id, course_id, position) VALUES (?, ?, ?)",
                (student_id, course_id, position)
            )

    # ── FALL 2025 ENROLLMENTS & GRADES ────────────────────────────────────────
    fall_data = [
        ('alice', 'CS100 - Intro to CS',       'A',  4.0),
        ('alice', 'MATH100 - Pre-Calculus',    'A',  4.0),
        ('alice', 'ENG100 - Academic Writing', 'B+', 3.3),
        ('bob',   'CS100 - Intro to CS',       'B',  3.0),
        ('bob',   'CS110 - Web Dev Basics',    'B+', 3.3),
        ('bob',   'MATH100 - Pre-Calculus',    'B',  3.0),
        ('carol', 'CS120 - Data Structures',   'C+', 2.3),
        ('carol', 'MATH110 - Statistics',      'B-', 2.7),
        ('carol', 'ENG100 - Academic Writing', 'B',  3.0),
        ('david', 'CS130 - Databases',         'A-', 3.7),
        ('david', 'PHYS100 - Physics I',       'A',  4.0),
        ('david', 'HIST100 - World History',   'A-', 3.7),
        ('eve',   'CS140 - Software Eng',      'C',  2.0),
        ('eve',   'MATH110 - Statistics',      'C+', 2.3),
        ('frank', 'ENG100 - Academic Writing', 'B-', 2.7),
        ('frank', 'HIST100 - World History',   'C',  2.0),
        ('grace', 'CS100 - Intro to CS',       'A',  4.0),
        ('grace', 'PHYS100 - Physics I',       'A-', 3.7),
        ('henry', 'CS110 - Web Dev Basics',    'C+', 2.3),
        ('henry', 'MATH100 - Pre-Calculus',    'C',  2.0),
    ]
    for username, course, letter, numeric in fall_data:
        enroll(username, course, 1)
        add_grade(username, course, 1, letter, numeric)
    conn.commit()

    # ── SPRING 2026 COURSES (10 courses — live demo semester) ─────────────────
    # [NORMAL]   CS101, MATH101        — open seats, enroll demo students live
    # [CANCEL]   CS201, MATH201        — only 2 enrolled, will cancel when enforced
    # [WAITLIST] CS301, ENG101         — cap=5, full + 3 on waitlist
    # [CONFLICT] CS401 & CS450         — same Mon/Wed 9am slot (Smith)
    # [CONFLICT] PHYS101 & PHYS201     — same Tue/Thu 11am slot (Jones)
    spring_courses = [
        ('CS101 - Intro to Computing', 'Mon/Wed', 1, '08:00', '09:30', 10, smith_id),
        ('CS201 - Discrete Math',      'Tue/Thu', 3, '10:00', '11:30', 10, smith_id),
        ('CS301 - Algorithms',         'Fri',     5, '13:00', '14:30',  5, smith_id),
        ('CS401 - Operating Systems',  'Mon/Wed', 1, '09:00', '10:30', 10, smith_id),
        ('CS450 - Computer Networks',  'Mon/Wed', 1, '09:00', '10:30', 10, smith_id),
        ('MATH101 - Calculus I',       'Tue/Thu', 3, '08:00', '09:30', 10, jones_id),
        ('MATH201 - Calculus II',      'Wed/Fri', 4, '08:00', '09:30', 10, jones_id),
        ('ENG101 - English Comp',      'Mon/Wed', 1, '14:00', '15:30',  5, jones_id),
        ('PHYS101 - Physics I',        'Tue/Thu', 3, '11:00', '12:30', 10, jones_id),
        ('PHYS201 - Physics II',       'Tue/Thu', 3, '11:00', '12:30', 10, jones_id),
    ]
    for name, slot, day, start, end, cap, inst_id in spring_courses:
        conn.execute(
            """INSERT INTO courses
               (course_name, instructor_id, time_slot, day_of_week, start_time, end_time,
                capacity, semester_id, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 2, 0, 'active')""",
            (name, inst_id, slot, day, start, end, cap)
        )
    conn.commit()

    # Demo students NOT enrolled — enroll live during demo
    conn.execute("UPDATE students SET semester_gpa=0.0, cumulative_gpa=0.0, credits_earned=0, honor_roll=0 WHERE id=?", (demo1_id,))
    conn.execute("UPDATE students SET semester_gpa=3.8, cumulative_gpa=3.6, credits_earned=4,  honor_roll=1 WHERE id=?", (demo2_id,))

    # NORMAL courses
    for s in ['alice', 'bob', 'carol', 'david']:
        enroll(s, 'CS101 - Intro to Computing', 2)
    for s in ['alice', 'bob', 'carol']:
        enroll(s, 'MATH101 - Calculus I', 2)

    # CANCEL courses
    for s in ['eve', 'frank']:
        enroll(s, 'CS201 - Discrete Math', 2)
        enroll(s, 'MATH201 - Calculus II', 2)

    # WAITLIST courses (cap=5, 5 enrolled + 3 on waitlist)
    for s in ['alice', 'bob', 'carol', 'david', 'grace']:
        enroll(s, 'CS301 - Algorithms', 2)
        enroll(s, 'ENG101 - English Comp', 2)
    for s, pos in [('henry', 1), ('eve', 2), ('frank', 3)]:
        waitlist(s, 'CS301 - Algorithms', 2, pos)
        waitlist(s, 'ENG101 - English Comp', 2, pos)

    # CONFLICT courses
    for s in ['alice', 'bob', 'carol']:
        enroll(s, 'CS401 - Operating Systems', 2)
    for s in ['david', 'grace', 'henry']:
        enroll(s, 'CS450 - Computer Networks', 2)
    for s in ['alice', 'bob', 'carol']:
        enroll(s, 'PHYS101 - Physics I', 2)
    for s in ['david', 'grace', 'henry']:
        enroll(s, 'PHYS201 - Physics II', 2)

    # Background student stats
    background_stats = [
        ('alice', 3.8, 3.6, 60, 1),
        ('bob',   3.2, 3.0, 45, 0),
        ('carol', 2.9, 2.8, 30, 0),
        ('david', 3.5, 3.3, 75, 1),
        ('eve',   2.5, 2.6, 15, 0),
        ('frank', 3.0, 2.9, 20, 0),
        ('grace', 3.9, 3.8, 90, 1),
        ('henry', 2.8, 2.7, 10, 0),
    ]
    for username, sem_gpa, cum_gpa, credits, honor in background_stats:
        sid = uid(username)
        if sid:
            conn.execute(
                "UPDATE students SET semester_gpa=?, cumulative_gpa=?, credits_earned=?, honor_roll=? WHERE id=?",
                (sem_gpa, cum_gpa, credits, honor, sid)
            )

    # Taboo words
    for word in ['hate', 'stupid', 'idiot', 'terrible', 'awful']:
        conn.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,))

    conn.commit()
    conn.close()
    print("Seed data inserted successfully.")


if __name__ == "__main__":
    init_db()
    seed_data()
    print("\nDone! Run 'python3 app.py' to start.")
    print("Login at http://127.0.0.1:5000  (all passwords: password123)")
    print("\nAccounts:")
    print("  registrar1    — registrar")
    print("  prof_smith    — instructor (5 courses each semester)")
    print("  prof_jones    — instructor (5 courses each semester)")
    print("  demo_student1 — freshman, 0 credits, NOT enrolled (enroll live)")
    print("  demo_student2 — 4 credits + honor roll, NOT enrolled (enroll live)")
    print("  alice/bob/carol/david/eve/frank/grace/henry — background students")
    print("\nSemesters:")
    print("  Fall 2025   — grading period, 10 courses, grades submitted")
    print("  Spring 2026 — setup period, 10 courses, LIVE DEMO")
    print("\nSpring 2026 scenario map:")
    print("  [NORMAL]   CS101, MATH101    — open seats")
    print("  [CANCEL]   CS201, MATH201    — only 2 enrolled, will cancel")
    print("  [WAITLIST] CS301, ENG101     — cap=5, full + 3 on waitlist")
    print("  [CONFLICT] CS401 & CS450     — same Mon/Wed 9am (Smith)")
    print("  [CONFLICT] PHYS101 & PHYS201 — same Tue/Thu 11am (Jones)")