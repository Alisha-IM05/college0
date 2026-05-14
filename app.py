import json
import os

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from jinja2 import ChoiceLoader, FileSystemLoader

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database.db import init_db, get_db

from modules.conduct import (
    submit_review, get_course_reviews, get_course_average_rating,
    file_student_complaint, file_instructor_complaint,
    get_pending_complaints, resolve_student_complaint, resolve_instructor_complaint,
    get_taboo_words, add_taboo_word, remove_taboo_word,
    get_user_warnings, get_warning_count, issue_warning,
    seed_conduct_data, mark_fine_paid, dismiss_complaint,
    get_suspension_info, submit_fine_payment, approve_fine_payment
)
from modules.semester import (
    advance_period, create_course, register_student,
    admit_from_waitlist, enforce_minimums, submit_grade,
    apply_for_graduation, resolve_graduation,
    get_current_semester, get_current_period, 
    use_honor_roll_to_remove_warning, submit_gpa_justification, 
    resolve_gpa_flag, get_active_semester
)

from modules.auth import (
    submit_application, get_applications_for_clerk_user,
    list_pending_applications, list_all_applications,
    approve_application, reject_application,
    change_password,
    suspend_user, terminate_user, reactivate_user, list_manageable_users,
    require_role, verify_clerk_session, establish_clerk_session,
)


app = Flask(__name__)
app.jinja_loader = ChoiceLoader([
    FileSystemLoader('templates'),
])

app.secret_key = 'college0secretkey'


@app.context_processor
def inject_clerk_config():
    """Make the Clerk publishable key available to every template so the
    visitor-facing pages can boot Clerk JS without a backend round-trip."""
    return {
        "CLERK_PUBLISHABLE_KEY": os.environ.get("CLERK_PUBLISHABLE_KEY", ""),
    }


# ── React shell helper ───────────────────────────────────────────────────────
# Auth-related pages are now rendered via a single Jinja shell (_shell.html)
# that mounts a Vite-built React bundle from static/dist/. Each route passes a
# `page` discriminator + arbitrary JSON-serialisable data the React component
# reads from the inline <script id="__data"> tag. Teammates' pages still use
# their existing Jinja templates unchanged.

_PAGE_TITLES = {
    'login': 'College0 — Login',
    'apply': 'College0 — Apply',
    'apply_status': 'College0 — Application Status',
    'change_password': 'College0 — Change Password',
    'dashboard': 'College0 — Dashboard',
    'registrar_applications': 'College0 — Applications',
    'registrar_users': 'College0 — Users',
    'register':          'College0 — Course Registration',
    'instructor_courses':'College0 — My Courses',
    'class_detail':      'College0 — Class Detail',
    'create':            'College0 — Create Course',
    'manage':            'College0 — Semester Management',
    'graduation':        'College0 — Graduation Applications',
    'reviews':           'College0 — Course Reviews',
    'warnings':          'College0 — My Warnings',
    'complaints':        'College0 — Complaints',
    'taboo':             'College0 — Taboo Words',
    'my_reviews':        'College0 — Reviews',
    'home':              'College0 — AI-Enabled College Management',
    'profile':           'College0 — My Profile',
    'suspended':         'College0 — Account Suspended',
}


def _json_default(obj):
    """sqlite3.Row -> dict; datetime -> isoformat; everything else -> str."""
    try:
        return dict(obj)
    except (TypeError, ValueError):
        pass
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


def render_react(page, **data):
    data.setdefault('clerk_publishable_key', os.environ.get('CLERK_PUBLISHABLE_KEY', ''))
    return render_template(
        '_shell.html',
        page=page,
        page_title=_PAGE_TITLES.get(page, 'College0'),
        data_json=json.dumps(data, default=_json_default),
    )


def wants_json():
    """True when the request was made via the React fetch helper (so we
    should respond with a JSON envelope) rather than a full page load."""
    if request.headers.get('X-Requested-With') == 'fetch':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept and 'text/html' not in accept


def _rows_to_dicts(rows):
    return [dict(r) for r in rows] if rows else []


# Routes that a user with must_change_password=1 is still allowed to hit.
_ALLOWED_DURING_PW_CHANGE = {
    'change_password_page', 'change_password_submit',
    'logout', 'static', 'apply_status', 'apply_page', 'apply_submit',
    'suspension_page', 'suspension_pay',
}


