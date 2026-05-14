# Semester & Course Management by Tanzina Sumona
from database.db import get_db
from modules.conduct import issue_warning, _insert_warning_only, suspend_instructor


PERIOD_ORDER = ['setup', 'registration', 'special_registration', 'running', 'grading']
GPA_MAP = {
    'A+': 4.0, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D+': 1.3, 'D': 1.0, 'D-': 0.7,
    'F': 0.0
}

def get_current_semester():
    """Returns the active semester — newest non-completed semester first."""
    conn = get_db()
    try:
        return conn.execute(
            """SELECT * FROM semesters
               ORDER BY CASE current_period
                   WHEN 'grading' THEN 5
                   WHEN 'running' THEN 4
                   WHEN 'special_registration' THEN 3
                   WHEN 'registration' THEN 2
                   WHEN 'setup' THEN 1
               END ASC, id DESC LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()

def get_current_period():
    """Returns the current period string, or None."""
    sem = get_current_semester()
    return sem['current_period'] if sem else None

def get_active_semester():
    """Returns the newest semester that still has work to do (not grading-completed)."""
    conn = get_db()
    try:
        # Prefer any semester not in grading, newest first
        result = conn.execute(
            """SELECT * FROM semesters
               WHERE current_period != 'grading'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        # If all semesters are in grading, just return the newest
        if result is None:
            result = conn.execute(
                "SELECT * FROM semesters ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return result
    finally:
        conn.close()


# Move a semester to the next period.
# Returns: the new period name if successful
# an error message if something goes wrong
def advance_period(semester_id):
    conn = get_db()
    try:
        semester = conn.execute(
            "SELECT * FROM semesters WHERE id = ?",
            (semester_id,)
        ).fetchone()
        if semester is None:
            return "Semester not found"
        current_period = semester["current_period"]
        if current_period == "grading":
            current_name = semester["name"]
            if "Spring" in current_name:
                year = int(current_name.split(" ")[1])
                new_name = f"Fall {year}"
            else:
                year = int(current_name.split(" ")[1])
                new_name = f"Spring {year + 1}"

            # Collect missing-grade warnings — fire AFTER conn closes to avoid lock
            missing_grade_warnings = []
            courses_this_semester = conn.execute(
                "SELECT * FROM courses WHERE semester_id = ? AND status = 'active'",
                (semester_id,)
            ).fetchall()
            for course in courses_this_semester:
                enrolled_students = conn.execute(
                    "SELECT student_id FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
                    (course['id'],)
                ).fetchall()
                for student in enrolled_students:
                    grade = conn.execute(
                        "SELECT * FROM grades WHERE student_id = ? AND course_id = ?",
                        (student['student_id'], course['id'])
                    ).fetchone()
                    if grade is None:
                        missing_grade_warnings.append((
                            course['instructor_id'],
                            f"You did not submit all grades for '{course['course_name']}' before the grading period ended."
                        ))
                        break  # one warning per course is enough

            conn.execute("UPDATE students SET special_registration = 0")
            # Terminate any students flagged during grading
            pending = conn.execute(
                "SELECT id FROM students WHERE termination_pending = 1"
            ).fetchall()
            for s in pending:
                conn.execute(
                    "UPDATE users SET role = 'terminated' WHERE id = ?",
                    (s['id'],)
                )
            conn.execute("UPDATE students SET termination_pending = 0")
            existing = conn.execute(
                "SELECT * FROM semesters WHERE name = ?", (new_name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE semesters SET current_period = 'setup' WHERE id = ?",
                    (existing['id'],)
                )
            else:
                conn.execute(
                    "INSERT INTO semesters (name, current_period) VALUES (?, 'setup')",
                    (new_name,)
                )
            conn.commit()
            conn.close()

            # Fire warnings after conn is fully closed — avoids "database is locked"
            for user_id, reason in missing_grade_warnings:
                issue_warning(user_id, reason)

            return f"New semester {new_name} created in setup period"
        current_index = PERIOD_ORDER.index(current_period)
        next_period = PERIOD_ORDER[current_index + 1]
        conn.execute(
            "UPDATE semesters SET current_period = ? WHERE id = ?",
            (next_period, semester_id)
        )
        conn.execute(
            """INSERT INTO semester_periods (semester_id, period_name, start_date)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (semester_id, next_period)
        )
        conn.commit()
        return next_period
    finally:
        conn.close()

# Create a new course for a semester
# Only allowed during the setup period
# Returns:
# 'Course created successfully' if it works
# an error message if something goes wrong
def create_course(semester_id, name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity):
    conn = get_db()
    try:
        # Get the semester from the database
        semester = conn.execute(
            "SELECT * FROM semesters WHERE id = ?",
            (semester_id,)
        ).fetchone()
        # Check if the semester exists
        if semester is None:
            return 'Semester not found'
        # Make sure we are in the setup period
        if semester['current_period'] != 'setup':
            return 'Course setup is only allowed during the setup period'
        # Check if a course with the same name already exists in this semester
        existing_course = conn.execute(
            "SELECT * FROM courses WHERE course_name = ? AND semester_id = ?",
            (name, semester_id)
        ).fetchone()
        if existing_course:
            return 'A course with this name already exists this semester'
        # Check if the instructor exists and has the correct role
        instructor = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'instructor'",
            (instructor_id,)
        ).fetchone()
        if instructor is None:
            return 'Instructor not found'
        if instructor['status'] == 'suspended':
            return 'This instructor is suspended and cannot teach next semester'
        # Insert the new course into the database
        conn.execute(
            """INSERT INTO courses (semester_id, course_name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity, enrolled_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')""",
            (semester_id, name, instructor_id, time_slot, day_of_week, start_time, end_time, capacity)
        )
        conn.commit()
        return 'Course created successfully'
    finally:
        conn.close()


# Register a student for a course
# If the course is full, add the student to the waitlist
# Returns:
#  'Student enrolled successfully' if it works
#  a waitlist message if the course is full
#  an error message if something goes wrong
def register_student(student_id, course_id):
    conn = get_db()
    try:
        # Block students who are no longer active
        user = conn.execute(
            "SELECT role, status FROM users WHERE id = ?",
            (student_id,)
        ).fetchone()
        if user and user['role'] == 'graduated':
            return 'You have graduated and no longer have active student access'
        if user and user['role'] == 'terminated':
            return 'Your enrollment has been terminated. Please contact the registrar'
        if user and user['status'] == 'suspended':
            return 'Your account is suspended. Please contact the registrar'
        # Get the semester for this course
        semester = conn.execute(
            "SELECT * FROM semesters WHERE id = (SELECT semester_id FROM courses WHERE id = ?)",
            (course_id,)
        ).fetchone()
        # Check if semester exists
        if semester is None:
            return 'Semester not found'
        # Check if registration period is open
        if semester['current_period'] != 'registration':
            # Check if student has special registration eligibility
            special = conn.execute(
                "SELECT special_registration FROM students WHERE id = ?",
                (student_id,)
            ).fetchone()
            if not special or special['special_registration'] == 0:
                return 'Registration is not currently open'
        # Check if student is already enrolled in this course
        already_enrolled = conn.execute(
            """
            SELECT * FROM enrollments 
            WHERE student_id = ? AND course_id = ? AND status = 'enrolled'
            """,
            (student_id, course_id)
        ).fetchone()
        if already_enrolled:
            return 'Student is already enrolled in this course'
        # Count how many courses the student is enrolled in THIS semester only
        enrolled_count = conn.execute(
            """SELECT COUNT(*) as count FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            WHERE e.student_id = ? AND e.status = 'enrolled'
            AND c.semester_id = (SELECT semester_id FROM courses WHERE id = ?)""",
            (student_id, course_id)
        ).fetchone()['count']

        waitlist_count = conn.execute(
            """SELECT COUNT(*) as count FROM waitlist w
            JOIN courses c ON w.course_id = c.id
            WHERE w.student_id = ?
            AND c.semester_id = (SELECT semester_id FROM courses WHERE id = ?)""",
            (student_id, course_id)
        ).fetchone()['count']
        # Check max course limit (4) — enrolled + waitlisted combined
        if enrolled_count + waitlist_count >= 4:
            return 'Student has reached the maximum of 4 courses (enrolled + waitlisted combined)'
        # Check if student has taken this course before
        past_grade = conn.execute(
            """SELECT g.letter_grade FROM grades g
               JOIN courses c1 ON g.course_id = c1.id
               JOIN courses c2 ON c2.id = ?
               WHERE g.student_id = ?
               AND c1.course_name = c2.course_name
               ORDER BY g.id DESC LIMIT 1""",
            (course_id, student_id)
        ).fetchone()
        # Only allow retake if previous grade was F
        if past_grade and past_grade['letter_grade'] != 'F':
            return 'Student cannot retake a course without a prior F grade'
        # Check for missing time slot data — treat as unsafe
        new_course = conn.execute(
            "SELECT day_of_week, start_time, end_time FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        if new_course and (new_course['day_of_week'] is None or 
                        new_course['start_time'] is None or 
                        new_course['end_time'] is None):
            return 'Cannot register — course time slot data is incomplete. Contact the registrar.'
        # Check for time conflicts
        conflict_course = get_conflict_course(student_id, course_id, conn)
        if conflict_course:
            return f'Time conflict: {conflict_course["course_name"]} ({conflict_course["time_slot"]} {conflict_course["start_time"]}-{conflict_course["end_time"]}) overlaps with the course you are trying to register for'
        # Get course details
        course = conn.execute(
            "SELECT * FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        # If course is full, add to waitlist instead
        if course['enrolled_count'] >= course['capacity']:
            return add_to_waitlist(student_id, course_id)
        # Enroll the student
        conn.execute(
            """
            INSERT INTO enrollments (student_id, course_id, status)
            VALUES (?, ?, 'enrolled')
            """,
            (student_id, course_id)
        )
        # Increase enrolled count
        conn.execute(
            "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
            (course_id,)
        )
        conn.commit()
        return 'Student enrolled successfully'
    finally:
        conn.close()


# Check if a student has a time conflict with a new course
# Returns:
#  True if there IS a conflict
#  False if there is NO conflict
def parse_time_slot(time_slot):
    """Parse 'Mon/Wed 10:00-11:30' into (days, start_minutes, end_minutes)"""
    try:
        parts = time_slot.strip().split(' ')
        days = set(parts[0].split('/'))
        times = parts[1].split('-')
        def to_minutes(t):
            h, m = t.split(':')
            return int(h) * 60 + int(m)
        start = to_minutes(times[0])
        end = to_minutes(times[1])
        return days, start, end
    except:
        return None, None, None

def times_overlap(days1, start1, end1, days2, start2, end2):
    """Check if two time slots overlap"""
    if not days1 & days2:  # no common days
        return False
    return start1 < end2 and start2 < end1

def get_conflict_course(student_id, course_id, conn=None):
    """Returns the conflicting course dict or None"""
    close = False
    if conn is None:
        conn = get_db()
        close = True
    try:
        new_course = conn.execute(
            "SELECT day_of_week, start_time, end_time, time_slot FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        if new_course is None or new_course['day_of_week'] is None:
            return None
        existing = conn.execute(
            """SELECT c.*
               FROM courses c
               JOIN enrollments e ON c.id = e.course_id
               WHERE e.student_id = ? AND e.status = 'enrolled'
               AND c.semester_id = (SELECT semester_id FROM courses WHERE id = ?)""",
            (student_id, course_id)
        ).fetchall()
        new_days = set(new_course['time_slot'].split('/'))
        for course in existing:
            if course['day_of_week'] is None:
                continue
            existing_days = set(course['time_slot'].split('/'))
            if not new_days & existing_days:
                continue
            if new_course['start_time'] < course['end_time'] and course['start_time'] < new_course['end_time']:
                return course
        return None
    finally:
        if close:
            conn.close()

def check_conflict(student_id, course_id):
    conn = get_db()
    try:
        new_course = conn.execute(
            "SELECT day_of_week, start_time, end_time, time_slot FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        if new_course is None:
            return True
        # Fall back to text parsing if new columns not set
        if new_course['day_of_week'] is None:
            return False
        existing = conn.execute(
            """SELECT c.day_of_week, c.start_time, c.end_time, c.time_slot
               FROM courses c
               JOIN enrollments e ON c.id = e.course_id
               WHERE e.student_id = ? AND e.status = 'enrolled'
               AND c.semester_id = (SELECT semester_id FROM courses WHERE id = ?)""",
            (student_id, course_id)
        ).fetchall()
        for course in existing:
            if course['day_of_week'] is None:
                continue
            # Check same day — for Mon/Wed (1) and Tue/Thu (3), Fri (5), Wed/Fri (4)
            # We use time_slot string to check shared days
            new_days = set(new_course['time_slot'].split('/'))
            existing_days = set(course['time_slot'].split('/'))
            if not new_days & existing_days:
                continue
            # Check time overlap
            new_start = new_course['start_time']
            new_end = new_course['end_time']
            ex_start = course['start_time']
            ex_end = course['end_time']
            if new_start < ex_end and ex_start < new_end:
                return True
        return False
    finally:
        conn.close()


# Add a student to a course waitlist (FIFO order)
# Returns:
#  success message with position if added
#  an error message if something goes wrong
def add_to_waitlist(student_id, course_id):
    conn = get_db()
    try:
        # Check if the student is already on the waitlist for this course
        existing_entry = conn.execute(
            "SELECT * FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id)
        ).fetchone()
        if existing_entry:
            return 'Student is already on the waitlist for this course'
        # Find the next position in the waitlist
        # Count current students and add 1
        current_count = conn.execute(
            "SELECT COUNT(*) as count FROM waitlist WHERE course_id = ?",
            (course_id,)
        ).fetchone()['count']
        position = current_count + 1
        # Add the student to the waitlist
        conn.execute(
            """
            INSERT INTO waitlist (student_id, course_id, position)
            VALUES (?, ?, ?)
            """,
            (student_id, course_id, position)
        )
        conn.commit()
        return 'Student added to waitlist at position ' + str(position)
    finally:
        conn.close()


# Admit a student from the waitlist into a course
# This is  done by the instructor
# Returns:
#  success message if admitted
#  an error message if something goes wrong
def admit_from_waitlist(course_id, student_id, instructor_id=None):
    conn = get_db()
    try:
        # Get course details
        course = conn.execute(
            "SELECT * FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        if course is None:
            return 'Course not found'
        # Check instructor is assigned to this course
        if instructor_id and course['instructor_id'] != instructor_id:
            return 'You are not the instructor assigned to this course'
        # Check time conflict for the student being admitted
        conflict = get_conflict_course(student_id, course_id, conn)
        if conflict:
            return f'Cannot admit — time conflict with {conflict["course_name"]} ({conflict["time_slot"]} {conflict["start_time"]}-{conflict["end_time"]})'
        # Instructors can override capacity for waitlisted students
        # capacity increases by 1 to accommodate the admitted student
        conn.execute(
            "UPDATE courses SET capacity = capacity + 1 WHERE id = ?",
            (course_id,)
        )
        # Check if the student is on the waitlist
        waitlist_entry = conn.execute(
            "SELECT * FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id)
        ).fetchone()
        if waitlist_entry is None:
            return 'Student is not on the waitlist for this course'
        already_enrolled = conn.execute(
            """SELECT * FROM enrollments
            WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
            (student_id, course_id)
        ).fetchone()
        if already_enrolled:
            return 'Student is already enrolled in this course'
        # Instructors can override capacity — increase AFTER validation
        conn.execute(
            "UPDATE courses SET capacity = capacity + 1 WHERE id = ?",
            (course_id,)
        )
  
        # Remove the student from the waitlist
        conn.execute(
            "DELETE FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id)
        )
        # Move everyone behind this student up one position
        conn.execute(
            """
            UPDATE waitlist 
            SET position = position - 1 
            WHERE course_id = ? AND position > ?
            """,
            (course_id, waitlist_entry['position'])
        )
        # Add the student to enrollments
        conn.execute(
            """
            INSERT INTO enrollments (student_id, course_id, status)
            VALUES (?, ?, 'enrolled')
            """,
            (student_id, course_id)
        )
        # Increase enrolled count
        conn.execute(
            "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
            (course_id,)
        )
        conn.commit()
        return 'Student admitted from waitlist successfully'
    finally:
        conn.close()

# Enforce minimum enrollment rules for a semester
# Cancels courses with fewer than 3 students
# Warns instructors whose courses were cancelled
# Suspends instructors if all their courses are cancelled
# Reopens registration for affected students
def enforce_minimums(semester_id):
    conn = get_db()
    # Collect (user_id, reason) pairs to warn AFTER the connection closes.
    # issue_warning() opens its own connection; calling it while conn is open
    # causes "database is locked" on SQLite.
    conduct_warnings = []   # list of (user_id, reason) — count toward suspension
    instructors_to_suspend = []  # list of user_id — all courses cancelled
    try:
        courses = conn.execute(
            "SELECT * FROM courses WHERE semester_id = ? AND status = 'active'",
            (semester_id,)
        ).fetchall()

        for course in courses:
            if course['enrolled_count'] < 3:
                conn.execute(
                    "UPDATE courses SET status = 'cancelled' WHERE id = ?",
                    (course['id'],)
                )
                conn.execute(
                    "UPDATE enrollments SET status = 'cancelled' WHERE course_id = ?",
                    (course['id'],)
                )
                affected = conn.execute(
                    "SELECT student_id FROM enrollments WHERE course_id = ? AND status = 'cancelled'",
                    (course['id'],)
                ).fetchall()
                for s in affected:
                    conn.execute(
                        "UPDATE students SET special_registration = 1 WHERE id = ?",
                        (s['student_id'],)
                    )
                # Queue instructor warning — fired after conn closes
                conduct_warnings.append((
                    course['instructor_id'],
                    f"Your course '{course['course_name']}' was cancelled due to low enrollment (fewer than 3 students)."
                ))

        instructors = conn.execute(
            "SELECT DISTINCT instructor_id FROM courses WHERE semester_id = ?",
            (semester_id,)
        ).fetchall()

        for instructor in instructors:
            active_count = conn.execute(
                """SELECT COUNT(*) as count FROM courses
                   WHERE instructor_id = ? AND semester_id = ? AND status = 'active'""",
                (instructor['instructor_id'], semester_id)
            ).fetchone()['count']
            if active_count == 0:
                instructors_to_suspend.append(instructor['instructor_id'])

        cancelled_courses = conn.execute(
            "SELECT * FROM courses WHERE semester_id = ? AND status = 'cancelled'",
            (semester_id,)
        ).fetchall()
        cancelled_count = len(cancelled_courses)

        if cancelled_count > 0:
            conn.execute(
                "UPDATE semesters SET current_period = 'special_registration' WHERE id = ?",
                (semester_id,)
            )

        # Collect underenrolled student notices (these use _insert_warning_only, no lock risk,
        # but keep them deferred too for consistency)
        underenrolled_notices = []
        students = conn.execute(
            """SELECT DISTINCT e.student_id
               FROM enrollments e JOIN courses c ON e.course_id = c.id
               WHERE c.semester_id = ? AND e.status = 'enrolled'""",
            (semester_id,)
        ).fetchall()
        for student in students:
            active_count = conn.execute(
                """SELECT COUNT(*) as count FROM enrollments e
                   JOIN courses c ON e.course_id = c.id
                   WHERE e.student_id = ? AND c.semester_id = ?
                   AND e.status = 'enrolled' AND c.status = 'active'""",
                (student['student_id'], semester_id)
            ).fetchone()['count']
            if active_count < 2:
                underenrolled_notices.append(student['student_id'])

        affected_students = conn.execute(
            """SELECT DISTINCT e.student_id
               FROM enrollments e JOIN courses c ON e.course_id = c.id
               WHERE c.semester_id = ? AND e.status = 'cancelled'""",
            (semester_id,)
        ).fetchall()
        for s in affected_students:
            conn.execute(
                "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
                (s['student_id'], 'One or more of your courses was cancelled. Special registration is now open for you.')
            )

        affected_count = len(affected_students)
        conn.commit()
    finally:
        conn.close()

    # ── Fire all warnings/suspensions AFTER the connection is closed ──────────
    for user_id, reason in conduct_warnings:
        issue_warning(user_id, reason)

    for user_id in instructors_to_suspend:
        suspend_instructor(user_id, "All courses this semester were cancelled due to low enrollment.")

    for student_id in underenrolled_notices:
        _insert_warning_only(
            student_id,
            'You are enrolled in fewer than 2 courses this semester — you may want to register for more.'
        )

    if cancelled_count == 0:
        return 'Semester advanced to running. No courses were cancelled.'
    else:
        return (f'Semester advanced to running. '
                f'{cancelled_count} course(s) cancelled due to low enrollment. '
                f'{affected_count} student(s) given special registration.')
    try:
        # Get all students who are enrolled in at least one course this semester
        students = conn.execute(
            """
            SELECT DISTINCT e.student_id
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            WHERE c.semester_id = ? AND e.status = 'enrolled'
            """,
            (semester_id,)
        ).fetchall()
        # Check each student
        for student in students:
            # Count how many active courses the student is enrolled in
            active_count = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
                AND c.semester_id = ?
                AND e.status = 'enrolled'
                AND c.status = 'active'
                """,
                (student['student_id'], semester_id)
            ).fetchone()['count']
            # G-005: warn student — administrative notice, does NOT count toward conduct suspension
            if active_count < 2:
                _insert_warning_only(
                    student['student_id'],
                    'You are enrolled in fewer than 2 courses this semester — you may want to register for more.'
                )
            conn.commit()
    finally:
        if close:
            conn.close()


# Submit a grade for a student
# Only allowed during the grading period
# Updates the student's GPA after the grade is saved
# Returns:
#  success message if grade is submitted
#  an error message if something goes wrong
def submit_grade(instructor_id, student_id, course_id, letter_grade):
    conn = get_db()
    try:
        # Get the semester for this course
        semester = conn.execute(
            """
            SELECT * FROM semesters
            WHERE id = (SELECT semester_id FROM courses WHERE id = ?)
            """,
            (course_id,)
        ).fetchone()
        # Check if semester exists
        if semester is None:
            return 'Semester not found'
        # Make sure grades can only be submitted during grading period
        if semester['current_period'] != 'grading':
            return 'Grade submission is only allowed during the grading period'
        # Get the course
        course = conn.execute(
            "SELECT * FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        # Check if the instructor is assigned to this course
        if course['instructor_id'] != instructor_id:
            return 'Instructor is not assigned to this course'
        # Check if the student is enrolled in the course
        enrolled = conn.execute(
            """
            SELECT * FROM enrollments
            WHERE student_id = ?
            AND course_id = ?
            AND status = 'enrolled'
            """,
            (student_id, course_id)
        ).fetchone()
        if enrolled is None:
            return 'Student is not enrolled in this course'
        # Check if the letter grade is valid
        if letter_grade not in GPA_MAP:
            return 'Invalid grade entered'
        # Convert the letter grade into a GPA number
        numeric_grade = GPA_MAP[letter_grade]
        # Check if this student already has a grade for this course
        existing_grade = conn.execute(
            """
            SELECT * FROM grades
            WHERE student_id = ? AND course_id = ?
            """,
            (student_id, course_id)
        ).fetchone()
        # If a grade already exists, update it
        if existing_grade:
            conn.execute(
                """
                UPDATE grades
                SET letter_grade = ?,
                    numeric_value = ?,
                    submitted_at = CURRENT_TIMESTAMP
                WHERE student_id = ? AND course_id = ?
                """,
                (letter_grade, numeric_grade, student_id, course_id)
            )
            if existing_grade['letter_grade'] == 'F' and letter_grade != 'F':
                conn.execute(
                    "UPDATE students SET credits_earned = credits_earned + 1 WHERE id = ?",
                    (student_id,)
                )
            elif existing_grade['letter_grade'] != 'F' and letter_grade == 'F':
                conn.execute(
                    "UPDATE students SET credits_earned = credits_earned - 1 WHERE id = ?",
                    (student_id,)
                )
        # If no grade exists yet, insert a new grade
        else:
            conn.execute(
                """
                INSERT INTO grades (student_id, course_id, letter_grade, numeric_value)
                VALUES (?, ?, ?, ?)
                """,
                (student_id, course_id, letter_grade, numeric_grade)
            )
            # Only add earned credit if the student passed
            if letter_grade != 'F':
                conn.execute(
                    "UPDATE students SET credits_earned = credits_earned + 1 WHERE id = ?",
                    (student_id,)
                )
        conn.commit()
        # Recalculate GPA after saving the grade
        calculate_gpa(student_id, semester['id'])


        # Flag instructor if class GPA is above 3.5 or below 2.5
        class_gpa = conn.execute(
            """
            SELECT AVG(g.numeric_value) as avg_gpa
            FROM grades g
            WHERE g.course_id = ?
            """,
            (course_id,)
        ).fetchone()['avg_gpa']

        if class_gpa is not None:
            if class_gpa > 3.5 or class_gpa < 2.5:
                # Check if already flagged for this course
                already_flagged = conn.execute(
                    "SELECT id FROM flagged_course_gpas WHERE course_id = ? AND status = 'pending'",
                    (course_id,)
                ).fetchone()
                if not already_flagged:
                    conn.execute(
                        """INSERT INTO flagged_course_gpas (course_id, instructor_id, class_gpa)
                        VALUES (?, ?, ?)""",
                        (course_id, instructor_id, class_gpa)
                    )
                conn.commit()

        return 'Grade submitted successfully'
    finally:
        conn.close()

# Recalculate a student's semester GPA and cumulative GPA
# Updates the students table
# Also checks the student's academic standing
def calculate_gpa(student_id, semester_id=None):
    conn = get_db()
    try:
        grades = conn.execute(
            "SELECT * FROM grades WHERE student_id = ?",
            (student_id,)
        ).fetchall()
        if not grades:
            return
        # Use provided semester_id, or fall back to the one currently in grading
        if semester_id is None:
            sem_row = conn.execute(
                """SELECT id FROM semesters WHERE current_period = 'grading'
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            semester_id = sem_row['id'] if sem_row else None
        if semester_id is None:
            return
        current_semester_grades = conn.execute(
            """SELECT g.numeric_value
               FROM grades g
               JOIN courses c ON g.course_id = c.id
               WHERE g.student_id = ? AND c.semester_id = ?""",
            (student_id, semester_id)
        ).fetchall()
        if not current_semester_grades:
            return
        semester_total = sum(g['numeric_value'] for g in current_semester_grades)
        semester_gpa = semester_total / len(current_semester_grades)
        cumulative_total = sum(g['numeric_value'] for g in grades)
        cumulative_gpa = cumulative_total / len(grades)
        conn.execute(
            """UPDATE students
               SET semester_gpa = ?, cumulative_gpa = ?
               WHERE id = ?""",
            (semester_gpa, cumulative_gpa, student_id)
        )
        conn.commit()
        update_academic_standing(student_id, semester_gpa, cumulative_gpa)
    finally:
        conn.close()

# Update a student's academic standing based on GPA rules
# Terminates students with low GPA or repeated failed courses
# Adds warnings for probation-level GPA
# Adds honor roll count for high GPA
def update_academic_standing(student_id, semester_gpa, cumulative_gpa):
    conn = get_db()
    try:
        # Count how many courses the student failed at least twice
        failed_twice_count = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM (
                SELECT course_id
                FROM grades
                WHERE student_id = ? AND letter_grade = 'F'
                GROUP BY course_id
                HAVING COUNT(*) >= 2
            )
            """,
            (student_id,)
        ).fetchone()['count']
        # Terminate the student if GPA is too low or they failed a course twice
        if cumulative_gpa < 2.0 or failed_twice_count > 0:
            conn.execute(
                "UPDATE students SET termination_pending = 1 WHERE id = ?",
                (student_id,)
            )
            conn.execute(
                "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
                (student_id, 'Your GPA has fallen below the minimum threshold. You will be terminated at the start of the next semester unless resolved.')
            )
            conn.commit()
            conn.close()
            return
        # Academic notice — does NOT count toward conduct suspension threshold
        if 2.0 <= cumulative_gpa <= 2.25:
            _insert_warning_only(
                student_id,
                'GPA between 2.0 and 2.25 — probation interview required.'
            )

        # Count how many semesters this student has grades for
        semester_count = conn.execute(
            """
            SELECT COUNT(DISTINCT c.semester_id) as count
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = ?
            """,
            (student_id,)
        ).fetchone()['count']
        # Add honor roll if semester GPA or cumulative GPA is high enough
        if semester_gpa > 3.75 or (semester_count > 1 and cumulative_gpa > 3.5):
            conn.execute(
                "UPDATE students SET honor_roll = honor_roll + 1 WHERE id = ?",
                (student_id,)
            )
        conn.commit()
    finally:
        conn.close()


# Submit a graduation application for a student
# Student must have at least 8 completed credits
# Only one pending application allowed at a time
# Returns:
#  success message if application is submitted
#  an error message if something goes wrong
def apply_for_graduation(student_id):
    conn = get_db()
    try:
        # Get student information
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()
        # Check if student exists and has enough credits
        if student is None or student['credits_earned'] < 8:
            # I-031/I-040: warn student for applying before completing 8 courses
            if student is not None:
                issue_warning(
                    student_id,
                    f"Reckless graduation application — you have only completed {student['credits_earned']} of 8 required courses."
                )
            return 'Student has not completed the required 8 courses. A warning has been issued.'
        # Check if there is already a pending graduation application
        existing_application = conn.execute(
            """
            SELECT * FROM graduation_applications
            WHERE student_id = ? AND status = 'pending'
            """,
            (student_id,)
        ).fetchone()
        if existing_application:
            return 'A graduation application is already pending'
        # Insert new graduation application
        conn.execute(
            """
            INSERT INTO graduation_applications (student_id, status)
            VALUES (?, 'pending')
            """,
            (student_id,)
        )
        conn.commit()
        return 'Graduation application submitted and pending registrar review'
    finally:
        conn.close()


# Approve or reject a graduation application
# This is usually done by the registrar
# If approved, the student is marked as graduated
# If rejected, the student gets a warning
# Returns:
#  success message if application is resolved
#  an error message if something goes wrong
def resolve_graduation(application_id, approved):
    conn = get_db()
    try:
        application = conn.execute(
            "SELECT * FROM graduation_applications WHERE id = ?",
            (application_id,)
        ).fetchone()
        if application is None:
            return 'Application not found'
        if application['status'] != 'pending':
            return 'Application has already been resolved'

        if approved:
            # Verify student has 8 passed, non-cancelled courses
            completed = conn.execute(
                "SELECT credits_earned FROM students WHERE id = ?",
                (application['student_id'],)
            ).fetchone()['credits_earned']
            if completed < 8:
                return f'Cannot approve — student has only completed {completed} of 8 required courses'
            conn.execute(
                """UPDATE graduation_applications
                   SET status = 'approved',
                       resolved_at = CURRENT_TIMESTAMP,
                       registrar_notes = 'Bachelor''s degree awarded'
                   WHERE id = ?""",
                (application_id,)
            )
            conn.execute(
                "UPDATE users SET role = 'graduated' WHERE id = ?",
                (application['student_id'],)
            )
            conn.commit()
            return 'Student has been graduated and removed from the system'
        else:
            conn.execute(
                """UPDATE graduation_applications
                   SET status = 'rejected',
                       resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (application_id,)
            )
            student_id_rej = application['student_id']
            conn.commit()
            conn.close()
            issue_warning(student_id_rej, 'Reckless graduation application — required courses not covered.')
            return 'Application rejected. Warning issued to student'
    finally:
        pass  # conn already closed above
        
def use_honor_roll_to_remove_warning(student_id, warning_id):
    conn = get_db()
    try:
        # Check student has unused honor roll distinctions
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()
        if student is None:
            return 'Student not found'
        if student['honor_roll'] <= 0:
            return 'No honor roll distinctions available to use'
        # Check the warning exists and belongs to this student
        warning = conn.execute(
            "SELECT * FROM warnings WHERE id = ? AND user_id = ?",
            (warning_id, student_id)
        ).fetchone()
        if warning is None:
            return 'Warning not found'
        # Remove the warning
        conn.execute(
            "DELETE FROM warnings WHERE id = ?",
            (warning_id,)
        )
        # Use up one honor roll distinction
        conn.execute(
            "UPDATE students SET honor_roll = honor_roll - 1 WHERE id = ?",
            (student_id,)
        )
        conn.commit()
        return 'Warning removed using honor roll distinction'
    finally:
        conn.close()
        
        
def submit_gpa_justification(instructor_id, flag_id, justification):
    conn = get_db()
    try:
        flag = conn.execute(
            "SELECT * FROM flagged_course_gpas WHERE id = ? AND instructor_id = ?",
            (flag_id, instructor_id)
        ).fetchone()
        if flag is None:
            return 'Flag not found or not assigned to you'
        if flag['status'] != 'pending':
            return 'This flag has already been resolved'
        conn.execute(
            """UPDATE flagged_course_gpas
               SET justification = ?, status = 'justified'
               WHERE id = ?""",
            (justification, flag_id)
        )
        conn.commit()
        return 'Justification submitted successfully'
    finally:
        conn.close()


def resolve_gpa_flag(registrar_id, flag_id, decision):
    """
    decision: 'accept', 'warn', or 'terminate'
    """
    conn = get_db()
    try:
        flag = conn.execute(
            "SELECT * FROM flagged_course_gpas WHERE id = ?",
            (flag_id,)
        ).fetchone()
        if flag is None:
            return 'Flag not found'
        if flag['status'] not in ['pending', 'justified']:
            return 'This flag has already been resolved'
        if decision == 'accept':
            conn.execute(
                """UPDATE flagged_course_gpas
                   SET status = 'justified', resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (flag_id,)
            )
            conn.commit()
            return 'Justification accepted — no penalty issued'
        elif decision == 'warn':
            conn.execute(
                """UPDATE flagged_course_gpas
                   SET status = 'warned', resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (flag_id,)
            )
            instructor_id_warn = flag['instructor_id']
            class_gpa_val = flag['class_gpa']
            conn.commit()
            conn.close()
            issue_warning(instructor_id_warn, f'Inadequate justification for flagged class GPA of {class_gpa_val:.2f}')
            return 'Warning issued to instructor'
        elif decision == 'terminate':
            conn.execute(
                """UPDATE flagged_course_gpas
                   SET status = 'terminated', resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (flag_id,)
            )
            conn.execute(
                "UPDATE users SET status = 'terminated' WHERE id = ?",
                (flag['instructor_id'],)
            )
            conn.commit()
            return 'Instructor terminated'
        else:
            return 'Invalid decision'
    finally:
        conn.close()