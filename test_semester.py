import sys
import os

base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base, 'database'))
sys.path.insert(0, os.path.join(base, 'modules'))

from db import get_db, init_db

# fresh start every run
init_db()
conn = get_db()
conn.execute("DELETE FROM warnings")
conn.execute("DELETE FROM waitlist")
conn.execute("DELETE FROM enrollments")
conn.execute("DELETE FROM courses")
conn.execute("DELETE FROM semesters")
conn.execute("DELETE FROM users")
conn.commit()

# seed users
conn.execute("INSERT INTO users (id, username, email, password, role, status) VALUES (1, 'registrar1', 'r@test.com', 'password', 'registrar', 'active')")
conn.execute("INSERT INTO users (id, username, email, password, role, status) VALUES (2, 'instructor1', 'i1@test.com', 'password', 'instructor', 'active')")
conn.execute("INSERT INTO users (id, username, email, password, role, status) VALUES (3, 'instructor2', 'i2@test.com', 'password', 'instructor', 'active')")
conn.execute("INSERT INTO users (id, username, email, password, role, status) VALUES (4, 'student1', 's1@test.com', 'password', 'student', 'active')")
conn.execute("INSERT INTO users (id, username, email, password, role, status) VALUES (5, 'student2', 's2@test.com', 'password', 'student', 'active')")

# seed semester
conn.execute("INSERT INTO semesters (id, name, current_period) VALUES (1, 'Spring 2026', 'registration')")

# seed courses
conn.execute("INSERT INTO courses (id, semester_id, course_name, instructor_id, time_slot, capacity, enrolled_count) VALUES (1, 1, 'CS101', 2, 'Mon/Wed 10:00-11:30', 30, 0)")
conn.execute("INSERT INTO courses (id, semester_id, course_name, instructor_id, time_slot, capacity, enrolled_count) VALUES (2, 1, 'CS201', 2, 'Tue/Thu 13:00-14:30', 30, 0)")
conn.execute("INSERT INTO courses (id, semester_id, course_name, instructor_id, time_slot, capacity, enrolled_count) VALUES (3, 1, 'MATH101', 3, 'Mon/Wed 14:00-15:30', 30, 0)")
conn.execute("INSERT INTO courses (id, semester_id, course_name, instructor_id, time_slot, capacity, enrolled_count) VALUES (4, 1, 'ENG101', 3, 'Fri 09:00-12:00', 30, 0)")
conn.commit()
conn.close()

from semester import (advance_period, create_course, register_student,
                      check_conflict, add_to_waitlist, admit_from_waitlist,
                      enforce_minimums, submit_grade)

print("=== advance_period ===")
print(advance_period(1))   # running
print(advance_period(1))   # grading
print(advance_period(1))   # already final
print(advance_period(99))  # not found

# reset to registration for next tests
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'registration' WHERE id = 1")
conn.commit()
conn.close()

print("\n=== create_course ===")
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'setup' WHERE id = 1")
conn.commit()
conn.close()
print(create_course(1, "CS999", 2, "Mon/Wed 12:00-13:30", 25))  # success
print(create_course(1, "CS999", 2, "Mon/Wed 12:00-13:30", 25))  # duplicate
print(create_course(1, "CS888", 99, "Mon/Wed 12:00-13:30", 25)) # bad instructor

print("\n=== register_student ===")
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'registration' WHERE id = 1")
conn.commit()
conn.close()
print(register_student(4, 1))  # success
print(register_student(4, 1))  # already enrolled
print(register_student(4, 2))  # success - different slot
print(register_student(4, 3))  # conflict - same slot as course 1... wait no, Mon/Wed 14:00 is different, should succeed

print("\n=== check_conflict ===")
print(check_conflict(4, 1))   # True - already enrolled same slot
print(check_conflict(4, 4))   # False - Fri slot, no conflict

print("\n=== enforce_minimums ===")
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'running' WHERE id = 1")
conn.commit()
conn.close()
enforce_minimums(1)
conn = get_db()
courses = conn.execute("SELECT id, course_name, status FROM courses").fetchall()
for c in courses:
    print(c['id'], c['course_name'], c['status'])
warnings = conn.execute("SELECT * FROM warnings").fetchall()
print('warnings issued:', len(warnings))
suspended = conn.execute("SELECT username FROM users WHERE status = 'suspended'").fetchall()
for s in suspended:
    print('suspended:', s['username'])
