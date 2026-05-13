from flask import Flask, render_template, request, redirect, url_for, session
from jinja2 import ChoiceLoader, FileSystemLoader
from modules.ai_features import register_ai_routes
from database.db import init_db, get_db

from modules.conduct import (
    submit_review, get_course_reviews,
    file_complaint, get_pending_complaints, resolve_complaint,
    get_taboo_words, add_taboo_word, remove_taboo_word,
    get_user_warnings, get_warning_count, issue_warning
)

from modules.semester import ( advance_period, create_course,  register_student, admit_from_waitlist,enforce_minimums, submit_grade, apply_for_graduation, resolve_graduation)

app = Flask(__name__)
app.jinja_loader = ChoiceLoader([
    FileSystemLoader('templates'),
])

app.secret_key = 'college0secretkey'

# initialize the database and vector store when the app starts
with app.app_context():
    init_db()

register_ai_routes(app)   # Subsystem 5 — mounts all /ai/* routes from modules/ai_features.py


# ── TEMPORARY LOGIN (until Zhuolin builds real auth) ─────────────────────────

def create_test_users():
    conn = get_db()
    test_users = [
        ('registrar1', 'registrar1@college0.com', 'password', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password', 'instructor'),
        ('instructor2', 'instructor2@college0.com', 'password', 'instructor'),
        ('student1', 'student1@college0.com', 'password', 'student'),
        ('student2',   'student2@college0.com',   'password', 'student'),
        ('nathan', 'nathan@college0.com', 'password', 'student'),
        ('maya', 'maya@college0.com', 'password', 'student'),
        ('liam', 'liam@college0.com', 'password', 'student'),
    ]
    for username, email, password, role in test_users:
        conn.execute(
            """INSERT OR IGNORE INTO users (username, email, password, role)
               VALUES (?, ?, ?, ?)""",
            (username, email, password, role)
        )
        conn.execute(
            "UPDATE users SET password = ?, role = ? WHERE username = ?",
            (password, role, username)
        )
        if role == 'student':
            user = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            conn.execute("INSERT OR IGNORE INTO students (id) VALUES (?)", (user['id'],))

    conn.execute(
        """DELETE FROM students
           WHERE id IN (SELECT s.id FROM students s JOIN users u ON s.id = u.id WHERE u.role != 'student')"""
    )

    def user_id(username):
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return row['id'] if row else None

    instructor1 = user_id('instructor1')
    instructor2 = user_id('instructor2')

    conn.execute(
        "INSERT OR IGNORE INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'running')"
    )
    conn.execute(
        "UPDATE semesters SET current_period = 'running' WHERE id = 1"
    )

    demo_courses = [
        ('CS101 - Intro to Computing', instructor1, 'Mon/Wed', 1, '10:00', '11:30', 30),
        ('CS201 - Data Structures', instructor1, 'Tue/Thu', 3, '13:00', '14:30', 30),
        ('MATH101 - Calculus I', instructor2, 'Mon/Wed', 1, '14:00', '15:30', 30),
        ('ENG101 - English Composition', instructor2, 'Fri', 5, '09:00', '12:00', 30),
        ('CS310 - Algorithms', instructor1, 'Mon/Wed', 1, '12:00', '13:30', 25),
        ('CS410 - Machine Learning', instructor2, 'Tue/Thu', 3, '10:00', '11:30', 20),
    ]
    for name, instructor_id, slot, day, start, end, cap in demo_courses:
        existing = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = 1",
            (name,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE courses
                   SET instructor_id = ?, time_slot = ?, day_of_week = ?,
                       start_time = ?, end_time = ?, capacity = ?, status = 'active'
                   WHERE id = ?""",
                (instructor_id, slot, day, start, end, cap, existing['id'])
            )
        else:
            conn.execute(
                """INSERT INTO courses
                   (course_name, instructor_id, time_slot, day_of_week, start_time,
                    end_time, capacity, semester_id, enrolled_count, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'active')""",
                (name, instructor_id, slot, day, start, end, cap)
            )

    def course_id(name):
        row = conn.execute(
            "SELECT id FROM courses WHERE course_name = ? AND semester_id = 1",
            (name,)
        ).fetchone()
        return row['id'] if row else None

    demo_students = {
        'student1': {'semester_gpa': 3.20, 'cumulative_gpa': 3.15, 'credits_earned': 42, 'status': 'active', 'honor_roll': 0},
        'student2': {'semester_gpa': 2.70, 'cumulative_gpa': 2.85, 'credits_earned': 36, 'status': 'active', 'honor_roll': 0},
        'nathan': {'semester_gpa': 3.42, 'cumulative_gpa': 3.42, 'credits_earned': 48, 'status': 'active', 'honor_roll': 0},
        'maya': {'semester_gpa': 3.90, 'cumulative_gpa': 3.88, 'credits_earned': 72, 'status': 'active', 'honor_roll': 1},
        'liam': {'semester_gpa': 1.80, 'cumulative_gpa': 1.95, 'credits_earned': 30, 'status': 'probation', 'honor_roll': 0},
    }
    for username, data in demo_students.items():
        sid = user_id(username)
        if sid:
            conn.execute(
                """UPDATE students
                   SET semester_gpa = ?, cumulative_gpa = ?, credits_earned = ?,
                       status = ?, honor_roll = ?
                   WHERE id = ?""",
                (
                    data['semester_gpa'], data['cumulative_gpa'],
                    data['credits_earned'], data['status'], data['honor_roll'], sid
                )
            )

    demo_enrollments = {
        'student1': ['CS101 - Intro to Computing', 'ENG101 - English Composition'],
        'student2': ['MATH101 - Calculus I'],
        'nathan': ['CS101 - Intro to Computing', 'CS201 - Data Structures', 'CS410 - Machine Learning'],
        'maya': ['CS310 - Algorithms', 'CS410 - Machine Learning'],
        'liam': ['ENG101 - English Composition', 'MATH101 - Calculus I'],
    }
    for username, course_names in demo_enrollments.items():
        sid = user_id(username)
        for course_name in course_names:
            cid = course_id(course_name)
            if sid and cid:
                exists = conn.execute(
                    """SELECT id FROM enrollments
                       WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
                    (sid, cid)
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                        (sid, cid)
                    )

    grade_values = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
    demo_grades = {
        'student1': [('CS101 - Intro to Computing', 'B')],
        'student2': [('ENG101 - English Composition', 'B')],
        'nathan': [('CS101 - Intro to Computing', 'A'), ('ENG101 - English Composition', 'B')],
        'maya': [('CS101 - Intro to Computing', 'A'), ('CS201 - Data Structures', 'A')],
        'liam': [('CS101 - Intro to Computing', 'D'), ('CS201 - Data Structures', 'F')],
    }
    for username, grades in demo_grades.items():
        sid = user_id(username)
        for course_name, letter in grades:
            cid = course_id(course_name)
            if sid and cid:
                exists = conn.execute(
                    "SELECT id FROM grades WHERE student_id = ? AND course_id = ?",
                    (sid, cid)
                ).fetchone()
                if exists:
                    conn.execute(
                        "UPDATE grades SET letter_grade = ?, numeric_value = ? WHERE id = ?",
                        (letter, grade_values[letter], exists['id'])
                    )
                else:
                    conn.execute(
                        """INSERT INTO grades
                           (student_id, course_id, letter_grade, numeric_value)
                           VALUES (?, ?, ?, ?)""",
                        (sid, cid, letter, grade_values[letter])
                    )

    course_ids = [
        course_id(name) for name, *_ in demo_courses
    ]
    for cid in course_ids:
        if cid:
            count = conn.execute(
                """SELECT COUNT(*) FROM enrollments
                   WHERE course_id = ? AND status = 'enrolled'""",
                (cid,)
            ).fetchone()[0]
            conn.execute("UPDATE courses SET enrolled_count = ? WHERE id = ?", (count, cid))

    for word in ['hate', 'stupid', 'idiot']:
        conn.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,))

    conn.commit()
    conn.close()

