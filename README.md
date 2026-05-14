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
pip install -r requirements.txt
```

Most interactive pages (login, dashboard, courses, conduct, semester tools,
applications, profile, AI assistant entry, and more) are a **Vite + React** app
mounted from `templates/_shell.html`, which loads the bundle under
`static/dist/`. Build it before running the server:
```bash
cd frontend
npm install
npm run build      # writes static/dist/assets/{main.js,main.css}
cd ..
```
Re-run `npm run build` whenever a file under `frontend/src/` changes. A few
**legacy Jinja** pages under `templates/` remain for some flows (for example
`semester/flagged_gpas.html` and selected AI admin templates in `templates/ai/`);
those do not require the frontend build.

> **Auth deep dive:** see [AUTH.md](AUTH.md) for the full architecture,
> use-case map (UC-07 through UC-13), data-flow diagrams, API contract,
> and troubleshooting for the Clerk + Flask-session bridge.

### Step 2b — Configure Clerk (for visitor sign-up / status check)
Create a `.env` file at the repo root with your Clerk keys (already gitignored):
```bash
CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CLERK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional: comma-separated list of allowed origins for the Clerk session JWT
# CLERK_AUTHORIZED_PARTIES=http://localhost:5000,http://127.0.0.1:5000
```
The Clerk publishable key is auto-exposed to the visitor pages (`/apply`,
`/apply/status`); the secret key is used server-side to verify Clerk session
tokens. If neither is set, the app still boots — only the visitor-facing
Clerk pages will display a configuration notice.

### Step 3 — Set up the database
```bash
python3 database/db.py
```
This creates the SQLite database file with all the tables.

> **Note:** If you already have a `database/college0.db` from before the auth/applications work
> was merged, delete it once so the new `users.must_change_password`, `users.clerk_user_id`, and
> `applications.clerk_user_id` columns are picked up (SQLite's `CREATE TABLE IF NOT EXISTS` won't
> add columns to an existing table):
> ```bash
> rm database/college0.db && python database/db.py
> ```

### Step 4 — Run the website
```bash
python3 app.py
```
Then open your browser and go to:
```
http://127.0.0.1:5000
```

---

## Folder & File Structure

```
college0/
├── app.py                  # Main Flask app — routes, React shell wiring, JSON APIs
├── config.py               # Database path, secret key, mail/Clerk-related settings
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── AUTH.md                 # Clerk + session bridge (visitor apply / status)
├── .env.example            # Example environment variables (copy to `.env`)
├── seed_chroma.py          # Optional Chroma / vector store seeding for AI features
├── test_semester.py        # Standalone semester DB / logic smoke script
│
├── almasur/                # Experimental AI sandbox code
│   ├── __init__.py
│   └── sandbox.py
│
├── modules/                # Backend logic — one primary file per subsystem
│   ├── __init__.py
│   ├── conduct.py          # Reviews, warnings, complaints, taboo filter, fines
│   ├── semester.py         # Courses, registration, GPA, graduation, semester periods
│   ├── auth.py             # Sessions, applications, passwords, user lifecycle
│   ├── frontend.py         # Shared UI helpers / navigation (Flask side)
│   ├── ai_features.py      # AI routes, recommendations, flags, assistant wiring
│   ├── ai.py               # Additional AI route registration
│   └── mail.py             # Optional outbound email helpers
│
├── frontend/               # Vite + TypeScript React SPA (built into static/dist/)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx        # App entry — mounts page from Flask `page` prop
│       ├── components/     # Banner, Navbar, Pill, Sidebar
│       ├── pages/          # One component per shell page (Login, Dashboard, …)
│       ├── lib/            # api.ts (fetch + JSON), data.ts
│       └── styles/
│           └── global.css
│
├── templates/              # Jinja: React shell, legacy pages, AI HTML fallbacks
│   ├── base.html           # Classic full-page layout (still used where applicable)
│   ├── _shell.html         # Minimal shell — loads React bundle + inline `__data`
│   ├── courses/            # Legacy HTML (e.g. register, class_detail, create, instructor_courses)
│   ├── conduct/            # Legacy HTML (reviews, warnings, complaints, taboo)
│   ├── semester/           # Legacy HTML (manage, graduation, flagged_gpas, …)
│   └── ai/                 # assistant, query, recommendations, flag(s), …
│
├── database/
│   ├── schema.sql          # Table definitions
│   └── db.py               # init_db(), get_db() — single shared DB access
│
├── static/
│   ├── style.css           # Global CSS for classic Jinja pages
│   ├── script.js           # Global JS for classic Jinja pages
│   └── dist/               # Created by `npm run build` in frontend/
│       └── assets/         # main.js, main.css (Vite output)
│
└── tests/
    └── test_auth_features.py
```

`database/college0.db` is created when you run `python database/db.py` (see Step 3).  
`frontend/node_modules/` is created by `npm install` and is not shown above.

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
The React UI in `frontend/` is compiled into `static/dist/` and mounted by
`templates/_shell.html` using JSON data passed from each route.

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
