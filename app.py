from flask import Flask, render_template, request, redirect, url_for, session
from jinja2 import ChoiceLoader, FileSystemLoader

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

# initialize the database when the app starts
with app.app_context():
    init_db()


# ── TEMPORARY LOGIN (until Zhuolin builds real auth) ─────────────────────────

def create_test_users():
    conn = get_db()
    test_users = [
        ('registrar1', 'registrar1@college0.com', 'password123', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password123', 'instructor'),
        ('student1', 'student1@college0.com', 'password123', 'student'),
        ('student2',   'student2@college0.com',   'password123', 'student'),
    ]
    for username, email, password, role in test_users:
        try:
            conn.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                (username, email, password, role)
            )
            if role == 'student':
                user = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                conn.execute(
                    "INSERT OR IGNORE INTO students (id) VALUES (?)", (user['id'],)
                )
        except:
            pass


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
        "SELECT * FROM semesters ORDER BY id ASC LIMIT 1"
    ).fetchone()
    student_data = None
    grades = None
    if session['role'] == 'student':
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
            "SELECT * FROM semesters ORDER BY id ASC LIMIT 1"
            
    ).fetchone()
    courses = conn.execute(
        """SELECT *, time_slot || ' ' || start_time || '-' || end_time as display_slot
           FROM courses WHERE status = 'active' AND semester_id = ?""",
        (semester['id'],)
    ).fetchall()
    enrolled = conn.execute(
        """SELECT c.* FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           WHERE e.student_id = ? AND e.status = 'enrolled'
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
                           role=session['role'],
                           username=session['username'],
                           waitlisted=waitlisted)
@app.route('/instructor/courses')
def instructor_courses():
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    conn = get_db()
    semester = conn.execute(
        "SELECT * FROM semesters ORDER BY id ASC LIMIT 1"
    ).fetchone()
    courses = conn.execute(
        """SELECT c.*, s.name as semester_name, s.current_period
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
        "SELECT * FROM semesters ORDER BY id ASC LIMIT 1"

    ).fetchone()
    courses = conn.execute(
        """SELECT *, time_slot || ' ' || start_time || '-' || end_time as display_slot
           FROM courses WHERE status = 'active' AND semester_id = ?""",
        (semester['id'],)
    ).fetchall()
    enrolled = conn.execute(
        """SELECT c.* FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           WHERE e.student_id = ? AND e.status = 'enrolled'
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
                           role=session['role'],
                           username=session['username'],
                           message=message,
                           waitlisted=waitlisted)

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
    semester = conn.execute("SELECT * FROM semesters ORDER BY id ASC LIMIT 1").fetchone()
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
    semester = conn.execute("SELECT * FROM semesters ORDER BY id ASC LIMIT 1").fetchone()
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
    if current == 'setup':
        message = 'Already at the first period'
    else:
        current_index = ['setup', 'registration', 'running', 'grading'].index(current)
        prev_period = ['setup', 'registration', 'running', 'grading'][current_index - 1]
        conn.execute("UPDATE semesters SET current_period = ? WHERE id = ?", (prev_period, semester_id))
        conn.commit()
        message = f'Moved back to {prev_period}'
    semester = conn.execute("SELECT * FROM semesters ORDER BY id ASC LIMIT 1").fetchone()
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
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = conn.execute(
        """SELECT * FROM semesters 
           ORDER BY CASE current_period 
               WHEN 'setup' THEN 1 
               WHEN 'registration' THEN 2 
               WHEN 'running' THEN 3 
               WHEN 'grading' THEN 4 
           END ASC, id DESC LIMIT 1"""
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
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = conn.execute("SELECT * FROM semesters ORDER BY id DESC LIMIT 1").fetchone()
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
        "DELETE FROM waitlist WHERE student_id = ? AND course_id = ?",
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
