-- ============================================================
-- College0 — Full Database Schema
-- Owner: Tanzina Sumona
-- All subsystems share this single SQLite database
-- Run via: python database/db.py
-- ============================================================


-- ============================================================
-- ZHUOLIN — User Management & Authentication Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,      -- used for login
    email TEXT UNIQUE NOT NULL,         -- used for contact/application
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student', 'instructor', 'registrar', 'suspended', 'terminated', 'graduated')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'terminated')),
    must_change_password INTEGER NOT NULL DEFAULT 0,   -- 1 = force password change on next login (UC-11)
    clerk_user_id TEXT UNIQUE,          -- Clerk identity; copied from applications.clerk_user_id on approve
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role_applied TEXT NOT NULL CHECK(role_applied IN ('student', 'instructor')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    clerk_user_id TEXT,                 -- links the Clerk identity that submitted this application (UC-07/08)
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);


-- ============================================================
-- TANZINA — Semester & Course Management Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    semester_gpa REAL DEFAULT 0.0,
    cumulative_gpa REAL DEFAULT 0.0,
    honor_roll INTEGER DEFAULT 0,
    credits_earned INTEGER DEFAULT 0,
    special_registration INTEGER DEFAULT 0,
    termination_pending INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'probation'))
);

CREATE TABLE IF NOT EXISTS semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    current_period TEXT NOT NULL DEFAULT 'setup' CHECK(current_period IN ('setup', 'registration', 'special_registration', 'running', 'grading')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semester_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id INTEGER NOT NULL,
    period_name TEXT NOT NULL CHECK(period_name IN ('setup', 'registration', 'special_registration', 'running', 'grading')),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    FOREIGN KEY (semester_id) REFERENCES semesters(id)
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    instructor_id INTEGER,
    time_slot TEXT,
    day_of_week INTEGER,
    start_time TEXT,
    end_time TEXT,
    capacity INTEGER NOT NULL DEFAULT 30,
    enrolled_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (semester_id) REFERENCES semesters(id),
    FOREIGN KEY (instructor_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    grade TEXT,                         -- NULL until instructor posts grade (used by Alisha's review check)
    status TEXT NOT NULL DEFAULT 'enrolled' CHECK(status IN ('enrolled', 'cancelled')),
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'admitted', 'denied')),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    letter_grade TEXT CHECK(letter_grade IN ('A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F')),
    numeric_value REAL,                 -- GPA equivalent: A=4.0, B=3.0, C=2.0, D=1.0, F=0.0
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS graduation_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    registrar_notes TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id)
);


-- ============================================================
-- ALISHA — Reviews, Warnings & Conduct Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS taboo_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    star_rating INTEGER NOT NULL CHECK(star_rating BETWEEN 1 AND 5),
    review_text TEXT NOT NULL,
    filtered_text TEXT,                 -- stores version with taboo words replaced by *
    is_visible INTEGER DEFAULT 1,       -- 1 = shown, 0 = hidden (3+ taboo words)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (student_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filed_by INTEGER NOT NULL,
    filed_against INTEGER NOT NULL,
    description TEXT NOT NULL,
    complaint_type TEXT DEFAULT 'student' CHECK(complaint_type IN ('student', 'instructor')),
    requested_action TEXT CHECK(requested_action IN ('warning', 'deregister', NULL)),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'resolved')),
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (filed_by) REFERENCES users(id),
    FOREIGN KEY (filed_against) REFERENCES users(id)
);
 
CREATE TABLE IF NOT EXISTS fines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 200.00,
    reason TEXT NOT NULL,
    paid INTEGER NOT NULL DEFAULT 0,        -- 0 = outstanding, 1 = payment submitted by user
    approved INTEGER NOT NULL DEFAULT 0,    -- 0 = pending registrar approval, 1 = approved
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    approved_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- ALMASUR — AI Feature & Creative Feature Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT,
    source TEXT CHECK(source IN ('vector_db', 'llm')),  -- where the answer came from
    role_at_query TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    flagged_by INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'reviewed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_id) REFERENCES ai_queries(id),
    FOREIGN KEY (flagged_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    reason TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS flagged_course_gpas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    class_gpa REAL NOT NULL,
    justification TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'justified', 'warned', 'terminated')),
    flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (instructor_id) REFERENCES users(id)
);