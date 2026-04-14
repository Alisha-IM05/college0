from flask import Flask, render_template, request, redirect, url_for, session
from database.db import init_db
from alisha.reviews_warnings import (
    submit_review, get_course_reviews,
    file_complaint, get_pending_complaints, resolve_complaint,
    get_taboo_words, add_taboo_word, remove_taboo_word,
    get_user_warnings, get_warning_count, issue_warning
)

app = Flask(__name__)
app.secret_key = 'college0secretkey'  # needed for sessions (keeping users logged in)

# initialize the database when the app starts
with app.app_context():
    init_db()


# ── TEMPORARY LOGIN (until Member 2 builds real auth) ────────────────────────
# We create fake users here just so we can test our features right now

from database.db import get_connection

def create_test_users():
    """Creates some test users so we can log in and test everything"""
    conn = get_connection()
    test_users = [
        ('registrar1', 'password123', 'registrar'),
        ('instructor1', 'password123', 'instructor'),
        ('student1', 'password123', 'student'),
        ('student2', 'password123', 'student'),
    ]
    for username, password, role in test_users:
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
        except:
            pass  # user already exists, skip
    
    # create a test course
    try:
        conn.execute(
            "INSERT INTO courses (name, instructor_id) VALUES (?, ?)",
            ('Introduction to Computer Science', 2)  # instructor1 teaches this
        )
        # enroll student1 in the course
        conn.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            (3, 1)  # student1 in course 1
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

    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password)
    ).fetchone()
    conn.close()

    if user:
        # save user info in session so we remember who is logged in
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
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
    return render_template('dashboard.html',
                           username=session['username'],
                           role=session['role'])


# ── REVIEWS ───────────────────────────────────────────────────────────────────

@app.route('/reviews/<int:course_id>')
def view_reviews(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    reviews = get_course_reviews(course_id, session['role'])
    return render_template('reviews.html',
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
    return render_template('reviews.html',
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
    count = get_warning_count(session['user_id'])
    return render_template('warnings.html',
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
        return render_template('complaints.html',
                               complaints=complaints,
                               role='registrar')
    return render_template('complaints.html',
                           complaints=[],
                           role=session['role'])

@app.route('/complaints/file', methods=['POST'])
def file_complaint_route():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    filed_against = int(request.form['filed_against'])
    description = request.form['description']
    message = file_complaint(session['user_id'], filed_against, description)
    return render_template('complaints.html',
                           complaints=[],
                           role=session['role'],
                           message=message)

@app.route('/complaints/resolve/<int:complaint_id>', methods=['POST'])
def resolve_complaint_route(complaint_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    warn_user_id = int(request.form['warn_user_id'])
    resolution_text = request.form['resolution_text']
    message = resolve_complaint(complaint_id, warn_user_id, resolution_text)
    complaints = get_pending_complaints()
    return render_template('complaints.html',
                           complaints=complaints,
                           role='registrar',
                           message=message)


# ── TABOO WORDS (registrar only) ──────────────────────────────────────────────

@app.route('/taboo')
def manage_taboo():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    words = get_taboo_words()
    return render_template('taboo.html', words=words)

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