conn.close()

# re-enroll student for grading tests
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'registration' WHERE id = 1")
conn.execute("UPDATE courses SET status = 'active', enrolled_count = 0 WHERE id = 1")
conn.execute("DELETE FROM enrollments WHERE student_id = 4 AND course_id = 1")
conn.commit()
conn.close()

from semester import register_student
register_student(4, 1)  # enroll student 4 in course 1

# now set to grading
conn = get_db()
conn.execute("UPDATE semesters SET current_period = 'grading' WHERE id = 1")
conn.commit()
conn.close()

print("\n=== submit_grade ===")
print(submit_grade(2, 4, 1, 'A'))   # should succeed
print(submit_grade(2, 4, 1, 'B'))   # should succeed - update existing
print(submit_grade(3, 4, 1, 'A'))   # should fail - wrong instructor
print(submit_grade(2, 5, 1, 'A'))   # should fail - student not enrolled
print(submit_grade(2, 4, 99, 'A'))  # should fail - semester not found


from semester import calculate_gpa, update_academic_standing

# seed students table first
conn = get_db()
conn.execute("INSERT OR IGNORE INTO students (id, semester_gpa, cumulative_gpa, honor_roll, credits_earned) VALUES (4, 0.0, 0.0, 0, 0)")
conn.commit()
conn.close()

print("\n=== calculate_gpa ===")
calculate_gpa(4)
conn = get_db()
student = conn.execute("SELECT * FROM students WHERE id = 4").fetchone()
print('semester_gpa:', student['semester_gpa'])
print('cumulative_gpa:', student['cumulative_gpa'])
print('honor_roll:', student['honor_roll'])
conn.close()

print("\n=== update_academic_standing ===")

# test termination - submit F grade
conn = get_db()
conn.execute("INSERT OR IGNORE INTO students (id, semester_gpa, cumulative_gpa, honor_roll, credits_earned) VALUES (5, 0.0, 0.0, 0, 0)")
conn.execute("INSERT OR IGNORE INTO enrollments (student_id, course_id, status) VALUES (5, 2, 'enrolled')")
conn.execute("INSERT OR IGNORE INTO grades (student_id, course_id, letter_grade, numeric_value) VALUES (5, 2, 'F', 0.0)")
conn.commit()
conn.close()

update_academic_standing(5, 0.0, 0.0)  # should terminate
conn = get_db()
user = conn.execute("SELECT role FROM users WHERE id = 5").fetchone()
print('terminated student role:', user['role'])  # should be terminated

# test probation warning
update_academic_standing(4, 2.1, 2.1)  # should issue probation warning
warnings = conn.execute("SELECT * FROM warnings WHERE user_id = 4").fetchall()
print('probation warnings:', len(warnings))  # should be 1

# test honor roll
update_academic_standing(4, 3.9, 3.9)  # should get honor roll
student = conn.execute("SELECT honor_roll FROM students WHERE id = 4").fetchone()
print('honor roll:', student['honor_roll'])  # should be 1
conn.close()

from semester import apply_for_graduation, resolve_graduation

print("\n=== apply_for_graduation ===")
print(apply_for_graduation(4))   # should fail - not enough credits
conn = get_db()
conn.execute("UPDATE students SET credits_earned = 8 WHERE id = 4")
conn.commit()
conn.close()
print(apply_for_graduation(4))   # should succeed
print(apply_for_graduation(4))   # should fail - already pending

conn = get_db()
apps = conn.execute("SELECT * FROM graduation_applications").fetchall()
for a in apps:
    print('app id:', a['id'], 'student:', a['student_id'], 'status:', a['status'])
conn.close()

print("\n=== resolve_graduation ===")
# get the pending application id dynamically
conn = get_db()
app = conn.execute("SELECT id FROM graduation_applications WHERE student_id = 4 AND status = 'pending'").fetchone()
app_id = app['id']
conn.close()

print(resolve_graduation(app_id, True))   # should approve
print(resolve_graduation(app_id, True))   # should fail - already resolved
print(resolve_graduation(99, True))       # should fail - not found

conn = get_db()
user = conn.execute("SELECT role FROM users WHERE id = 4").fetchone()
print('graduated student role:', user['role'])  # should be graduated
conn.close()