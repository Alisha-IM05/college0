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

    # --- Zhuolin's users ---
    users = [
        ("registrar1", "password", "registrar", "active"),
        ("student1",   "password", "student",   "active"),
        ("student2",   "password", "student",   "active"),
        ("instructor1","password", "instructor", "active"),
        ("instructor2","password", "instructor", "active"),
    ]
    for email, password, role, status in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (email, password, role, status) VALUES (?, ?, ?, ?)",
            (email, password, role, status)
        )

    # --- Tanzina's semester and courses ---
    conn.execute(
        "INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'registration')"
    )
    courses = [
        (1, "CS101 - Intro to Computing",  2, "Mon/Wed 10:00-11:30", 30),
        (1, "CS201 - Data Structures",     2, "Tue/Thu 13:00-14:30", 30),
        (1, "MATH101 - Calculus I",        3, "Mon/Wed 14:00-15:30", 30),
        (1, "ENG101 - English Composition",3, "Fri 09:00-12:00",     30),
    ]
    for semester_id, name, instructor_id, time_slot, capacity in courses:
        conn.execute(
            "INSERT OR IGNORE INTO courses (semester_id, course_name, instructor_id, time_slot, capacity) VALUES (?, ?, ?, ?, ?)",
            (semester_id, name, instructor_id, time_slot, capacity)
        )

    # --- Alisha's taboo words ---
    taboo = ["hate", "stupid", "idiot"]
    for word in taboo:
        conn.execute(
            "INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,)
        )

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