@app.before_request
def enforce_password_change():
    """UC-11: once a user is logged in with a temporary password, every
    request must redirect to /change-password until they pick a new one.
    Also redirects suspended users to /suspension for all routes except
    the suspension page itself, logout, and static assets."""
    if 'user_id' not in session:
        return None

    # Routes suspended users are allowed to visit
    _SUSPENSION_ALLOWED = {'suspension_page', 'suspension_pay', 'logout', 'static'}
    if request.endpoint in _SUSPENSION_ALLOWED:
        return None

    conn = get_db()
    row = conn.execute(
        "SELECT must_change_password, status, role FROM users WHERE id = ?",
        (session['user_id'],),
    ).fetchone()
    conn.close()

    if row is None:
        session.clear()
        return redirect(url_for('home'))

    # Always sync role from DB — this ensures reactivation by registrar
    # is reflected in the session on the very next request, without requiring re-login.
    session['role'] = row['role']

    # Redirect suspended users to the suspension page
    if row['status'] == 'suspended' or row['role'] == 'suspended':
        session['role'] = 'suspended'   # keep session in sync
        if request.endpoint not in _ALLOWED_DURING_PW_CHANGE:
            return redirect(url_for('suspension_page'))
        return None

    if request.endpoint in _ALLOWED_DURING_PW_CHANGE:
        return None

    if row['status'] != 'active':
        session.clear()
        return redirect(url_for('home'))

    if row['must_change_password']:
        session['must_change_password'] = True
        return redirect(url_for('change_password_page'))

    return None


# ── SUSPENSION ROUTES ────────────────────────────────────────────────────────

@app.route('/suspension')
def suspension_page():
    """Dedicated page for suspended users — shows fine, warnings, pay button."""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    info = get_suspension_info(session['user_id'])
    return render_react('suspended',
                        username=session.get('username', ''),
                        role='suspended',
                        warning_count=info['warning_count'],
                        warnings=info['warnings'],
                        fine=info['fine'])


@app.route('/suspension/pay', methods=['POST'])
def suspension_pay():
    """User submits fine payment — marks fine as paid, awaits registrar approval."""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    ok, message = submit_fine_payment(session['user_id'])
    if wants_json():
        return jsonify({'ok': ok, 'message': message})
    return redirect(url_for('suspension_page'))



# initialize the database when the app starts
with app.app_context():
    init_db()


# ── TEMPORARY LOGIN (until Zhuolin builds real auth) ─────────────────────────

