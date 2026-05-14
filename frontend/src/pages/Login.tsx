import React, { useState } from 'react';

import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

const QUICK_LOGINS = [
  { label: 'Registrar', username: 'registrar1', password: 'password123', cls: 'btn-registrar' },
  { label: 'Instructor', username: 'prof_smith', password: 'password123', cls: 'btn-instructor' },
  { label: 'Student 1', username: 'demo_student1', password: 'password123', cls: 'btn-student1' },
  { label: 'Student 2', username: 'demo_student2', password: 'password123', cls: 'btn-student2' },
];

export function Login(): React.ReactElement {
  const data = getPageData();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(data.error ?? null);
  const [submitting, setSubmitting] = useState(false);

  async function doLogin(u: string, p: string) {
    setSubmitting(true);
    setError(null);
    const resp = await postForm('/login', { username: u, password: p });
    setSubmitting(false);
    if (resp.redirect) {
      navigate(resp.redirect);
      return;
    }
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
      return;
    }
    setError(resp.error || 'Invalid username or password.');
  }

  return (
    <div className="login-shell">
      <div className="login-page">
        <div>
          <h1>College0</h1>
          <p className="subtitle">AI-Enabled College Program System</p>
        </div>

        <div className="login-box" style={{ maxWidth: 400, margin: '0 auto' }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: 12 }}>Sign in</h2>
          {error && <div className="error">{error}</div>}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void doLogin(username, password);
            }}
          >
            <label htmlFor="username">Username</label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="submit" className="block" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <div className="quick-login-strip">
          <p className="label">— Quick Login (Demo) —</p>
          <div className="quick-btns">
            {QUICK_LOGINS.map((q) => (
              <button
                key={q.username}
                type="button"
                className={q.cls}
                disabled={submitting}
                onClick={() => void doLogin(q.username, q.password)}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        <p className="muted" style={{ textAlign: 'center' }}>
          <a href="/apply">Apply for an account</a>
          {' · '}
          <a href="/apply/status">Application status</a> (use the link from your confirmation email)
        </p>
      </div>
    </div>
  );
}