create_test_users()


# ── LOGIN / LOGOUT ────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password)
    ).fetchone()
    conn.close()

    if user:
        session['user_id']  = user['id']
        session['username'] = user['username']
        session['role']     = user['role']
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid username or password.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters 
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    student_data = None
    student_data = conn.execute(
            """SELECT u.*, s.semester_gpa, s.cumulative_gpa, s.credits_earned, s.honor_roll
               FROM users u
               LEFT JOIN students s ON u.id = s.id
               WHERE u.id = ?""",
            (session['user_id'],)
        ).fetchone()
    grades = conn.execute(
            """SELECT g.letter_grade, g.numeric_value, c.course_name, s.name as semester_name
               FROM grades g
               JOIN courses c ON g.course_id = c.id
               JOIN semesters s ON c.semester_id = s.id
               WHERE g.student_id = ?
               ORDER BY s.id DESC""",
            (session['user_id'],)
        ).fetchall()
    conn.close()
    return render_template('dashboard.html',
                           username=session['username'],
                           role=session['role'],
                           semester=semester,
                           student_data=student_data,
                           grades=grades)
    
    
#start of Tanzina's code
# ── COURSES / REGISTRATION ────────────────────────────────────────────────────

@app.route('/courses/register')
def course_registration():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    special_registration = False
    if session['role'] == 'student':
        sr = conn.execute(
            "SELECT special_registration FROM students WHERE id = ?",
            (session['user_id'],)
        ).fetchone()
        special_registration = sr and sr['special_registration'] == 1
    courses = conn.execute(
        """SELECT c.*, u.username as instructor_name,
           c.time_slot || ' ' || c.start_time || '-' || c.end_time as display_slot
           FROM courses c
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE c.status = 'active' AND c.semester_id = ?""",
        (semester['id'],)
    ).fetchall()
    enrolled = conn.execute(
        """SELECT c.*, u.username as instructor_name 
           FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'enrolled'
           AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    cancelled_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name 
           FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'cancelled'
           AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    waitlisted = conn.execute(
        """SELECT w.*, c.course_name, c.time_slot
           FROM waitlist w
           JOIN courses c ON w.course_id = c.id
           WHERE w.student_id = ?
           ORDER BY w.course_id""",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    
    return render_template('courses/register.html',
                           courses=courses,
                           semester=semester,
                           enrolled=enrolled,
                           cancelled_courses=cancelled_courses,                           
                           role=session['role'],
                           username=session['username'],
                           waitlisted=waitlisted,
                           special_registration=special_registration)
@app.route('/instructor/courses')
def instructor_courses():
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    courses = conn.execute(
        """SELECT c.*, s.name as semester_name, s.current_period,
           (SELECT COUNT(*) FROM waitlist w 
            WHERE w.course_id = c.id AND w.status = 'pending') as waitlist_count
           FROM courses c
           JOIN semesters s ON c.semester_id = s.id
           WHERE c.instructor_id = ? AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    conn.close()
    return render_template('courses/instructor_courses.html',
                           courses=courses,
                           semester=semester,
                           role=session['role'],
                           username=session['username'])

@app.route('/courses/register/<int:course_id>', methods=['POST'])
def register_for_course(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    message = register_student(session['user_id'], course_id)
    
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    special_registration = False
    if session['role'] == 'student':
        sr = conn.execute(
            "SELECT special_registration FROM students WHERE id = ?",
            (session['user_id'],)
        ).fetchone()
        special_registration = sr and sr['special_registration'] == 1
    courses = conn.execute(
        """SELECT c.*, u.username as instructor_name,
           c.time_slot || ' ' || c.start_time || '-' || c.end_time as display_slot
           FROM courses c
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE c.status = 'active' AND c.semester_id = ?""",
        (semester['id'],)
    ).fetchall()
    enrolled = conn.execute(
        """SELECT c.*, u.username as instructor_name 
           FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'enrolled'
           AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    cancelled_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name 
           FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'cancelled'
           AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    waitlisted = conn.execute(
        """SELECT w.*, c.course_name, c.time_slot
           FROM waitlist w
           JOIN courses c ON w.course_id = c.id
           WHERE w.student_id = ?
           ORDER BY w.course_id""",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    
    return render_template('courses/register.html',
                           courses=courses,
                           semester=semester,
                           enrolled=enrolled,
                           cancelled_courses=cancelled_courses,
                           role=session['role'],
                           username=session['username'],
                           message=message,
                           waitlisted=waitlisted,
                           special_registration=special_registration)

@app.route('/courses/drop/<int:course_id>', methods=['POST'])
def drop_course(course_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('home'))
    conn = get_db()
    conn.execute(
        "UPDATE enrollments SET status = 'cancelled' WHERE student_id = ? AND course_id = ?",
        (session['user_id'], course_id)
    )
    conn.execute(
        "UPDATE courses SET enrolled_count = enrolled_count - 1 WHERE id = ?",
        (course_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('course_registration'))
# ── SEMESTER MANAGEMENT (registrar) ──────────────────────────────────────────

@app.route('/semester')
def semester_management():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    conn.close()
    return render_template('semester/manage.html',
                           semester=semester,
                           role=session['role'],
                           username=session['username'])

@app.route('/semester/advance', methods=['POST'])
def advance_semester():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    semester_id = int(request.form['semester_id'])
    message = advance_period(semester_id)
    conn = get_db()
    semester = conn.execute(
        """SELECT * FROM semesters
           ORDER BY CASE current_period
               WHEN 'setup' THEN 1
               WHEN 'registration' THEN 2
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4
               WHEN 'grading' THEN 5
           END DESC LIMIT 1"""
    ).fetchone()
    conn.close()
    return render_template('semester/manage.html',
                           semester=semester,
                           role=session['role'],
                           username=session['username'],
                           message=message)

@app.route('/semester/retreat', methods=['POST'])
def retreat_semester():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    semester_id = int(request.form['semester_id'])
    conn = get_db()
    semester = conn.execute("SELECT * FROM semesters WHERE id = ?", (semester_id,)).fetchone()
    current = semester['current_period']
    PERIOD_ORDER = ['setup', 'registration', 'special_registration', 'running', 'grading']
    if current == 'setup':
        message = 'Already at the first period'
    else:
        current_index = PERIOD_ORDER.index(current)
        prev_period = PERIOD_ORDER[current_index - 1]
        conn.execute("UPDATE semesters SET current_period = ? WHERE id = ?", (prev_period, semester_id))
        conn.commit()
        message = f'Moved back to {prev_period}'
    semester = conn.execute("SELECT * FROM semesters ORDER BY CASE current_period WHEN 'setup' THEN 1 WHEN 'registration' THEN 2 WHEN 'special_registration' THEN 3 WHEN 'running' THEN 4 WHEN 'grading' THEN 5 END DESC LIMIT 1").fetchone()
    conn.close()
    return render_template('semester/manage.html',
                           semester=semester,
                           role=session['role'],
                           username=session['username'],
                           message=message)


# ── CREATE COURSE (registrar) ─────────────────────────────────────────────────

@app.route('/courses/create')
def create_course_page():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    conn = get_db()
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor' AND status = 'active'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = conn.execute(
        """SELECT * FROM semesters 
           ORDER BY CASE current_period 
               WHEN 'setup' THEN 1 
               WHEN 'registration' THEN 2 
               WHEN 'special_registration' THEN 3
               WHEN 'running' THEN 4 
               WHEN 'grading' THEN 5 
           END DESC LIMIT 1"""
    ).fetchone()
    current_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name
           FROM courses c JOIN users u ON c.instructor_id = u.id
           WHERE c.semester_id = ?""",
        (current_semester['id'],)
    ).fetchall()
    conn.close()
    return render_template('courses/create.html',
                           instructors=instructors,
                           semesters=semesters,
                           semester=current_semester,
                           current_courses=current_courses,
                           role=session['role'],
                           username=session['username'])

@app.route('/courses/create', methods=['POST'])
def create_course_route():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    course_id = request.form['course_id']
    name = request.form['name']
    instructor_id = int(request.form['instructor_id'])
    day_of_week = int(request.form['day_of_week'])
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    semester_id = int(request.form['semester_id'])
    capacity = int(request.form['capacity'])
    
    # Build time_slot display string
    day_labels = {'1': 'Mon/Wed', '3': 'Tue/Thu', '4': 'Wed/Fri', '5': 'Fri'}
    day_label = day_labels.get(request.form['day_of_week'], 'Mon/Wed')
    time_slot = f"{day_label} {start_time}-{end_time}"
    
    message = create_course(semester_id, name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity)
    conn = get_db()
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor' AND status = 'active'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = conn.execute("SELECT * FROM semesters ORDER BY CASE current_period WHEN 'setup' THEN 1 WHEN 'registration' THEN 2 WHEN 'special_registration' THEN 3 WHEN 'running' THEN 4 WHEN 'grading' THEN 5 END DESC LIMIT 1").fetchone()
    current_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name
           FROM courses c JOIN users u ON c.instructor_id = u.id
           WHERE c.semester_id = ?""",
        (current_semester['id'],)
    ).fetchall()
    conn.close()
    return render_template('courses/create.html',
                           instructors=instructors,
                           semesters=semesters,
                           semester=current_semester,
                           current_courses=current_courses,
                           role=session['role'],
                           username=session['username'],
                           message=message)
@app.route('/courses/delete/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    conn = get_db()
    conn.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM waitlist WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('create_course_page'))


# ── GRADUATION ────────────────────────────────────────────────────────────────

@app.route('/graduation/apply', methods=['POST'])
def graduation_apply():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('home'))
    message = apply_for_graduation(session['user_id'])
    return redirect(url_for('dashboard') + f'?message={message}')

@app.route('/graduation/resolve')
def graduation_resolve_page():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    conn = get_db()
    applications = conn.execute(
        """SELECT ga.*, u.username, 
           (SELECT COUNT(*) FROM grades g 
            JOIN enrollments e ON g.student_id = e.student_id AND g.course_id = e.course_id
            WHERE g.student_id = ga.student_id AND g.letter_grade != 'F') as credits_earned
           FROM graduation_applications ga
           JOIN users u ON ga.student_id = u.id
           WHERE ga.status = 'pending'"""
    ).fetchall()
    conn.close()
    return render_template('semester/graduation.html',
                           applications=applications,
                           role=session['role'],
                           username=session['username'])

@app.route('/graduation/resolve/<int:student_id>', methods=['POST'])
def graduation_resolve_route(student_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    decision = request.form['decision']  # 'approved' or 'rejected'
    conn = get_db()
    application = conn.execute(
        "SELECT * FROM graduation_applications WHERE student_id = ? AND status = 'pending'",
        (student_id,)
    ).fetchone()
    conn.close()
    if application:
        message = resolve_graduation(application['id'], decision == 'approved')
    else:
        message = 'No pending application found for this student'
    return redirect(url_for('graduation_resolve_page'))

#End of Tanzina's code
# ── CLASS DETAIL (instructor) ─────────────────────────────────────────────────

@app.route('/courses/<int:course_id>')
def class_detail(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db()
    course = conn.execute(
        "SELECT * FROM courses WHERE id = ?", (course_id,)
    ).fetchone()
    
    enrolled = conn.execute(
        """SELECT u.id, u.username, g.letter_grade 
           FROM enrollments e
           JOIN users u ON e.student_id = u.id
           LEFT JOIN grades g ON g.student_id = u.id AND g.course_id = ?
           WHERE e.course_id = ? AND e.status = 'enrolled'""",
        (course_id, course_id)
    ).fetchall()
    
    waitlist = conn.execute(
        """SELECT u.id, u.username, w.position
           FROM waitlist w
           JOIN users u ON w.student_id = u.id
           WHERE w.course_id = ?
           ORDER BY w.position""",
        (course_id,)
    ).fetchall()
    
    semester = conn.execute(
        "SELECT * FROM semesters WHERE id = ?", (course['semester_id'],)
    ).fetchone()
    conn.close()
    
    return render_template('courses/class_detail.html',
                           course=course,
                           enrolled=enrolled,
                           waitlist=waitlist,
                           semester=semester,
                           role=session['role'],
                           username=session['username'])


@app.route('/courses/<int:course_id>/grade', methods=['POST'])
def submit_grade_route(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    student_id = int(request.form['student_id'])
    letter_grade = request.form['letter_grade']
    message = submit_grade(session['user_id'], student_id, course_id, letter_grade)
    return redirect(url_for('class_detail', course_id=course_id))


@app.route('/courses/<int:course_id>/admit', methods=['POST'])
def admit_waitlist_route(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    student_id = int(request.form['student_id'])
    message = admit_from_waitlist(course_id, student_id, session['user_id'])
    return redirect(url_for('class_detail', course_id=course_id))
@app.route('/courses/<int:course_id>/reject', methods=['POST'])
def reject_waitlist_route(course_id):
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    student_id = int(request.form['student_id'])
    conn = get_db()
    # Remove from waitlist
    conn.execute(
        "UPDATE waitlist SET status = 'denied' WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    )
    # Issue notification via warning
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.execute(
        "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
        (student_id, f'Your waitlist request for {course["course_name"]} was rejected by the instructor')
    )
    conn.commit()
    conn.close()
    return redirect(url_for('class_detail', course_id=course_id))


# ── REVIEWS ───────────────────────────────────────────────────────────────────

@app.route('/reviews/<int:course_id>')
def view_reviews(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    reviews = get_course_reviews(course_id, session['role'])
    return render_template('conduct/reviews.html',
                           reviews=reviews,
                           course_id=course_id,
                           role=session['role'])

@app.route('/reviews/submit/<int:course_id>', methods=['POST'])
def submit_review_route(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    star_rating = int(request.form['star_rating'])
    review_text = request.form['review_text']
    message = submit_review(session['user_id'], course_id, star_rating, review_text)
    reviews = get_course_reviews(course_id, session['role'])
    return render_template('conduct/reviews.html',
                           reviews=reviews,
                           course_id=course_id,
                           role=session['role'],
                           message=message)


# ── WARNINGS ──────────────────────────────────────────────────────────────────

@app.route('/warnings')
def view_warnings():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    warnings = get_user_warnings(session['user_id'])
    count    = get_warning_count(session['user_id'])
    return render_template('conduct/warnings.html',
                           warnings=warnings,
                           count=count,
                           username=session['username'])


# ── COMPLAINTS ────────────────────────────────────────────────────────────────

@app.route('/complaints')
def view_complaints():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    if session['role'] == 'registrar':
        complaints = get_pending_complaints()
        return render_template('conduct/complaints.html',
                               complaints=complaints,
                               role='registrar')
    return render_template('conduct/complaints.html',
                           complaints=[],
                           role=session['role'])

@app.route('/complaints/file', methods=['POST'])
def file_complaint_route():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    filed_against = int(request.form['filed_against'])
    description   = request.form['description']
    message = file_complaint(session['user_id'], filed_against, description)
    return render_template('conduct/complaints.html',
                           complaints=[],
                           role=session['role'],
                           message=message)

@app.route('/complaints/resolve/<int:complaint_id>', methods=['POST'])
def resolve_complaint_route(complaint_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    warn_user_id    = int(request.form['warn_user_id'])
    resolution_text = request.form['resolution_text']
    message = resolve_complaint(complaint_id, warn_user_id, resolution_text)
    complaints = get_pending_complaints()
    return render_template('conduct/complaints.html',
                           complaints=complaints,
                           role='registrar',
                           message=message)


# ── TABOO WORDS (registrar only) ──────────────────────────────────────────────

@app.route('/taboo')
def manage_taboo():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    words = get_taboo_words()
    return render_template('conduct/taboo.html', words=words)

@app.route('/taboo/add', methods=['POST'])
def add_taboo():
    if session['role'] != 'registrar':
        return redirect(url_for('home'))
    word = request.form['word']
    add_taboo_word(word)
    return redirect(url_for('manage_taboo'))

@app.route('/taboo/remove/<word>')
def remove_taboo(word):
    if session['role'] != 'registrar':
        return redirect(url_for('home'))
    remove_taboo_word(word)
    return redirect(url_for('manage_taboo'))


# ── RUN THE APP ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
