"""Auth regression tests (isolated DB via COLLEGE0_DATABASE)."""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid

_fd, _TEST_DB = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["COLLEGE0_DATABASE"] = _TEST_DB

import app as college0_app  # noqa: E402
from database.db import get_db  # noqa: E402
from modules.auth import (  # noqa: E402
    approve_application,
    get_applications_for_user_id,
    get_applications_for_view_token,
    reject_application,
    submit_application,
    suspend_user,
)


class AuthFeaturesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flask_app = college0_app.app
        cls.flask_app.testing = True
        cls.client = cls.flask_app.test_client()

    def test_submit_duplicate_pending_email(self):
        u = uuid.uuid4().hex[:8]
        email = f"dup.{u}@example.com"
        a1 = submit_application("Ann", "Lee", email, "student")
        self.assertTrue(a1[0], a1[1])
        a2 = submit_application("Ann", "Other", email, "instructor")
        self.assertFalse(a2[0])
        self.assertIn("pending", a2[1].lower())

    def test_view_token_status_and_approve(self):
        u = uuid.uuid4().hex[:8]
        email = f"maria.{u}@example.com"
        ok, msg, tok = submit_application("Maria", "Garcia", email, "student")
        self.assertTrue(ok, msg)
        self.assertIsNotNone(tok)
        urow = get_db().execute(
            "SELECT id, applicant_only, password FROM users WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()
        self.assertIsNotNone(urow)
        self.assertEqual(int(urow["applicant_only"]), 1)
        submit_password = urow["password"]
        rows = get_applications_for_view_token(tok)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertTrue(str(rows[0]["issued_username"] or "").lower().startswith("maria"))
        self.assertEqual(rows[0]["issued_temp_password"], submit_password)
        app_id = rows[0]["id"]
        res = approve_application(app_id)
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(str(res.get("username", "")).lower().startswith("maria"))
        self.assertNotIn("temp_password", res)
        rows2 = get_applications_for_view_token(tok)
        self.assertEqual(rows2[0]["status"], "approved")
        uid = res["user_id"]
        ao = get_db().execute(
            "SELECT applicant_only, password, must_change_password FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        self.assertEqual(int(ao["applicant_only"]), 0)
        self.assertEqual(ao["password"], submit_password)
        self.assertEqual(int(ao["must_change_password"]), 1)
        by_session = get_applications_for_user_id(uid)
        self.assertEqual(len(by_session), 1)
        self.assertEqual(by_session[0]["status"], "approved")

    def test_submit_succeeds_without_mail_config(self):
        u = uuid.uuid4().hex[:8]
        email = f"nosubmit.{u}@example.com"
        ok, msg, tok = submit_application("N", "S", email, "student")
        self.assertTrue(ok, msg)
        self.assertIsNotNone(tok)
        self.assertIn("status", msg.lower())
        n = get_db().execute(
            "SELECT COUNT(*) AS c FROM applications WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()["c"]
        self.assertEqual(n, 1)

    def test_approve_succeeds_without_mail_config(self):
        u = uuid.uuid4().hex[:8]
        email = f"approveok.{u}@example.com"
        ok, msg, tok = submit_application("A", "Ok", email, "student")
        self.assertTrue(ok, msg)
        app_id = get_applications_for_view_token(tok)[0]["id"]
        res = approve_application(app_id)
        self.assertTrue(res.get("ok"), res)
        row = get_db().execute("SELECT status FROM applications WHERE id = ?", (app_id,)).fetchone()
        self.assertEqual(row["status"], "approved")

    def test_reject_application(self):
        u = uuid.uuid4().hex[:8]
        email = f"reject.{u}@example.com"
        ok, msg, tok = submit_application("R", "J", email, "instructor")
        self.assertTrue(ok, msg)
        app_id = get_applications_for_view_token(tok)[0]["id"]
        ok2, msg2 = reject_application(app_id)
        self.assertTrue(ok2, msg2)
        row = get_db().execute(
            "SELECT status FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        self.assertEqual(row["status"], "rejected")
        n_user = get_db().execute(
            "SELECT COUNT(*) AS c FROM users WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()["c"]
        self.assertEqual(n_user, 0)

    def test_applicant_redirected_from_dashboard(self):
        u = uuid.uuid4().hex[:8]
        email = f"app.{u}@example.com"
        ok, msg, _tok = submit_application("App", "User", email, "student")
        self.assertTrue(ok, msg)
        pw_row = get_db().execute(
            "SELECT username, password FROM users WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()
        self.assertIsNotNone(pw_row)
        r = self.client.post(
            "/login",
            data={"username": pw_row["username"], "password": pw_row["password"]},
            follow_redirects=False,
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("change-password", r.headers.get("Location", ""))
        r2 = self.client.post(
            "/change-password",
            data={
                "old_password": pw_row["password"],
                "new_password": "newsecret1",
                "confirm_password": "newsecret1",
            },
            follow_redirects=False,
        )
        self.assertEqual(r2.status_code, 302)
        self.assertIn("apply/status", r2.headers.get("Location", ""))
        r3 = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(r3.status_code, 302)
        self.assertIn("apply/status", r3.headers.get("Location", ""))

    def test_suspended_login_json_redirect(self):
        u = uuid.uuid4().hex[:8]
        conn = get_db()
        conn.execute(
            """INSERT INTO users (username, email, password, role, status)
               VALUES (?, ?, 'secretpw', 'student', 'suspended')""",
            (f"sus_{u}", f"sus_{u}@test.com"),
        )
        conn.commit()
        conn.close()
        r = self.client.post(
            "/login",
            data={"username": f"sus_{u}", "password": "secretpw"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertFalse(data.get("ok"))
        self.assertIn("account-blocked", data.get("redirect", ""))
        self.assertIn("suspended", data.get("redirect", ""))

    def test_class_detail_student_not_enrolled_403(self):
        u = uuid.uuid4().hex[:8]
        conn = get_db()
        sem_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM semesters").fetchone()[0]
        conn.execute(
            "INSERT INTO semesters (id, name, current_period) VALUES (?, ?, 'registration')",
            (sem_id, f"Test Sem {u}"),
        )
        conn.execute(
            """INSERT INTO users (username, email, password, role, status)
               VALUES (?, ?, 'pw', 'student', 'active')""",
            (f"tstu_{u}", f"tstu_{u}@test.com"),
        )
        sid = conn.execute("SELECT id FROM users WHERE username = ?", (f"tstu_{u}",)).fetchone()["id"]
        conn.execute("INSERT OR IGNORE INTO students (id) VALUES (?)", (sid,))
        inst = conn.execute(
            "SELECT id FROM users WHERE role = 'instructor' LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(inst)
        iid = inst["id"]
        cid = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM courses").fetchone()[0]
        conn.execute(
            """INSERT INTO courses (id, semester_id, course_name, instructor_id, time_slot,
               day_of_week, start_time, end_time, capacity, enrolled_count, status)
               VALUES (?, ?, ?, ?, 'Mon', 1, '09:00', '10:00', 10, 0, 'active')""",
            (cid, sem_id, f"Isolation {u}", iid),
        )
        conn.commit()
        conn.close()
        with self.client.session_transaction() as sess:
            sess["user_id"] = sid
            sess["username"] = f"tstu_{u}"
            sess["role"] = "student"
        r = self.client.get(f"/courses/{cid}")
        self.assertEqual(r.status_code, 403)

    def test_suspend_user_helper(self):
        u = uuid.uuid4().hex[:8]
        conn = get_db()
        conn.execute(
            """INSERT INTO users (username, email, password, role, status)
               VALUES (?, ?, 'pw', 'student', 'active')""",
            (f"victim_{u}", f"vic_{u}@test.com"),
        )
        conn.commit()
        vid = conn.execute("SELECT id FROM users WHERE username = ?", (f"victim_{u}",)).fetchone()["id"]
        conn.close()
        ok, _msg = suspend_user(vid)
        self.assertTrue(ok)
        st = get_db().execute("SELECT status FROM users WHERE id = ?", (vid,)).fetchone()["status"]
        self.assertEqual(st, "suspended")


if __name__ == "__main__":
    unittest.main()
