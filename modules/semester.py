# Semester & Course Management by Tanzina Sumona
from database.db import get_db


PERIOD_ORDER = ['setup', 'registration', 'running', 'grading']
GPA_MAP = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}


# Move a semester to the next period.
# Returns: the new period name if successful
# an error message if something goes wrong
def advance_period(semester_id):
    conn = get_db()
    try:
        # Get the semester from the database
        semester = conn.execute(
            "SELECT * FROM semesters WHERE id = ?",
            (semester_id,)
        ).fetchone()
        # If no semester was found, stop here
        if semester is None:
            return "Semester not found"
        # Get the current period for this semester
        current_period = semester["current_period"]
        # If the semester is already in the last period, create a new semester
        if current_period == "grading":
            current_name = semester["name"]
            if "Spring" in current_name:
                year = int(current_name.split(" ")[1])
                new_name = f"Fall {year}"
            else:
                year = int(current_name.split(" ")[1])
                new_name = f"Spring {year + 1}"
            conn.execute(
                "INSERT INTO semesters (name, current_period) VALUES (?, 'setup')",
                (new_name,)
            )
            conn.commit()
            return f"New semester {new_name} created in setup period"
        # Find the current period's position in the list
        current_index = PERIOD_ORDER.index(current_period)
        # Move to the next period in the list
        next_period = PERIOD_ORDER[current_index + 1]
        # Update the semester's current period
        conn.execute(
            "UPDATE semesters SET current_period = ? WHERE id = ?",
            (next_period, semester_id)
        )
        # Record when this new period started
        conn.execute( 
            """
            INSERT INTO semester_periods (semester_id, period_name, start_date)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (semester_id, next_period)
        )
        # Save the database changes
        conn.commit()
        return next_period
    finally:
        conn.close()


# Create a new course for a semester
# Only allowed during the setup period
# Returns:
# 'Course created successfully' if it works
# an error message if something goes wrong
def create_course(semester_id, name, instructor_id, time_slot, capacity):
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
        # Insert the new course into the database
        conn.execute(
            """
            INSERT INTO courses 
            (semester_id, course_name, instructor_id, time_slot, capacity, enrolled_count, status)
            VALUES (?, ?, ?, ?, ?, 0, 'active')
            """,
            (semester_id, name, instructor_id, time_slot, capacity)
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
        # Count how many courses the student is currently enrolled in
        enrolled_count = conn.execute(
            """
            SELECT COUNT(*) as count 
            FROM enrollments 
            WHERE student_id = ? AND status = 'enrolled'
            """,
            (student_id,)
        ).fetchone()['count']
        # Check max course limit (4)
        if enrolled_count >= 4:
            return 'Student has reached the maximum of 4 courses'
        # Check if student has taken this course before
        past_grade = conn.execute(
            "SELECT * FROM grades WHERE student_id = ? AND course_id = ?",
            (student_id, course_id)
        ).fetchone()
        # Only allow retake if previous grade was F
        if past_grade and past_grade['letter_grade'] != 'F':
            return 'Student cannot retake a course without a prior F grade'
        # Check for time conflicts with existing courses
        if check_conflict(student_id, course_id):
            return 'Time conflict detected with an existing course'
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
def check_conflict(student_id, course_id):
    conn = get_db()
    try:
        # Get the time slot of the new course the student wants
        new_course = conn.execute(
            "SELECT time_slot FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        # If the course doesn't exist, block it (treat as conflict)
        if new_course is None:
            return True
        # Get all time slots of courses the student is already enrolled in
        existing_slots = conn.execute(
            """
            SELECT c.time_slot 
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ? AND e.status = 'enrolled'
            """,
            (student_id,)
        ).fetchall()
        # Check each existing course for a time conflict
        for slot in existing_slots:
            if slot['time_slot'] == new_course['time_slot']:
                return True  # conflict found
        # If no conflicts were found
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
def admit_from_waitlist(course_id, student_id):
    conn = get_db()
    try:
        # Get course details
        course = conn.execute(
            "SELECT * FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        # Check if there is space in the course
        if course['enrolled_count'] >= course['capacity']:
            return 'No seats available in this course'
        # Check if the student is on the waitlist
        waitlist_entry = conn.execute(
            "SELECT * FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id)
        ).fetchone()
        if waitlist_entry is None:
            return 'Student is not on the waitlist for this course'
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
    try:
        # Get all active courses for this semester
        courses = conn.execute(
            """
            SELECT * FROM courses
            WHERE semester_id = ? AND status = 'active'
            """,
            (semester_id,)
        ).fetchall()
        # Check each course to see if it has enough students
        for course in courses:
            if course['enrolled_count'] < 3:
                # Cancel the course
                conn.execute(
                    "UPDATE courses SET status = 'cancelled' WHERE id = ?",
                    (course['id'],)
                )
                # Cancel all enrollments for this course
                conn.execute(
                    "UPDATE enrollments SET status = 'cancelled' WHERE course_id = ?",
                    (course['id'],)
                )
                # Warn the instructor
                conn.execute(
                    """
                    INSERT INTO warnings (user_id, reason)
                    VALUES (?, ?)
                    """,
                    (
                        course['instructor_id'],
                        'Your course was cancelled due to low enrollment'
                    )
                )
        # Get all instructors who taught courses this semester
        instructors = conn.execute(
            """
            SELECT DISTINCT instructor_id
            FROM courses
            WHERE semester_id = ?
            """,
            (semester_id,)
        ).fetchall()
        # Check if each instructor still has any active courses
        for instructor in instructors:
            active_count = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM courses
                WHERE instructor_id = ?
                AND semester_id = ?
                AND status = 'active'
                """,
                (instructor['instructor_id'], semester_id)
            ).fetchone()['count']
            # If the instructor has no active courses, suspend them
            if active_count == 0:
                conn.execute(
                    """
                    UPDATE users
                    SET status = 'suspended'
                    WHERE id = ? AND role = 'instructor'
                    """,
                    (instructor['instructor_id'],)
                )
        # Open special registration again
        conn.execute(
            """
            UPDATE semesters
            SET current_period = 'registration'
            WHERE id = ?
            """,
            (semester_id,)
        )
        # Warn students whose courses were cancelled
        warn_underenrolled_students(semester_id)
        # Save all changes
        conn.commit()
        return 'Minimum enrollment rules enforced successfully'
    finally:
        conn.close()

