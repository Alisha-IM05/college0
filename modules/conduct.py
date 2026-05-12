import re
from database.db import get_connection


# TABOO WORD FUNCTIONS
def get_taboo_words():
    """Gets the full list of taboo words from the database"""
    conn = get_connection()
    words = conn.execute("SELECT word FROM taboo_words").fetchall()
    conn.close()
    return [row['word'].lower() for row in words]

def add_taboo_word(word):
    """Registrar adds a new taboo word — H-013: block empty submissions"""
    word = word.strip().lower()
    if not word:
        return False  # H-013: prevent empty taboo word
    conn = get_connection()
    try:
        conn.execute("INSERT INTO taboo_words (word) VALUES (?)", (word,))
        conn.commit()
        return True
    except:
        return False  # H-014: handle duplicate without breaking
    finally:
        conn.close()

def remove_taboo_word(word):
    """Registrar removes a taboo word"""
    conn = get_connection()
    conn.execute("DELETE FROM taboo_words WHERE word = ?", (word.lower(),))
    conn.commit()
    conn.close()

def filter_review(text):
    """
    Scans review text for taboo words using whole-word matching (H-017).
    Returns: (filtered_text, taboo_count)
    - filtered_text has bad words replaced with asterisks
    - taboo_count is how many distinct taboo words were found
    """
    taboo_words = get_taboo_words()
    taboo_count = 0
    filtered_text = text

    for word in taboo_words:
        # H-017: whole-word matching — won't flag "badword" inside "notbadwordhere"
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, filtered_text, flags=re.IGNORECASE):
            taboo_count += 1
            replacement = '*' * len(word)
            filtered_text = re.sub(pattern, replacement, filtered_text, flags=re.IGNORECASE)

    return filtered_text, taboo_count


