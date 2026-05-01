# College0 — AI-Enabled College Program Management System
**City College of New York | Software Engineering | Group E**
Alisha Mughal, Zhuolin Li, Tanzina Sumona, Abdullah Altamir, Almasur Antor

---

## Local Setup (Run the Website on Your Computer)

### Requirements
Make sure you have these installed:
- Python 3.10 or higher
- pip (comes with Python)

### Step 1 — Clone the repo
```bash
git clone https://github.com/Alisha-IM05/college0.git
cd college0
```

### Step 2 — Install dependencies
```bash
pip install flask
```

### Step 3 — Set up the database
```bash
python database/db.py
```
This creates the SQLite database file with all the tables.

### Step 4 — Run the website
```bash
python app.py
```
Then open your browser and go to:
```
http://127.0.0.1:5000
```

---

## Folder & File Structure

```
college0/
├── app.py                  # Main Flask app — routes only. Only Alisha merges here.
├── config.py               # Database path and secret key settings
├── README.md               # This file
│
├── modules/                # Backend logic — one file per team member
│   ├── conduct.py          # Alisha — reviews, warnings, complaints, taboo filter
│   ├── semester.py         # Tanzina — courses, registration, GPA, graduation
│   ├── auth.py             # Zhuolin — login, applications, user accounts
│   ├── frontend.py         # Abdullah — page routing and UI navigation
│   └── ai_features.py      # Almasur — AI queries, recommendations, content filter
│
├── templates/              # HTML pages — Abdullah leads, each member owns their subfolder
│   ├── base.html           # Shared layout and navbar used by all pages
│   ├── login.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── courses/
│   │   ├── register.html
│   │   └── class_detail.html
│   ├── conduct/
│   │   ├── reviews.html
│   │   ├── warnings.html
│   │   └── complaints.html
│   └── ai/
│       ├── query.html
│       └── recommendations.html
│
├── database/
│   ├── schema.sql          # All table definitions in one place
│   └── db.py               # Shared get_db() function — everyone imports from here
│
└── static/
    ├── style.css           # Global styles
    └── script.js           # Global scripts
```

---

## How the Code Is Connected

Each person writes logic in their own `modules/` file.
When one module needs another person's function, it simply imports it:

```python
# Example: Tanzina's semester.py calling Alisha's warning function
from modules.conduct import issue_warning

issue_warning(instructor_id, "Course cancelled due to low enrollment")
```

`app.py` connects all the modules together and starts the server.
`database/db.py` is the single shared database connection everyone uses.

---

## Git Workflow

Everyone works on their own branch and opens a pull request to merge into `main`.

```bash
# Start your work
git checkout -b your-name-feature

# Save your work
git add .
git commit -m "description of what you did"
git push origin your-name-feature
```

Then open a Pull Request on GitHub → Alisha reviews → merges into `main`.

**Never push directly to `main`.**

---

## Project Timeline — Due May 12

| Date | Milestone |
|------|-----------|
| May 1 | Repo restructured, all module files created, database schema finalized |
| May 3 | Each member has their core routes and logic working locally |
| May 6 | All modules connected through app.py, site runs end to end |
| May 8 | Cross-module features working (warnings, AI filter, GPA triggers) |
| May 10 | Full walkthrough tested, bugs fixed, demo script prepared |
| May 11 | Final polish, README updated, repo cleaned up |
| **May 12** | **Project due — demo ready** |

---

## Team Responsibilities

| Member | Subsystem | Module File |
|--------|-----------|-------------|
| Alisha Mughal | Reviews, Warnings & Conduct | `modules/conduct.py` |
| Tanzina Sumona | Semester & Course Management | `modules/semester.py` |
| Zhuolin Li | User Management & Authentication | `modules/auth.py` |
| Abdullah Altamir | Frontend UI | `modules/frontend.py` |
| Almasur Antor | AI Feature & Creative Feature | `modules/ai_features.py` |

---

## Demo Login Credentials (for local testing)

| Role | Username | Password |
|------|----------|----------|
| Registrar | registrar1 | password |
| Student | student1 | password |
| Instructor | instructor1 | password |

> These are seeded automatically when you run `python database/db.py`