# Warn students who are enrolled in fewer than 2 active courses
# Only checks students in the given semester
# Returns nothing (just updates the database)
def warn_underenrolled_students(semester_id):
    conn = get_db()
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
            # If the student has fewer than 2 active courses, send a warning
            if active_count < 2:
                conn.execute(
                    """
                    INSERT INTO warnings (user_id, reason)
                    VALUES (?, ?)
                    """,
                    (
                        student['student_id'],
                        'You are enrolled in fewer than 2 courses this semester'
                    )
                )
        conn.commit()
    finally:
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
        calculate_gpa(student_id)

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
                conn.execute(
                    """
                    INSERT INTO warnings (user_id, reason)
                    VALUES (?, ?)
                    """,
                    (
                        instructor_id,
                        f'Your course GPA of {class_gpa:.2f} has been flagged for registrar review (outside 2.5–3.5 range)'
                    )
                )
                conn.commit()

        return 'Grade submitted successfully'
    finally:
        conn.close()

# Recalculate a student's semester GPA and cumulative GPA
# Updates the students table
# Also checks the student's academic standing
def calculate_gpa(student_id):
    conn = get_db()
    try:
        # Get all grades for this student
        grades = conn.execute(
            "SELECT * FROM grades WHERE student_id = ?",
            (student_id,)
        ).fetchall()
        # If the student has no grades, there is nothing to calculate
        if not grades:
            return
        # Get this student's current semester grades
        current_semester_grades = conn.execute(
            """
            SELECT g.numeric_value
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            JOIN semesters s ON c.semester_id = s.id
            WHERE g.student_id = ?
            AND s.current_period = 'grading'
            """,
            (student_id,)
        ).fetchall()
        # If there are no current semester grades, avoid dividing by zero
        if not current_semester_grades:
            return
        # Calculate semester GPA
        semester_total = sum(grade['numeric_value'] for grade in current_semester_grades)
        semester_gpa = semester_total / len(current_semester_grades)
        # Calculate cumulative GPA using all grades
        cumulative_total = sum(grade['numeric_value'] for grade in grades)
        cumulative_gpa = cumulative_total / len(grades)
        # Update the student record with the new GPAs
        conn.execute(
            """
            UPDATE students
            SET semester_gpa = ?, cumulative_gpa = ?
            WHERE id = ?
            """,
            (semester_gpa, cumulative_gpa, student_id)
        )
        conn.commit()
        # Update academic standing based on GPA
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
                "UPDATE users SET role = 'terminated' WHERE id = ?",
                (student_id,)
            )
            conn.commit()
            return
        # Add a warning if the student needs a probation interview
        if 2.0 <= cumulative_gpa <= 2.25:
            conn.execute(
                """
                INSERT INTO warnings (user_id, reason)
                VALUES (?, ?)
                """,
                (
                    student_id,
                    'GPA between 2.0 and 2.25 — probation interview required'
                )
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
            return 'Student has not completed the required 8 courses'
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
        # Get the graduation application
        application = conn.execute(
            "SELECT * FROM graduation_applications WHERE id = ?",
            (application_id,)
        ).fetchone()
        # Check if the application exists
        if application is None:
            return 'Application not found'
        # Make sure the application has not already been approved or rejected
        if application['status'] != 'pending':
            return 'Application has already been resolved'
        # If registrar approves the application
        if approved:
            conn.execute(
                """
                UPDATE graduation_applications
                SET status = 'approved',
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (application_id,)
            )
            # Mark student as graduated
            conn.execute(
                "UPDATE users SET role = 'graduated' WHERE id = ?",
                (application['student_id'],)
            )
            conn.commit()
            return 'Student has been graduated and removed from the system'
        # If registrar rejects the application
        else:
            conn.execute(
                """
                UPDATE graduation_applications
                SET status = 'rejected',
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (application_id,)
            )
            conn.execute(
                """
                INSERT INTO warnings (user_id, reason)
                VALUES (?, ?)
                """,
                (
                    application['student_id'],
                    'Reckless graduation application — required courses not covered'
                )
            )
            conn.commit()
            return 'Application rejected. Warning issued to student'
    finally:
        conn.close()