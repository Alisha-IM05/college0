-- Users table (shared with whole team, basic version for now)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL -- 'registrar', 'instructor', 'student', 'visitor'
);

-- Reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    star_rating INTEGER NOT NULL CHECK(star_rating BETWEEN 1 AND 5),
    review_text TEXT NOT NULL,
    filtered_text TEXT,         -- stores the version with taboo words replaced by *
    is_visible INTEGER DEFAULT 1, -- 1 = shown, 0 = hidden (3+ taboo words)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id)
);

-- Warnings table
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Taboo words table
CREATE TABLE IF NOT EXISTS taboo_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE
);

-- Complaints table
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filed_by INTEGER NOT NULL,       -- user who filed the complaint
    filed_against INTEGER NOT NULL,  -- user being complained about
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',   -- 'pending', 'resolved'
    resolution TEXT,                 -- what the registrar decided
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (filed_by) REFERENCES users(id),
    FOREIGN KEY (filed_against) REFERENCES users(id)
);

-- Courses table (basic, your teammates will expand this)
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    instructor_id INTEGER,
    FOREIGN KEY (instructor_id) REFERENCES users(id)
);

-- Course enrollments table
CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    grade TEXT,                      -- NULL until instructor posts grade
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);