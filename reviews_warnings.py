from database.db import get_connection

# ── TABOO WORD FUNCTIONS ──────────────────────────────────────────────────────

def get_taboo_words():
    """Gets the full list of taboo words from the database"""
    conn = get_connection()
    words = conn.execute("SELECT word FROM taboo_words").fetchall()
    conn.close()
    return [row['word'].lower() for row in words]

def add_taboo_word(word):
    """Registrar adds a new taboo word"""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO taboo_words (word) VALUES (?)", (word.lower(),))
        conn.commit()
        return True
    except:
        return False  # word already exists
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
    Scans review text for taboo words.
    Returns: (filtered_text, taboo_count)
    - filtered_text has bad words replaced with *
    - taboo_count is how many taboo words were found
    """
    taboo_words = get_taboo_words()
    taboo_count = 0
    filtered_text = text

    for word in taboo_words:
        # check each word in the review
        words_in_review = filtered_text.lower().split()
        if word in words_in_review:
            taboo_count += 1
            # replace the bad word with asterisks (keeps same length)
            replacement = '*' * len(word)
            # replace in a case-insensitive way
            import re
            filtered_text = re.sub(re.escape(word), replacement, filtered_text, flags=re.IGNORECASE)

    return filtered_text, taboo_count


# ── REVIEW FUNCTIONS ──────────────────────────────────────────────────────────

def submit_review(student_id, course_id, star_rating, review_text):
    """
    Student submits a review.
    Automatically filters for taboo words and issues warnings.
    Returns a message telling the student what happened.
    """
    # Step 1: check if student is enrolled in the course
    conn = get_connection()
    enrollment = conn.execute(
        "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchone()
    conn.close()

    if not enrollment:
        return "You are not enrolled in this course and cannot review it."

    # Step 2: check if grade has already been posted (review period closed)
    if enrollment['grade'] is not None:
        return "The review period for this course is closed because grades have been posted."

    # Step 3: filter the review for taboo words
    filtered_text, taboo_count = filter_review(review_text)

    # Step 4: apply the rules based on taboo word count
    if taboo_count >= 3:
        # review is hidden, student gets 2 warnings
        issue_warning(student_id, "Review contained 3 or more taboo words and was hidden.")
        issue_warning(student_id, "Second warning for review with 3 or more taboo words.")
        return "Your review was not posted because it contained too many inappropriate words. You have received 2 warnings."

    elif taboo_count in [1, 2]:
        # review is shown but filtered, student gets 1 warning
        save_review(student_id, course_id, star_rating, filtered_text, is_visible=1)
        issue_warning(student_id, f"Review contained {taboo_count} taboo word(s). Words replaced with *.")
        update_course_rating(course_id)
        return "Your review was posted but some inappropriate words were replaced with *. You have received 1 warning."

    else:
        # clean review, post as normal
        save_review(student_id, course_id, star_rating, review_text, is_visible=1)
        update_course_rating(course_id)
        return "Your review was posted successfully!"

def save_review(student_id, course_id, star_rating, text, is_visible):
    """Saves a review to the database"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO reviews 
        (student_id, course_id, star_rating, review_text, filtered_text, is_visible) 
        VALUES (?, ?, ?, ?, ?, ?)""",
        (student_id, course_id, star_rating, text, text, is_visible)
    )
    conn.commit()
    conn.close()

def get_course_reviews(course_id, viewer_role):
    """
    Gets all visible reviews for a course.
    If viewer is registrar, also shows who wrote each review.
    Everyone else just sees anonymous reviews.
    """
    conn = get_connection()
    if viewer_role == 'registrar':
        reviews = conn.execute(
            """SELECT r.*, u.username as reviewer_name 
            FROM reviews r 
            JOIN users u ON r.student_id = u.id
            WHERE r.course_id = ? AND r.is_visible = 1""",
            (course_id,)
        ).fetchall()
    else:
        reviews = conn.execute(
            """SELECT id, course_id, star_rating, review_text, created_at
            FROM reviews 
            WHERE course_id = ? AND is_visible = 1""",
            (course_id,)
        ).fetchall()
    conn.close()
    return reviews

def update_course_rating(course_id):
    """
    Recalculates the average rating for a course.
    If average drops below 2.0, warns the instructor.
    """
    conn = get_connection()
    result = conn.execute(
        "SELECT AVG(star_rating) as avg_rating FROM reviews WHERE course_id = ? AND is_visible = 1",
        (course_id,)
    ).fetchone()
    conn.close()

    if result['avg_rating'] is not None:
        avg = result['avg_rating']
        if avg < 2.0:
            # get the instructor of this course and warn them
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


# ── WARNING FUNCTIONS ─────────────────────────────────────────────────────────

def issue_warning(user_id, reason):
    """
    Issues a warning to a user and checks if threshold is reached.
    Students: 3 warnings = suspended
    Instructors: 3 warnings = suspended
    """
    conn = get_connection()

    # save the warning
    conn.execute(
        "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
        (user_id, reason)
    )
    conn.commit()

    # count total warnings for this user
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

    # apply suspension if threshold reached
    if count >= 3:
        if user['role'] == 'student':
            suspend_user(user_id, "3 warnings accumulated - suspended for 1 semester")
        elif user['role'] == 'instructor':
            suspend_user(user_id, "3 warnings accumulated - suspended from teaching next semester")

def get_user_warnings(user_id):
    """Gets all warnings for a specific user"""
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
    """Suspends a user by updating their role to suspended"""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET role = 'suspended' WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    print(f"User {user_id} has been suspended. Reason: {reason}")


# ── COMPLAINT FUNCTIONS ───────────────────────────────────────────────────────

def file_complaint(filed_by, filed_against, description):
    """Student or instructor files a complaint"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO complaints (filed_by, filed_against, description) 
        VALUES (?, ?, ?)""",
        (filed_by, filed_against, description)
    )
    conn.commit()
    conn.close()
    return "Your complaint has been submitted and is pending registrar review."

def get_pending_complaints():
    """Registrar gets all unresolved complaints"""
    conn = get_connection()
    complaints = conn.execute(
        """SELECT c.*, 
           u1.username as filed_by_name, 
           u2.username as filed_against_name
           FROM complaints c
           JOIN users u1 ON c.filed_by = u1.id
           JOIN users u2 ON c.filed_against = u2.id
           WHERE c.status = 'pending'
           ORDER BY c.created_at DESC"""
    ).fetchall()
    conn.close()
    return complaints

def resolve_complaint(complaint_id, warn_user_id, resolution_text):
    """
    Registrar resolves a complaint.
    warn_user_id: the user who gets the warning as a result
    """
    conn = get_connection()
    conn.execute(
        """UPDATE complaints 
        SET status = 'resolved', resolution = ? 
        WHERE id = ?""",
        (resolution_text, complaint_id)
    )
    conn.commit()
    conn.close()

    # issue warning to whoever the registrar decided to punish
    issue_warning(warn_user_id, f"Warning issued following complaint resolution: {resolution_text}")
    return "Complaint resolved and warning issued."