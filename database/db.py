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
        ('registrar1', 'registrar1@college0.com', 'password123', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password123', 'instructor'),
        ('student1', 'student1@college0.com', 'password123', 'student'),
        ('student2', 'student2@college0.com', 'password123', 'student'),
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

    # Spring 2026 — setup
    conn.execute("INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'setup')")
    spring = [
        ('CS101 - Intro to Computing',   'Mon/Wed', 1, '10:00', '11:30', 30),
        ('CS201 - Data Structures',      'Tue/Thu', 3, '13:00', '14:30', 30),
        ('MATH101 - Calculus I',         'Mon/Wed', 1, '11:00', '12:30', 30),  # conflicts CS101
        ('CS999 - Popular Course',       'Fri',     5, '09:00', '11:00',  1),  # full
        ('ENG101 - English Composition', 'Tue/Thu', 3, '09:00', '10:30', 30),
    ]
    for name, time_slot, day, start, end, cap in spring:
        conn.execute(
            "INSERT OR IGNORE INTO courses (course_name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity, semester_id, enrolled_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'active')",
            (name, instructor['id'], time_slot, day, start, end, cap)
        )
    conn.execute("UPDATE courses SET enrolled_count = 1 WHERE course_name = 'CS999 - Popular Course' AND semester_id = 1")

    # Fall 2026 — setup
    conn.execute("INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (2, 'Fall 2026', 'setup')")
    fall = [
        ('CS310 - Algorithms',           'Mon/Wed 09:00-10:30', 30),
        ('CS320 - Operating Systems',    'Tue/Thu 14:00-15:30', 30),
        ('MATH201 - Linear Algebra',     'Tue/Thu 14:30-16:00', 30),
        ('CS888 - Advanced Topics',      'Wed/Fri 13:00-14:30',  1),
        ('ENG201 - Technical Writing',   'Fri 10:00-12:00',     30),
    ]
    for name, slot, cap in fall:
        conn.execute(
            "INSERT OR IGNORE INTO courses (course_name, instructor_id, time_slot, capacity, semester_id, enrolled_count, status) VALUES (?, ?, ?, ?, 2, 0, 'active')",
            (name, instructor['id'], slot, cap)
        )
    conn.execute("UPDATE courses SET enrolled_count = 1 WHERE course_name = 'CS888 - Advanced Topics' AND semester_id = 2")

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