#  REVIEW FUNCTIONS 
def submit_review(student_id, course_id, star_rating, review_text):
    """
    Student submits a review.
    H-002: only enrolled students can review
    H-003: block after grades posted
    H-027: block empty review text
    H-016 to H-022: taboo filtering and warning rules
    """
    # H-027: block empty review text
    if not review_text or not review_text.strip():
        return "error:Review text cannot be empty."

    # H-002: check if student is enrolled in the course
    conn = get_connection()
    enrollment = conn.execute(
        """SELECT * FROM enrollments 
           WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
        (student_id, course_id)
    ).fetchone()
    conn.close()

    if not enrollment:
        return "error:You are not enrolled in this course and cannot review it."

    # H-003: block review after grade has been posted
    if enrollment['grade'] is not None:
        return "error:The review period for this course is closed because grades have been posted."

    # Check if student already submitted a review for this course
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM reviews WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchone()
    conn.close()
    if existing:
        return "error:You have already submitted a review for this course."

    # H-016: scan for taboo words using whole-word matching
    filtered_text, taboo_count = filter_review(review_text)

    # H-021/H-022: apply rules based on taboo word count
    if taboo_count >= 3:
        # H-021: hide review entirely for 3+ taboo words
        # H-022: issue 2 warnings
        issue_warning(student_id, "Review hidden: contained 3 or more taboo words.")
        issue_warning(student_id, "Second warning: review with 3+ taboo words was not published.")
        return "warning:Your review was not posted because it contained too many inappropriate words. You have received 2 warnings."

    elif taboo_count in [1, 2]:
        # H-019: publish filtered review with asterisks
        # H-020: issue 1 warning
        save_review(student_id, course_id, star_rating, review_text, filtered_text, is_visible=1)
        issue_warning(student_id, f"Review contained {taboo_count} taboo word(s). Words replaced with *.")
        update_course_rating(course_id)
        return "warning:Your review was posted but some inappropriate words were replaced with *. You have received 1 warning."

    else:
        # H-018: publish clean review normally
        save_review(student_id, course_id, star_rating, review_text, review_text, is_visible=1)
        update_course_rating(course_id)
        return "success:Your review was posted successfully!"

def save_review(student_id, course_id, star_rating, original_text, filtered_text, is_visible):
    """Saves a review to the database"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO reviews 
        (student_id, course_id, star_rating, review_text, filtered_text, is_visible) 
        VALUES (?, ?, ?, ?, ?, ?)""",
        (student_id, course_id, star_rating, original_text, filtered_text, is_visible)
    )
    conn.commit()
    conn.close()

def get_course_reviews(course_id, viewer_role):
    """
    Gets all visible reviews for a course.
    H-008/H-009: hide reviewer identity from students and instructors
    H-010: show reviewer identity only to registrar
    H-028: non-registrars see filtered_text (asterisks), registrar sees raw review_text
    H-029: registrar sees full moderation info
    """
    conn = get_connection()
    if viewer_role == 'registrar':
        # H-010 + H-029: registrar sees reviewer name and raw text
        reviews = conn.execute(
            """SELECT r.id, r.course_id, r.star_rating, r.review_text, r.filtered_text,
                      r.is_visible, r.created_at, u.username as reviewer_name
               FROM reviews r
               JOIN users u ON r.student_id = u.id
               WHERE r.course_id = ?
               ORDER BY r.created_at DESC""",
            (course_id,)
        ).fetchall()
    else:
        # H-008/H-009/H-028: anonymous, show filtered_text only for visible reviews
        reviews = conn.execute(
            """SELECT id, course_id, star_rating, filtered_text as review_text, created_at
               FROM reviews
               WHERE course_id = ? AND is_visible = 1
               ORDER BY created_at DESC""",
            (course_id,)
        ).fetchall()
    conn.close()
    return reviews

def get_course_average_rating(course_id):
    """Returns the average star rating for a course from visible reviews"""
    conn = get_connection()
    result = conn.execute(
        "SELECT AVG(star_rating) as avg_rating FROM reviews WHERE course_id = ? AND is_visible = 1",
        (course_id,)
    ).fetchone()
    conn.close()
    if result and result['avg_rating'] is not None:
        return round(result['avg_rating'], 2)
    return None

def update_course_rating(course_id):
    """
    H-025: recalculates average rating after each visible review.
    H-024: warns instructor if average drops below 2.0.
    """
    avg = get_course_average_rating(course_id)
    if avg is not None and avg < 2.0:
        conn = get_connection()
        course = conn.execute(
            "SELECT instructor_id FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        conn.close()
        if course and course['instructor_id']:
            issue_warning(
                course['instructor_id'],
                f"Course average rating dropped below 2.0 (current average: {avg:.2f})"
            )


#  WARNING FUNCTIONS

def issue_warning(user_id, reason):
    """
    J-021: centralized warning helper used by all modules.
    J-022: counts warnings by user.
    J-024: suspends student after 3 warnings.
    J-029: suspends instructor after 3 warnings.
    H-023: checks warning threshold after each warning insertion.
    """
    conn = get_connection()

    # save the warning
    conn.execute(
        "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
        (user_id, reason)
    )
    conn.commit()

    # H-023 / J-022: count total warnings for this user
    count = conn.execute(
        "SELECT COUNT(*) as total FROM warnings WHERE user_id = ?",
        (user_id,)
    ).fetchone()['total']

    # get the user's role
    user = conn.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    # J-024 / J-029: suspend at 3 warnings
    if count >= 3 and user and user['role'] in ('student', 'instructor'):
        suspend_user(user_id, "3 warnings accumulated — suspended for 1 semester")

def get_user_warnings(user_id):
    """J-023: gets all warnings for a specific user"""
    conn = get_connection()
    warnings = conn.execute(
        "SELECT * FROM warnings WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return warnings

def get_warning_count(user_id):
    """Returns the total number of warnings a user has"""
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) as total FROM warnings WHERE user_id = ?",
        (user_id,)
    ).fetchone()['total']
    conn.close()
    return count

def suspend_user(user_id, reason):
    """
    J-025: suspends user and records suspension.
    J-027: records fine owed by suspended student.
    """
    conn = get_connection()

    # get role before suspending
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()

    conn.execute(
        "UPDATE users SET role = 'suspended', status = 'suspended' WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    print(f"User {user_id} suspended. Reason: {reason}")


#  COMPLAINT FUNCTIONS
def file_student_complaint(filed_by, filed_against_id, description):
    """
    J-001: student files a complaint against a student or instructor.
    J-002: validate target exists.
    J-003: block self-complaints.
    J-004: require non-empty description.
    J-005: store as pending with timestamp.
    """
    # J-004: require description
    if not description or not description.strip():
        return "error:Complaint description cannot be empty."

    # J-003: block self-complaints
    if filed_by == filed_against_id:
        return "error:You cannot file a complaint against yourself."

    conn = get_connection()

    # J-002: validate target exists
    target = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (filed_against_id,)
    ).fetchone()
    if not target:
        conn.close()
        return "error:The user you are complaining about does not exist."

    # J-005: store as pending
    conn.execute(
        """INSERT INTO complaints (filed_by, filed_against, description, complaint_type)
           VALUES (?, ?, ?, 'student')""",
        (filed_by, filed_against_id, description.strip())
    )
    conn.commit()
    conn.close()
    return f"success:Your complaint against {target['username']} has been submitted and is pending registrar review."

def file_instructor_complaint(instructor_id, student_id, description, requested_action):
    """
    J-012: instructor files complaint against a student.
    J-013: restrict to students in assigned courses.
    J-014: require requested action (warning or de-registration).
    J-002: validate student exists.
    J-003: block self-complaints.
    """
    if not description or not description.strip():
        return "error:Complaint description cannot be empty."

    if not requested_action or requested_action not in ('warning', 'deregister'):
        return "error:You must specify a requested action: warning or de-registration."

    if instructor_id == student_id:
        return "error:You cannot file a complaint against yourself."

    conn = get_connection()

    # J-002: validate student exists
    student = conn.execute(
        "SELECT id, username FROM users WHERE id = ? AND role = 'student'",
        (student_id,)
    ).fetchone()
    if not student:
        conn.close()
        return "error:That student does not exist."

    # J-013: student must be enrolled in one of the instructor's courses
    enrolled = conn.execute(
        """SELECT e.id FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           WHERE c.instructor_id = ? AND e.student_id = ? AND e.status = 'enrolled'""",
        (instructor_id, student_id)
    ).fetchone()
    if not enrolled:
        conn.close()
        return "error:You can only file complaints against students enrolled in your courses."

    conn.execute(
        """INSERT INTO complaints (filed_by, filed_against, description, complaint_type, requested_action)
           VALUES (?, ?, ?, 'instructor', ?)""",
        (instructor_id, student_id, description.strip(), requested_action)
    )
    conn.commit()
    conn.close()
    return f"success:Your complaint against {student['username']} has been submitted for registrar review."

def get_pending_complaints():
    """J-006: registrar gets all unresolved complaints"""
    conn = get_connection()
    complaints = conn.execute(
        """SELECT c.*,
           u1.username as filed_by_name, u1.role as filed_by_role,
           u2.username as filed_against_name, u2.role as filed_against_role
           FROM complaints c
           JOIN users u1 ON c.filed_by = u1.id
           JOIN users u2 ON c.filed_against = u2.id
           WHERE c.status = 'pending'
           ORDER BY c.created_at DESC"""
    ).fetchall()
    conn.close()
    return complaints

def resolve_student_complaint(complaint_id, warn_target_id, resolution_text):
    """
    J-008/J-009: registrar warns the student or instructor they choose.
    J-010: save resolution notes.
    J-011: remove from pending queue.
    """
    if not resolution_text or not resolution_text.strip():
        return "error:Resolution notes cannot be empty."

    conn = get_connection()
    complaint = conn.execute(
        "SELECT * FROM complaints WHERE id = ? AND status = 'pending'",
        (complaint_id,)
    ).fetchone()
    if not complaint:
        conn.close()
        return "error:Complaint not found or already resolved."

    conn.execute(
        """UPDATE complaints SET status = 'resolved', resolution = ? WHERE id = ?""",
        (resolution_text.strip(), complaint_id)
    )
    conn.commit()
    conn.close()

    # J-008/J-009: issue warning to the chosen user
    issue_warning(warn_target_id, f"Warning from complaint resolution: {resolution_text.strip()}")
    return "success:Complaint resolved and warning issued."

def resolve_instructor_complaint(complaint_id, decision, resolution_text):
    """
    J-015: registrar must act — no silent dismissal.
    J-016: if accepted, warn student.
    J-017: if accepted with deregister action, de-register student.
    J-018: if rejected, warn instructor.
    J-019: update enrolled_count after de-registration.
    """
    if not resolution_text or not resolution_text.strip():
        return "error:Resolution notes cannot be empty."

    if decision not in ('accept', 'reject'):
        return "error:Decision must be accept or reject."

    conn = get_connection()
    complaint = conn.execute(
        "SELECT * FROM complaints WHERE id = ? AND status = 'pending'",
        (complaint_id,)
    ).fetchone()
    if not complaint:
        conn.close()
        return "error:Complaint not found or already resolved."

    conn.execute(
        "UPDATE complaints SET status = 'resolved', resolution = ? WHERE id = ?",
        (resolution_text.strip(), complaint_id)
    )
    conn.commit()
    conn.close()

    student_id = complaint['filed_against']
    instructor_id = complaint['filed_by']
    requested_action = complaint['requested_action']

    if decision == 'accept':
        # J-016: warn the student
        issue_warning(student_id, f"Instructor complaint accepted against you: {resolution_text.strip()}")

        # J-017: de-register student if that was the requested action
        if requested_action == 'deregister':
            _deregister_student_from_instructor_courses(student_id, instructor_id)
            return "success:Complaint accepted. Student warned and de-registered from instructor's courses."
        return "success:Complaint accepted. Student warned."

    else:
        # J-018: reject complaint — warn the instructor for filing
        issue_warning(instructor_id, f"Your complaint was rejected by the registrar: {resolution_text.strip()}")
        return "success:Complaint rejected. Instructor has been warned."

def _deregister_student_from_instructor_courses(student_id, instructor_id):
    """
    J-017: de-registers student from all courses taught by this instructor.
    J-019: updates enrolled_count.
    J-020: records a notification via warning entry.
    """
    conn = get_connection()
    courses = conn.execute(
        """SELECT c.id, c.course_name FROM enrollments e
           JOIN courses c ON e.course_id = c.id
           WHERE c.instructor_id = ? AND e.student_id = ? AND e.status = 'enrolled'""",
        (instructor_id, student_id)
    ).fetchall()

    for course in courses:
        conn.execute(
            "UPDATE enrollments SET status = 'cancelled' WHERE student_id = ? AND course_id = ?",
            (student_id, course['id'])
        )
        # J-019: update enrolled_count
        conn.execute(
            "UPDATE courses SET enrolled_count = enrolled_count - 1 WHERE id = ? AND enrolled_count > 0",
            (course['id'],)
        )

    conn.commit()
    conn.close()

    if courses:
        course_names = ', '.join([c['course_name'] for c in courses])
        # J-020: notify student via warning
        issue_warning(student_id, f"You have been de-registered from: {course_names} following a complaint.")

def mark_fine_paid(user_id):
    """J-028: registrar marks a suspended student's fine as paid"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
        (user_id, "Fine marked as paid by registrar.")
    )
    conn.commit()
    conn.close()
    return "success:Fine marked as paid."


# SEED DATA FOR DEMO

def seed_conduct_data():
    """
    L-014: seed taboo words for review filtering demo.
    L-015: seed warning edge cases for 3-warning suspension demo.
    """
    conn = get_connection()

    # L-014: seed taboo words
    taboo_words = ['hate', 'stupid', 'idiot', 'terrible', 'awful', 'garbage', 'useless']
    for word in taboo_words:
        conn.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word,))

    # L-015: seed a student with 2 warnings (one more = suspended)
    student = conn.execute("SELECT id FROM users WHERE username = 'student2'").fetchone()
    if student:
        existing = conn.execute(
            "SELECT COUNT(*) as c FROM warnings WHERE user_id = ?", (student['id'],)
        ).fetchone()['c']
        if existing == 0:
            conn.execute(
                "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
                (student['id'], "Warning 1: Seeded for demo — 3-warning suspension test.")
            )
            conn.execute(
                "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
                (student['id'], "Warning 2: Seeded for demo — one more warning triggers suspension.")
            )

    conn.commit()
    conn.close()
    print("Conduct seed data inserted.")