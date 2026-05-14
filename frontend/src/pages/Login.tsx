import React, { useEffect, useState } from 'react';
import { SignedIn, SignedOut, SignIn, useAuth } from '@clerk/clerk-react';

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
  const data = getPageData();
  const [demoError, setDemoError] = useState<string | null>(data.error ?? null);
  const [submitting, setSubmitting] = useState(false);

  async function doDemoLogin(username: string, password: string) {
    setSubmitting(true);
    setDemoError(null);
    const resp = await postForm('/login', { username, password });
    setSubmitting(false);
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
    } else {
      setDemoError(resp.error || 'Invalid username or password.');
    }
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
            style={{
              flex: 1, minWidth: 160,
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid #e2e8f0',
              fontSize: 13,
              background: 'white',
              color: selected ? '#1e293b' : '#94a3b8',
              outline: 'none',
              cursor: 'pointer',
            }}
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
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: 'none',
              background: selected ? color : '#e2e8f0',
              color: selected ? 'white' : '#94a3b8',
              fontWeight: 700,
              fontSize: 13,
              cursor: selected ? 'pointer' : 'not-allowed',
              transition: 'all .15s',
              whiteSpace: 'nowrap',
            }}
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

        <SignedOut>
          <div className="clerk-mount">
            <SignIn
              routing="hash"
              signUpUrl="/apply"
              forceRedirectUrl="/"
            />
          </div>
          <div className="apply-links">
            <a href="/apply">Apply for an account</a>
            {' · '}
            <a href="/apply/status/">Check application status</a>
          </div>
        </SignedOut>

        <SignedIn>
          <div className="bridge-status">
            <ClerkBridge />
          </div>
        </SignedIn>

        <div className="quick-login-strip">
          <p className="label">— Quick Login (Demo) —</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <QuickDropdown label="Registrar" color="#dc2626" users={QUICK_LOGINS.registrar} />
            <QuickDropdown label="Instructor" color="#16a34a" users={QUICK_LOGINS.instructor} />
            <QuickDropdown label="Student" color="#7c3aed" users={QUICK_LOGINS.student} />
          </div>
          {demoError && (
            <p className="error" style={{ textAlign: 'center', marginTop: 10 }}>{demoError}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function ClerkBridge(): React.ReactElement {
  const { getToken, signOut } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [retryRedirect, setRetryRedirect] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const params = new URLSearchParams(window.location.search);
      if (params.get('signed_out') === '1') {
        try {
          await signOut();
        } finally {
          if (!cancelled) window.location.replace('/');
        }
        return;
      }
      try {
        const token = await getToken();
        const resp = await postForm('/auth/clerk-login', {}, { bearerToken: token });
        if (cancelled) return;
        if (resp.ok && resp.redirect) {
          navigate(resp.redirect);
          return;
        }
        setError(resp.error || 'Could not sign you in.');
        if (resp.redirect) setRetryRedirect(resp.redirect);
      } catch (err) {
        if (!cancelled) setError((err as Error).message || 'Network error.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [getToken, signOut]);

  return (
    <>
      <p className="muted">
        Signed in via Clerk
        {' '}·{' '}
        <a
          href="#"
          onClick={async (e) => {
            e.preventDefault();
            await signOut();
            window.location.reload();
          }}
        >
          Use a different account
        </a>
      </p>
      {error ? (
        <>
          <div className="error">{error}</div>
          {retryRedirect && (
            <a className="cta" href={retryRedirect}>Continue</a>
          )}
        </>
      ) : (
        <p className="muted">Signing you in…</p>
      )}
    </>
  );
}