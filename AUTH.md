# College0 Authentication

How sign-up, login, and account management work in College0, and how
the system covers Use Cases UC-07 through UC-13.

## How it works

College0 uses two cooperating identity systems:

- **Clerk** handles public sign-up + sign-in (the widget on `/apply`
  and `/`). Visitors create one Clerk account and reuse it forever.
- **Flask sessions + the `users` table** are the in-app source of truth
  for roles and access. Every page reads `session['role']` and
  `session['user_id']`.

A Clerk identity is linked to an app account by storing the Clerk user
id on `users.clerk_user_id`. When an approved user signs in with Clerk
on `/`, the server verifies the JWT, looks up the matching user row,
and opens a normal Flask session.

A small username/password backdoor (`POST /login`) is kept for the four
seeded demo accounts (`registrar1`, `instructor1`, `student1`,
`student2`) so the demo works without anyone needing Clerk accounts.

```mermaid
flowchart LR
  V[Visitor] -->|Clerk SignUp| Apply[/apply]
  Apply -->|JWT verified| App[applications table]
  App -->|Registrar approves| Users[users table]
  Users -->|temp password| User[New user]
  User -->|Clerk SignIn at /| Bridge[/auth/clerk-login]
  Bridge --> Session[Flask session]
  Session --> Dashboard[/dashboard]
```

## Use cases

| UC | Purpose | Key code |
|----|---------|----------|
| UC-07 / UC-08 | Visitor submits student / instructor application | `submit_application` in [modules/auth.py](modules/auth.py), `/apply` in [app.py](app.py), [Apply.tsx](frontend/src/pages/Apply.tsx) |
| UC-09 | Registrar approves / rejects | `approve_application`, `reject_application`, [RegistrarApplications.tsx](frontend/src/pages/RegistrarApplications.tsx) |
| UC-10 | New user gets username + temp password | Generated inside `approve_application`; shown to registrar and on `/apply/status` |
| UC-11 | First-login password change | `enforce_password_change` guard + `/change-password` routes, [ChangePassword.tsx](frontend/src/pages/ChangePassword.tsx) |
| UC-12 | Role-based access control | `@require_role` decorator in [modules/auth.py](modules/auth.py) |
| UC-13 | Suspend / terminate / reactivate | `suspend_user` / `terminate_user` / `reactivate_user`, [RegistrarUsers.tsx](frontend/src/pages/RegistrarUsers.tsx) |

## Two ways to sign in

Both paths end up populating the same Flask `session['user_id']`,
`session['username']`, `session['role']` — everything downstream is
identical.

- **Clerk (real users):** sign in on `/`, the React `ClerkBridge`
  POSTs the JWT to `/auth/clerk-login`, the server matches it to a
  `users` row by `clerk_user_id`, and redirects to `/change-password`
  (if `must_change_password = 1`) or `/dashboard`.
- **Demo backdoor:** the Quick Login buttons on `/` POST to `/login`
  with a seeded username/password.

The Clerk widget's "Sign up" link points at `/apply`, so anyone signing
up still goes through registrar approval — UC-09 stays intact.

## Setup

1. Install dependencies and build the React bundle:

   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && npm run build && cd ..
   ```

2. Create `.env` at the repo root with your Clerk keys:

   ```bash
   CLERK_PUBLISHABLE_KEY=pk_test_...
   CLERK_SECRET_KEY=sk_test_...
   ```

   Without these, `/apply`, `/apply/status`, and `/` show a "Clerk not
   configured" notice; the demo backdoor still works.

3. Initialize / reset the database:

   ```bash
   rm -f database/college0.db && python database/db.py
   ```

4. Run:

   ```bash
   python app.py
   ```

## Sign-out detail

`/logout` clears the Flask session and redirects to `/?signed_out=1`.
The login page's bridge sees that flag and also calls `clerk.signOut()`
before reloading, so a stale Clerk session can't silently sign the
user back in.

## Security notes

This is coursework, not production. If you reuse any of it:

- Hash `users.password` (currently plaintext).
- Move `app.secret_key` to an env var.
- Remove the demo backdoor.
- Add CSRF protection and rate limiting.
