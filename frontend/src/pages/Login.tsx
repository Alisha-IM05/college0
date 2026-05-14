import React, { useState } from 'react';
import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

const QUICK_LOGINS = {
  registrar: [
    { label: 'Registrar 1', username: 'registrar1', password: 'password123' },
  ],
  instructor: [
    { label: 'Prof. Smith', username: 'prof_smith', password: 'password123' },
    { label: 'Prof. Jones', username: 'prof_jones', password: 'password123' },
  ],
  student: [
    { label: 'Demo Student 1', username: 'demo_student1', password: 'password123' },
    { label: 'Demo Student 2', username: 'demo_student2', password: 'password123' },
    { label: 'Alice', username: 'alice', password: 'password123' },
    { label: 'Bob', username: 'bob', password: 'password123' },
    { label: 'Carol', username: 'carol', password: 'password123' },
    { label: 'David', username: 'david', password: 'password123' },
    { label: 'Eve', username: 'eve', password: 'password123' },
    { label: 'Frank', username: 'frank', password: 'password123' },
    { label: 'Grace', username: 'grace', password: 'password123' },
    { label: 'Henry', username: 'henry', password: 'password123' },
  ],
};

export function Login(): React.ReactElement {
  const data = getPageData() as any;
  const [demoError, setDemoError] = useState<string | null>(data.error ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function doDemoLogin(u: string, p: string) {
    setSubmitting(true);
    setDemoError(null);
    const resp = await postForm('/login', { username: u, password: p });
    setSubmitting(false);
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
    } else {
      setDemoError(resp.error || 'Invalid username or password.');
    }
  }

  async function handleManualLogin(e: React.FormEvent) {
    e.preventDefault();
    await doDemoLogin(username, password);
  }

  function QuickDropdown({
    label,
    color,
    users,
  }: {
    label: string;
    color: string;
    users: { label: string; username: string; password: string }[];
  }) {
    const [selected, setSelected] = useState('');

    if (users.length === 1) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: '#64748b' }}>
            {label}
          </label>
          <button
            type="button"
            disabled={submitting}
            onClick={() => void doDemoLogin(users[0].username, users[0].password)}
            style={{ padding: '8px 24px', borderRadius: 8, border: 'none', background: color, color: 'white', fontWeight: 700, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap' }}
          >
            {users[0].label} →
          </button>
        </div>
      );
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
        <label style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: '#64748b' }}>
          {label}
        </label>
        <div style={{ display: 'flex', gap: 6 }}>
          <select
            value={selected}
            onChange={e => setSelected(e.target.value)}
            disabled={submitting}
            style={{ flex: 1, minWidth: 160, padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 13, background: 'white', color: selected ? '#1e293b' : '#94a3b8', outline: 'none', cursor: 'pointer' }}
          >
            <option value="">Select {label}...</option>
            {users.map(u => (
              <option key={u.username} value={u.username}>{u.label}</option>
            ))}
          </select>
          <button
            type="button"
            disabled={submitting || !selected}
            onClick={() => {
              const user = users.find(u => u.username === selected);
              if (user) void doDemoLogin(user.username, user.password);
            }}
            style={{ padding: '8px 14px', borderRadius: 8, border: 'none', background: selected ? color : '#e2e8f0', color: selected ? 'white' : '#94a3b8', fontWeight: 700, fontSize: 13, cursor: selected ? 'pointer' : 'not-allowed', transition: 'all .15s', whiteSpace: 'nowrap' }}
          >
            Go →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-shell">
      <div className="login-page">
        <div>
          <h1>College0</h1>
          <p className="subtitle">AI-Enabled College Program System</p>
        </div>

        {/* Manual login form */}
        <form onSubmit={handleManualLogin} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 8 }}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14 }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14 }}
          />
          <button
            type="submit"
            disabled={submitting}
            style={{ padding: '10px', borderRadius: 8, border: 'none', background: '#2E4A7A', color: 'white', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}
          >
            {submitting ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="apply-links">
          <a href="/apply">Apply for an account</a>
          {' · '}
          <a href="/apply/status/">Check application status</a>
        </div>

        {demoError && (
          <p className="error" style={{ textAlign: 'center', marginTop: 10 }}>{demoError}</p>
        )}

        <div className="quick-login-strip">
          <p className="label">— Quick Login (Demo) —</p>
          <div style={{ display: 'flex', gap: 12, flexDirection: 'column' }}>
            <QuickDropdown label="Registrar" color="#dc2626" users={QUICK_LOGINS.registrar} />
            <QuickDropdown label="Instructor" color="#16a34a" users={QUICK_LOGINS.instructor} />
            <QuickDropdown label="Student" color="#7c3aed" users={QUICK_LOGINS.student} />
          </div>
        </div>
      </div>
    </div>
  );
}