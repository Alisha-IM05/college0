"""
modules/frontend.py

Frontend helper utilities for College0.
Import and use in app.py routes, or call from Jinja2 via template globals.
"""

from flask import session


# ── GRADE HELPERS ─────────────────────────────────────────────────────────────

GRADE_POINTS = {
    'A+': 4.0, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D+': 1.3, 'D': 1.0,
    'F':  0.0,
}

def grade_badge_class(letter_grade):
    """Return a CSS badge class for a letter grade."""
    if not letter_grade:
        return 'gray'
    if letter_grade in ('A+', 'A', 'A-'):
        return 'green'
    if letter_grade in ('B+', 'B', 'B-'):
        return 'blue'
    if letter_grade in ('C+', 'C', 'C-'):
        return 'yellow'
    return 'red'


def grade_points(letter_grade):
    """Return GPA points for a letter grade string."""
    return GRADE_POINTS.get(letter_grade, 0.0)


def format_gpa(value):
    """Format a GPA float to 2 decimal places, or return '—' if None."""
    if value is None:
        return '—'
    return f'{float(value):.2f}'


# ── PERIOD HELPERS ────────────────────────────────────────────────────────────

PERIOD_ORDER = ['setup', 'registration', 'special_registration', 'running', 'grading']

PERIOD_LABELS = {
    'setup':                'Setup',
    'registration':         'Registration',
    'special_registration': 'Special Reg.',
    'running':              'Running',
    'grading':              'Grading',
}

PERIOD_DESCRIPTIONS = {
    'setup':                'Create and configure courses for the upcoming semester.',
    'registration':         'Students can register for and drop courses.',
    'special_registration': 'Only students with special access can still register.',
    'running':              'Semester is in progress. Instructors manage waitlists.',
    'grading':              'Instructors submit final grades. Students may apply for graduation.',
}

def period_label(period):
    """Human-readable label for a semester period slug."""
    return PERIOD_LABELS.get(period, period.replace('_', ' ').title())


def period_description(period):
    """One-line description of what happens in a given period."""
    return PERIOD_DESCRIPTIONS.get(period, '')


def period_index(period):
    """Return the 0-based index of a period in the pipeline."""
    try:
        return PERIOD_ORDER.index(period)
    except ValueError:
        return -1


def period_progress(current_period):
    """
    Return a list of dicts for rendering a progress bar/step list.
    Each dict: { slug, label, status }  where status is 'past', 'active', or 'upcoming'.
    """
    current_idx = period_index(current_period)
    steps = []
    for i, slug in enumerate(PERIOD_ORDER):
        if i < current_idx:
            status = 'past'
        elif i == current_idx:
            status = 'active'
        else:
            status = 'upcoming'
        steps.append({'slug': slug, 'label': PERIOD_LABELS[slug], 'status': status})
    return steps


# ── STATUS HELPERS ────────────────────────────────────────────────────────────

def student_status_class(student_data):
    """Return a CSS class for the student standing banner."""
    if not student_data:
        return 'status-good'
    status = student_data.get('status', '')
    if status == 'terminated':
        return 'status-terminated'
    if status == 'probation':
        return 'status-probation'
    honor = student_data.get('honor_roll', 0)
    sem_gpa = student_data.get('semester_gpa') or 0
    cum_gpa = student_data.get('cumulative_gpa') or 0
    if honor and (sem_gpa > 3.75 or cum_gpa > 3.5):
        return 'status-honor'
    return 'status-good'


def student_status_message(student_data):
    """Return a short status message for the student standing banner."""
    if not student_data:
        return '✅ Good Standing'
    status = student_data.get('status', '')
    if status == 'terminated':
        return '❌ Enrollment terminated due to academic performance. Contact the registrar.'
    if status == 'probation':
        return '⚠️ Academic Probation — GPA must improve above 2.25.'
    honor = student_data.get('honor_roll', 0)
    sem_gpa = student_data.get('semester_gpa') or 0
    cum_gpa = student_data.get('cumulative_gpa') or 0
    if honor and (sem_gpa > 3.75 or cum_gpa > 3.5):
        return '🏆 Honor Roll — Outstanding academic achievement!'
    return '✅ Good Standing'


# ── SEAT AVAILABILITY ─────────────────────────────────────────────────────────

def seats_remaining(course):
    """Return number of open seats in a course dict/row."""
    capacity = course.get('capacity') or 0
    enrolled = course.get('enrolled_count') or 0
    return max(0, capacity - enrolled)


def seats_badge_class(course):
    """CSS badge class based on seat availability."""
    remaining = seats_remaining(course)
    if remaining == 0:
        return 'red'
    if remaining <= 3:
        return 'yellow'
    return 'green'


# ── FLASK INTEGRATION ─────────────────────────────────────────────────────────

def register_template_helpers(app):
    """
    Call this once in app.py after creating the Flask app to make all
    helper functions available inside every Jinja2 template.

    Usage in app.py:
        from modules.frontend import register_template_helpers
        register_template_helpers(app)

    Usage in templates:
        {{ format_gpa(student_data.semester_gpa) }}
        {{ grade_badge_class(g.letter_grade) }}
        {% for step in period_progress(semester.current_period) %}
    """
    helpers = {
        'grade_badge_class':    grade_badge_class,
        'grade_points':         grade_points,
        'format_gpa':           format_gpa,
        'period_label':         period_label,
        'period_description':   period_description,
        'period_progress':      period_progress,
        'student_status_class': student_status_class,
        'student_status_message': student_status_message,
        'seats_remaining':      seats_remaining,
        'seats_badge_class':    seats_badge_class,
    }
    app.jinja_env.globals.update(helpers)