def create_test_users():
    conn = get_db()
    test_users = [
        ('registrar1', 'registrar1@college0.com', 'password123', 'registrar'),
        ('instructor1', 'instructor1@college0.com', 'password123', 'instructor'),
        ('zhuolin', 'zhoulinl@college0.com', '12345', 'student'),
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
    conn = get_db()
    semester = get_active_semester()
    stats = {
        'student_count': conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'instructor_count': conn.execute("SELECT COUNT(*) FROM users WHERE role='instructor'").fetchone()[0],
        'course_count': conn.execute("SELECT COUNT(*) FROM courses WHERE status='active'").fetchone()[0],
    }
    conn.close()
    return render_react('home',
                        semester=dict(semester) if semester else None,
                        stats=stats)

@app.route('/login', methods=['GET'])
def login_page():
    return render_react('login',
                        clerk_publishable_key=os.environ.get('CLERK_PUBLISHABLE_KEY', ''))

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

    def _login_error(message):
        if wants_json():
            return jsonify({'ok': False, 'error': message}), 200
        return render_react('login', error=message)

    if not user:
        return _login_error("Invalid username or password.")
    if user['status'] == 'terminated':
        return _login_error("Your account has been terminated. Please contact the registrar.")

    session['user_id']  = user['id']
    session['username'] = user['username']
    session['role']     = user['role']

    # Suspended users are allowed to log in — they get redirected to /suspension
    # by the before_request hook, where they can pay their fine.
    if user['status'] == 'suspended':
        if wants_json():
            return jsonify({'ok': True, 'redirect': url_for('suspension_page')})
        return redirect(url_for('suspension_page'))

    if user['must_change_password']:
        session['must_change_password'] = True
        target = url_for('change_password_page')
    else:
        session.pop('must_change_password', None)
        target = url_for('dashboard')

    if wants_json():
        return jsonify({'ok': True, 'redirect': target})
    return redirect(target)

@app.route('/auth/clerk-login', methods=['POST'])
def clerk_login():
    """Bridge a verified Clerk session into the Flask session. The React
    login page calls this after the user signs in with the Clerk <SignIn>
    widget, so the same identity used on /apply can open a normal app
    session. UC-10/UC-11 still apply: if the user row has
    must_change_password=1, we redirect to /change-password just like the
    username/password login does."""
    result = establish_clerk_session(request)
    if not result.get('ok'):
        payload = {'ok': False, 'error': result.get('error', 'Sign-in failed.')}
        if result.get('redirect'):
            payload['redirect'] = result['redirect']
        return jsonify(payload), 200

    user = result['user']
    session['user_id']  = user['id']
    session['username'] = user['username']
    session['role']     = user['role']
    if result['must_change_password']:
        session['must_change_password'] = True
    else:
        session.pop('must_change_password', None)

    return jsonify({'ok': True, 'redirect': result['redirect']})


@app.route('/logout')
def logout():
    """Clear the Flask session and bounce back to /. The `?signed_out=1`
    flag tells the React login page to also sign out of Clerk on arrival —
    otherwise the lingering Clerk JWT would let the page's ClerkBridge
    re-establish the Flask session immediately and the user would land
    right back on /dashboard."""
    session.clear()
    return redirect(url_for('home') + '?signed_out=1')


# ── APPLICATIONS (UC-07 / UC-08 / UC-11) ─────────────────────────────────────
# Visitors authenticate with Clerk (JS) to submit an application and check
# its status. The Clerk session is verified server-side via verify_clerk_session.

@app.route('/apply', methods=['GET'])
def apply_page():
    return render_react('apply')


@app.route('/apply', methods=['POST'])
def apply_submit():
    clerk_user_id = verify_clerk_session(request)
    if not clerk_user_id:
        msg = "You must sign in with Clerk before submitting an application."
        if wants_json():
            return jsonify({'ok': False, 'error': msg}), 200
        return render_react('apply', error=msg)

    first_name = request.form.get('first_name', '')
    last_name = request.form.get('last_name', '')
    email = request.form.get('email', '')
    role_applied = request.form.get('role_applied', '')

    ok, message = submit_application(
        first_name, last_name, email, role_applied, clerk_user_id
    )
    if not ok:
        if wants_json():
            return jsonify({'ok': False, 'error': message}), 200
        return render_react('apply', error=message,
                            first_name=first_name, last_name=last_name,
                            email=email, role_applied=role_applied)
    if wants_json():
        return jsonify({'ok': True, 'redirect': url_for('apply_status')})
    return redirect(url_for('apply_status'))


@app.route('/apply/status')
def apply_status():
    clerk_user_id = verify_clerk_session(request)
    applications = _rows_to_dicts(
        get_applications_for_clerk_user(clerk_user_id) if clerk_user_id else []
    )
    return render_react('apply_status',
                        applications=applications,
                        signed_in=bool(clerk_user_id))


@app.route('/apply/status.json')
def apply_status_json():
    """JSON variant used by the React ApplyStatus page when the initial HTML
    response wasn't able to verify the Clerk session server-side (e.g. the
    `__session` cookie wasn't sent on the initial GET)."""
    clerk_user_id = verify_clerk_session(request)
    applications = _rows_to_dicts(
        get_applications_for_clerk_user(clerk_user_id) if clerk_user_id else []
    )
    return jsonify({
        'signed_in': bool(clerk_user_id),
        'applications': applications,
    })


# ── REGISTRAR: REVIEW APPLICATIONS (UC-09 / UC-10) ───────────────────────────

def _applications_payload(issued=None):
    pending = _rows_to_dicts(list_pending_applications())
    reviewed = [dict(a) for a in list_all_applications() if a['status'] != 'pending']
    return {
        'pending': pending,
        'reviewed': reviewed,
        'issued': issued,
    }


@app.route('/registrar/applications')
@require_role('registrar')
def registrar_applications():
    issued = session.pop('issued_credentials', None)
    return render_react('registrar_applications',
                        role=session['role'],
                        username=session['username'],
                        **_applications_payload(issued))


@app.route('/registrar/applications/<int:application_id>/approve', methods=['POST'])
@require_role('registrar')
def registrar_approve_application(application_id):
    result = approve_application(application_id)
    if result.get('ok'):
        issued = {
            'user_id': result['user_id'],
            'username': result['username'],
            'temp_password': result['temp_password'],
            'role': result['role'],
            'email': result['email'],
        }
    else:
        issued = {'error': result.get('message', 'Approval failed.')}

    if wants_json():
        return jsonify({'ok': bool(result.get('ok')),
                        'data': {'issued': issued, **_applications_payload(issued)}})

    session['issued_credentials'] = issued
    return redirect(url_for('registrar_applications'))


@app.route('/registrar/applications/<int:application_id>/reject', methods=['POST'])
@require_role('registrar')
def registrar_reject_application(application_id):
    ok, message = reject_application(application_id)
    issued = ({'error': message} if not ok else {'rejected': True, 'message': message})

    if wants_json():
        return jsonify({'ok': ok,
                        'data': {'issued': issued, **_applications_payload(issued)}})

    session['issued_credentials'] = issued
    return redirect(url_for('registrar_applications'))


# ── REGISTRAR: MANAGE USERS (UC-13) ──────────────────────────────────────────

@app.route('/registrar/users')
@require_role('registrar')
def registrar_users():
    users = _rows_to_dicts(list_manageable_users())
    # Fetch pending fines so registrar can see who has submitted payment
    conn = get_db()
    pending_fines = conn.execute(
        "SELECT user_id FROM fines WHERE paid = 1 AND approved = 0"
    ).fetchall()
    conn.close()
    pending_fine_user_ids = [row['user_id'] for row in pending_fines]
    return render_react('registrar_users',
                        users=users,
                        pending_fine_user_ids=pending_fine_user_ids,
                        message=session.pop('user_action_message', None),
                        role=session['role'],
                        username=session['username'])


@app.route('/registrar/users/<int:user_id>/<action>', methods=['POST'])
@require_role('registrar')
def registrar_user_action(user_id, action):
    if action == 'suspend':
        ok, message = suspend_user(user_id)
    elif action == 'terminate':
        ok, message = terminate_user(user_id)
    elif action == 'reactivate':
        ok, message = reactivate_user(user_id)
    elif action == 'approve_fine':
        ok, message = approve_fine_payment(user_id)
    else:
        ok, message = False, "Unknown action."

    if wants_json():
        return jsonify({
            'ok': ok,
            'message': message,
            'data': {'users': _rows_to_dicts(list_manageable_users())},
        })

    session['user_action_message'] = message
    return redirect(url_for('registrar_users'))


# ── CHANGE PASSWORD (UC-11) ──────────────────────────────────────────────────

@app.route('/change-password', methods=['GET'])
def change_password_page():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_react('change_password',
                        must_change=session.get('must_change_password', False),
                        username=session['username'],
                        role=session.get('role'))


@app.route('/change-password', methods=['POST'])
def change_password_submit():
    if 'user_id' not in session:
        if wants_json():
            return jsonify({'ok': False, 'error': 'Not signed in.'}), 401
        return redirect(url_for('home'))

    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    def _pw_error(message):
        if wants_json():
            return jsonify({'ok': False, 'error': message}), 200
        return render_react('change_password',
                            error=message,
                            must_change=session.get('must_change_password', False),
                            username=session['username'],
                            role=session.get('role'))

    if new_password != confirm:
        return _pw_error("New password and confirmation do not match.")

    ok, message = change_password(session['user_id'], old_password, new_password)
    if not ok:
        return _pw_error(message)

    session.pop('must_change_password', None)
    if wants_json():
        return jsonify({'ok': True, 'redirect': url_for('dashboard')})
    return redirect(url_for('dashboard'))


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    semester = get_active_semester()
    student_data = None
    grades = []
    grad_app = None 
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
        grad_app = conn.execute(
            """SELECT * FROM graduation_applications
            WHERE student_id = ?
            ORDER BY id DESC LIMIT 1""",
            (session['user_id'],)
        ).fetchone()
    conn.close()
    return render_react('dashboard',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        student_data=dict(student_data) if student_data else None,
                        grades=_rows_to_dicts(grades))
    
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    student = None
    if session['role'] == 'student':
        student = conn.execute("SELECT * FROM students WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    
    # show tutorial only once
    show_tutorial = session.get('role') == 'student' and not session.get('tutorial_done')
    if show_tutorial:
        session['tutorial_done'] = True
    
    return render_react('profile',
                        username=session['username'],
                        role=session['role'],
                        user=dict(user) if user else None,
                        student=dict(student) if student else None,
                        show_tutorial=show_tutorial)
    
    
#start of Tanzina's code
# ── COURSES / REGISTRATION ────────────────────────────────────────────────────

@app.route('/courses/register')
def course_registration():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    semester = get_active_semester()
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
       WHERE c.status = 'active' AND c.semester_id = ?
       AND c.id NOT IN (
           SELECT course_id FROM enrollments
           WHERE student_id = ? AND status = 'cancelled'
       )""",
    (semester['id'], session['user_id'])
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
        AND c.semester_id = ?
        ORDER BY w.course_id""",
        (session['user_id'], semester['id'])
    ).fetchall()
    conn.close()
    return render_react('register',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        courses=_rows_to_dicts(courses),
                        enrolled=_rows_to_dicts(enrolled),
                        cancelled_courses=_rows_to_dicts(cancelled_courses),
                        waitlisted=_rows_to_dicts(waitlisted),
                        special_registration=bool(special_registration))
    
@app.route('/instructor/courses')
def instructor_courses():
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    conn = get_db()
    semester = get_active_semester()
    courses = conn.execute(
        """SELECT c.*, s.name as semester_name, s.current_period,
           (SELECT COUNT(*) FROM waitlist w WHERE w.course_id = c.id) as waitlist_count,
           (SELECT COUNT(*) FROM grades g WHERE g.course_id = c.id) as graded_count
           FROM courses c JOIN semesters s ON c.semester_id = s.id
           WHERE c.instructor_id = ? AND c.semester_id = ?
           ORDER BY c.status ASC, c.course_name ASC""",
        (session['user_id'], semester['id'])
    ).fetchall()
    conn.close()
    return render_react('instructor_courses',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        courses=_rows_to_dicts(courses))

@app.route('/courses/register/<int:course_id>', methods=['POST'])
def register_for_course(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    message = register_student(session['user_id'], course_id)
    conn = get_db()
    semester = get_active_semester()
    special_registration = False
    if session['role'] == 'student':
        sr = conn.execute("SELECT special_registration FROM students WHERE id = ?", (session['user_id'],)).fetchone()
        special_registration = sr and sr['special_registration'] == 1
    courses = conn.execute(
        """SELECT c.*, u.username as instructor_name,
           c.time_slot || ' ' || c.start_time || '-' || c.end_time as display_slot
           FROM courses c LEFT JOIN users u ON c.instructor_id = u.id
           WHERE c.status = 'active' AND c.semester_id = ?""", (semester['id'],)
    ).fetchall()
    enrolled = conn.execute(
        """SELECT c.*, u.username as instructor_name FROM enrollments e
           JOIN courses c ON e.course_id = c.id LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'enrolled' AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    cancelled_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name FROM enrollments e
           JOIN courses c ON e.course_id = c.id LEFT JOIN users u ON c.instructor_id = u.id
           WHERE e.student_id = ? AND e.status = 'cancelled' AND c.semester_id = ?""",
        (session['user_id'], semester['id'])
    ).fetchall()
    waitlisted = conn.execute(
        """SELECT w.*, c.course_name, c.time_slot FROM waitlist w
           JOIN courses c ON w.course_id = c.id
           WHERE w.student_id = ? ORDER BY w.course_id""", (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_react('register',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        courses=_rows_to_dicts(courses),
                        enrolled=_rows_to_dicts(enrolled),
                        cancelled_courses=_rows_to_dicts(cancelled_courses),
                        waitlisted=_rows_to_dicts(waitlisted),
                        special_registration=bool(special_registration),
                        message=message)

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
    semester = get_active_semester()
    conn.close()
    print(f"DEBUG semester_management: id={semester['id']} name={semester['name']}")  # ADD THIS
    return render_react('manage',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None)

@app.route('/semester/advance', methods=['POST'])
def advance_semester():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    semester_id = int(request.form['semester_id'])
    message = advance_period(semester_id)
    if message == 'special_registration':
        summary = enforce_minimums(semester_id)
        message = summary
    conn = get_db()
    # Auto-reject all waitlist entries when semester moves to running
    semester_check = get_active_semester()
    if semester_check and semester_check['current_period'] == 'running':
        conn.execute("DELETE FROM waitlist WHERE course_id IN (SELECT id FROM courses WHERE semester_id = ?)", (semester_id,))
        conn.commit()
    semester = get_active_semester()
    special_reg_students = _rows_to_dicts(conn.execute(
        """SELECT u.username FROM users u JOIN students s ON s.id = u.id
           WHERE s.special_registration = 1"""
    ).fetchall())
    conn.close()
    return render_react('manage',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        message=message,
                        special_reg_students=special_reg_students)

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
        # Try to go back to previous semester's grading period
        prev_semester = conn.execute(
            "SELECT * FROM semesters WHERE id < ? ORDER BY id DESC LIMIT 1",
            (semester_id,)
        ).fetchone()
        if prev_semester:
            conn.execute(
                "UPDATE semesters SET current_period = 'grading' WHERE id = ?",
                (prev_semester['id'],)
            )
            conn.commit()
            message = f'Moved back to {prev_semester["name"]} grading period'
        else:
            message = 'Already at the first period'
    else:
        current_index = PERIOD_ORDER.index(current)
        prev_period = PERIOD_ORDER[current_index - 1]
        conn.execute(
            "UPDATE semesters SET current_period = ? WHERE id = ?",
            (prev_period, semester_id)
        )
        conn.commit()
        message = f'Moved back to {prev_period}'
    
    semester = get_active_semester()
    conn.close()
    return render_react('manage',
                        username=session['username'],
                        role=session['role'],
                        semester=dict(semester) if semester else None,
                        message=message)

# ── CREATE COURSE (registrar) ─────────────────────────────────────────────────

@app.route('/courses/create')
def create_course_page():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    conn = get_db()
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor' AND status = 'active'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = get_active_semester()
    current_courses = conn.execute(
        """SELECT c.*, u.username as instructor_name
           FROM courses c JOIN users u ON c.instructor_id = u.id
           WHERE c.semester_id = ?""",
        (current_semester['id'],)
    ).fetchall()
    conn.close()
    return render_react('create',
                        username=session['username'],
                        role=session['role'],
                        instructors=_rows_to_dicts(instructors),
                        semesters=_rows_to_dicts(semesters),
                        semester=dict(current_semester) if current_semester else None,
                        current_courses=_rows_to_dicts(current_courses))

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
    day_labels = {'1': 'Mon/Wed', '3': 'Tue/Thu', '4': 'Wed/Fri', '5': 'Fri'}
    day_label = day_labels.get(request.form['day_of_week'], 'Mon/Wed')
    time_slot = f"{day_label} {start_time}-{end_time}"
    message = create_course(semester_id, name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity)
    conn = get_db()
    instructors = conn.execute("SELECT id, username FROM users WHERE role = 'instructor' AND status = 'active'").fetchall()
    semesters = conn.execute("SELECT * FROM semesters").fetchall()
    current_semester = get_active_semester()
    current_courses = conn.execute(
        "SELECT c.*, u.username as instructor_name FROM courses c JOIN users u ON c.instructor_id = u.id WHERE c.semester_id = ?",
        (current_semester['id'],)
    ).fetchall()
    conn.close()
    return render_react('create',
                        username=session['username'],
                        role=session['role'],
                        instructors=_rows_to_dicts(instructors),
                        semesters=_rows_to_dicts(semesters),
                        semester=dict(current_semester) if current_semester else None,
                        current_courses=_rows_to_dicts(current_courses),
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
    return render_react('graduation',
                        username=session['username'],
                        role=session['role'],
                        applications=_rows_to_dicts(applications))

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


# ── CLASS DETAIL (instructor) ─────────────────────────────────────────────────

@app.route('/courses/<int:course_id>')
def class_detail(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    course = conn.execute(
        "SELECT * FROM courses WHERE id = ?", (course_id,)
    ).fetchone()

    if course is None:
        conn.close()
        return "Course not found", 404
    if session['role'] == 'instructor' and course['instructor_id'] != session['user_id']:
        conn.close()
        return "Access denied — this course is not assigned to you", 403
    
    enrolled = conn.execute(
        """SELECT u.id, u.username, g.letter_grade 
           FROM enrollments e JOIN users u ON e.student_id = u.id
           LEFT JOIN grades g ON g.student_id = u.id AND g.course_id = ?
           WHERE e.course_id = ? AND e.status = 'enrolled'""",
        (course_id, course_id)
    ).fetchall()
    waitlist = conn.execute(
        """SELECT u.id, u.username, w.position
           FROM waitlist w JOIN users u ON w.student_id = u.id
           WHERE w.course_id = ? ORDER BY w.position""",
        (course_id,)
    ).fetchall()
    semester = conn.execute(
        "SELECT * FROM semesters WHERE id = ?", (course['semester_id'],)
    ).fetchone()
    conn.close()
    return render_react('class_detail',
                        username=session['username'],
                        role=session['role'],
                        course=dict(course) if course else None,
                        enrolled=_rows_to_dicts(enrolled),
                        waitlist=_rows_to_dicts(waitlist),
                        semester=dict(semester) if semester else None)


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

@app.route('/warnings/remove/<int:warning_id>', methods=['POST'])
def remove_warning_with_honor_roll(warning_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('home'))
    from modules.semester import use_honor_roll_to_remove_warning
    message = use_honor_roll_to_remove_warning(session['user_id'], warning_id)
    return redirect(url_for('view_warnings'))

## ── FLAGGED GPAS ─────────────────────────────────────────────────

@app.route('/flagged-gpas')
def flagged_gpas_page():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    if session['role'] == 'registrar':
        flags = conn.execute(
            """SELECT f.*, c.course_name, u.username as instructor_name
               FROM flagged_course_gpas f
               JOIN courses c ON f.course_id = c.id
               JOIN users u ON f.instructor_id = u.id
               WHERE f.status IN ('pending', 'justified')
               ORDER BY f.flagged_at DESC"""
        ).fetchall()
    elif session['role'] == 'instructor':
        flags = conn.execute(
            """SELECT f.*, c.course_name
               FROM flagged_course_gpas f
               JOIN courses c ON f.course_id = c.id
               WHERE f.instructor_id = ? AND f.status = 'pending'
               ORDER BY f.flagged_at DESC""",
            (session['user_id'],)
        ).fetchall()
    else:
        conn.close()
        return redirect(url_for('home'))
    conn.close()
    return render_template('semester/flagged_gpas.html',
                           flags=flags,
                           role=session['role'],
                           username=session['username'])


@app.route('/flagged-gpas/justify/<int:flag_id>', methods=['POST'])
def justify_gpa_flag(flag_id):
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    from modules.semester import submit_gpa_justification
    justification = request.form.get('justification', '')
    submit_gpa_justification(session['user_id'], flag_id, justification)
    return redirect(url_for('flagged_gpas_page'))


@app.route('/flagged-gpas/resolve/<int:flag_id>', methods=['POST'])
def resolve_gpa_flag_route(flag_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    from modules.semester import resolve_gpa_flag
    decision = request.form.get('decision')
    resolve_gpa_flag(session['user_id'], flag_id, decision)
    return redirect(url_for('flagged_gpas_page'))




#End of Tanzina's code

# ── REVIEWS ───────────────────────────────────────────────────────────────────
@app.route('/reviews')
def my_reviews_page():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    if session['role'] == 'student':
        courses = conn.execute(
            """SELECT DISTINCT c.id, c.course_name, c.time_slot,
                      e.grade, e.status as enrollment_status,
                      s.name as semester_name,
                      r.id as review_id
               FROM enrollments e
               JOIN courses c ON e.course_id = c.id
               JOIN semesters s ON c.semester_id = s.id
               LEFT JOIN reviews r ON r.course_id = c.id AND r.student_id = e.student_id
               WHERE e.student_id = ?
               ORDER BY e.enrolled_at DESC""",
            (session['user_id'],)
        ).fetchall()
        conn.close()
        return render_react('my_reviews',
                            username=session['username'],
                            role=session['role'],
                            courses=_rows_to_dicts(courses))
    else:
        # Registrar sees ALL reviews including hidden (is_visible=0) for moderation
        if session['role'] == 'registrar':
            courses = conn.execute(
                """SELECT c.id, c.course_name, c.time_slot,
                          s.name as semester_name,
                          AVG(CASE WHEN r.is_visible=1 THEN r.star_rating END) as avg_rating,
                          COUNT(r.id) as review_count,
                          SUM(CASE WHEN r.is_visible=0 THEN 1 ELSE 0 END) as hidden_count
                   FROM courses c
                   JOIN semesters s ON c.semester_id = s.id
                   LEFT JOIN reviews r ON r.course_id = c.id
                   GROUP BY c.id
                   ORDER BY s.id DESC, c.course_name"""
            ).fetchall()
        else:
            courses = conn.execute(
                """SELECT c.id, c.course_name, c.time_slot,
                          s.name as semester_name,
                          AVG(r.star_rating) as avg_rating,
                          COUNT(r.id) as review_count
                   FROM courses c
                   JOIN semesters s ON c.semester_id = s.id
                   LEFT JOIN reviews r ON r.course_id = c.id AND r.is_visible = 1
                   GROUP BY c.id
                   ORDER BY s.id DESC, c.course_name"""
            ).fetchall()
        conn.close()
        return render_react('my_reviews',
                            username=session['username'],
                            role=session['role'],
                            courses=_rows_to_dicts(courses))

@app.route('/reviews/<int:course_id>')
def view_reviews(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
 
    # Check if this student was ever enrolled (for showing/hiding the form)
    was_enrolled = None
    already_reviewed = None
    if session['role'] == 'student':
        was_enrolled = conn.execute(
            "SELECT grade FROM enrollments WHERE student_id = ? AND course_id = ? ORDER BY enrolled_at DESC LIMIT 1",
            (session['user_id'], course_id)
        ).fetchone()
        already_reviewed = conn.execute(
            "SELECT id FROM reviews WHERE student_id = ? AND course_id = ?",
            (session['user_id'], course_id)
        ).fetchone()
 
    conn.close()
    reviews = get_course_reviews(course_id, session['role'])
    avg_rating = get_course_average_rating(course_id)
    return render_react('reviews',
                        username=session['username'],
                        role=session['role'],
                        course_id=course_id,
                        course=dict(course) if course else None,
                        reviews=_rows_to_dicts(reviews),
                        avg_rating=avg_rating)


@app.route('/reviews/submit/<int:course_id>', methods=['POST'])
def submit_review_route(course_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    star_rating = int(request.form['star_rating'])
    review_text = request.form.get('review_text', '').strip()
    result = submit_review(session['user_id'], course_id, star_rating, review_text)
    status, message = result.split(':', 1)
    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    reviews = get_course_reviews(course_id, session['role'])
    avg_rating = get_course_average_rating(course_id)
    return render_react('reviews',
                        username=session['username'],
                        role=session['role'],
                        course_id=course_id,
                        course=dict(course) if course else None,
                        reviews=_rows_to_dicts(reviews),
                        avg_rating=avg_rating,
                        message=message,
                        message_type=status)


# ── WARNINGS ──────────────────────────────────────────────────────────────────

@app.route('/warnings')
def view_warnings():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    warnings = get_user_warnings(session['user_id'])
    count = get_warning_count(session['user_id'])
    return render_react('warnings',
                        username=session['username'],
                        role=session['role'],
                        warnings=_rows_to_dicts(warnings),
                        count=count)


# ── COMPLAINTS ────────────────────────────────────────────────────────────────

@app.route('/complaints')
def view_complaints():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = get_db()
    all_users = conn.execute(
        "SELECT id, username, role FROM users WHERE role IN ('student', 'instructor') ORDER BY username"
    ).fetchall()
    if session['role'] == 'instructor':
        my_students = conn.execute(
            """SELECT DISTINCT u.id, u.username FROM users u
               JOIN enrollments e ON u.id = e.student_id
               JOIN courses c ON e.course_id = c.id
               WHERE c.instructor_id = ? AND e.status = 'enrolled'""",
            (session['user_id'],)
        ).fetchall()
        conn.close()
        return render_react('complaints',
                            username=session['username'],
                            role=session['role'],
                            complaints=[],
                            all_users=_rows_to_dicts(all_users),
                            my_students=_rows_to_dicts(my_students))
    if session['role'] == 'registrar':
        complaints = get_pending_complaints()
        conn.close()
        return render_react('complaints',
                            username=session['username'],
                            role='registrar',
                            complaints=_rows_to_dicts(complaints),
                            all_users=[])
    conn.close()
    return render_react('complaints',
                        username=session['username'],
                        role=session['role'],
                        complaints=[],
                        all_users=_rows_to_dicts(all_users),
                        my_students=[])

@app.route('/complaints/file/student', methods=['POST'])
def file_student_complaint_route():
    if 'user_id' not in session or session['role'] not in ('student', 'instructor'):
        return redirect(url_for('home'))
    filed_against = int(request.form['filed_against'])
    description = request.form.get('description', '').strip()
    result = file_student_complaint(session['user_id'], filed_against, description)
    status, message = result.split(':', 1)
    conn = get_db()
    all_users = conn.execute(
        "SELECT id, username, role FROM users WHERE role IN ('student', 'instructor') ORDER BY username"
    ).fetchall()
    conn.close()
    return render_react('complaints',
                        username=session['username'],
                        role=session['role'],
                        complaints=[],
                        all_users=_rows_to_dicts(all_users),
                        my_students=[],
                        message=message,
                        message_type=status)

@app.route('/complaints/file/instructor', methods=['POST'])
def file_instructor_complaint_route():
    if 'user_id' not in session or session['role'] != 'instructor':
        return redirect(url_for('home'))
    student_id = int(request.form['student_id'])
    description = request.form.get('description', '').strip()
    requested_action = request.form.get('requested_action', '')
    result = file_instructor_complaint(session['user_id'], student_id, description, requested_action)
    status, message = result.split(':', 1)
    conn = get_db()
    my_students = conn.execute(
        """SELECT DISTINCT u.id, u.username FROM users u
           JOIN enrollments e ON u.id = e.student_id
           JOIN courses c ON e.course_id = c.id
           WHERE c.instructor_id = ? AND e.status = 'enrolled'""",
        (session['user_id'],)
    ).fetchall()
    all_users = conn.execute(
        "SELECT id, username, role FROM users WHERE role IN ('student', 'instructor') ORDER BY username"
    ).fetchall()
    conn.close()
    return render_react('complaints',
                        username=session['username'],
                        role=session['role'],
                        complaints=[],
                        all_users=_rows_to_dicts(all_users),
                        my_students=_rows_to_dicts(my_students),
                        message=message,
                        message_type=status)

@app.route('/complaints/resolve/student/<int:complaint_id>', methods=['POST'])
def resolve_student_complaint_route(complaint_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    warn_user_id = int(request.form['warn_user_id'])
    resolution_text = request.form.get('resolution_text', '').strip()
    result = resolve_student_complaint(complaint_id, warn_user_id, resolution_text)
    status, message = result.split(':', 1)
    complaints = get_pending_complaints()
    return render_react('complaints',
                        username=session['username'],
                        role='registrar',
                        complaints=_rows_to_dicts(complaints),
                        all_users=[],
                        message=message,
                        message_type=status)

@app.route('/complaints/resolve/instructor/<int:complaint_id>', methods=['POST'])
def resolve_instructor_complaint_route(complaint_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    decision = request.form.get('decision', '')
    resolution_text = request.form.get('resolution_text', '').strip()
    result = resolve_instructor_complaint(complaint_id, decision, resolution_text)
    status, message = result.split(':', 1)
    complaints = get_pending_complaints()
    return render_react('complaints',
                        username=session['username'],
                        role='registrar',
                        complaints=_rows_to_dicts(complaints),
                        all_users=[],
                        message=message,
                        message_type=status)

#dismiss
@app.route('/complaints/dismiss/<int:complaint_id>', methods=['POST'])
def dismiss_complaint_route(complaint_id):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    result = dismiss_complaint(complaint_id)
    status, message = result.split(':', 1)
    complaints = get_pending_complaints()
    return render_template('conduct/complaints.html',
                           complaints=complaints,
                           role='registrar',
                           username=session['username'],
                           all_users=[],
                           message=message,
                           message_type=status)

# ── TABOO WORDS (registrar only) ──────────────────────────────────────────────

@app.route('/taboo')
def manage_taboo():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    words = get_taboo_words()
    return render_react('taboo',
                        username=session['username'],
                        role=session['role'],
                        words=words)

@app.route('/taboo/add', methods=['POST'])
def add_taboo():
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    word = request.form.get('word', '').strip()
    success = add_taboo_word(word)
    words = get_taboo_words()
    if not word:
        message, message_type = "Word cannot be empty.", "error"
    elif not success:
        message, message_type = f'"{word}" is already in the taboo list.', "warning"
    else:
        message, message_type = f'"{word}" added to taboo list.', "success"
    return render_react('taboo',
                        username=session['username'],
                        role=session['role'],
                        words=words,
                        message=message,
                        message_type=message_type)

@app.route('/taboo/remove/<word>')
def remove_taboo(word):
    if 'user_id' not in session or session['role'] != 'registrar':
        return redirect(url_for('home'))
    remove_taboo_word(word)
    return redirect(url_for('manage_taboo'))

# ── RUN THE APP ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)