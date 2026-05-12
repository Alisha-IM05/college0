import React, { useEffect, useState } from 'react';
import { SignedIn, SignedOut, SignIn, useAuth } from '@clerk/clerk-react';

import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

const QUICK_LOGINS = [
  { label: 'Registrar', username: 'registrar1', password: 'password123', cls: 'btn-registrar' },
  { label: 'Instructor', username: 'instructor1', password: 'password123', cls: 'btn-instructor' },
  { label: 'Student 1', username: 'student1', password: 'password123', cls: 'btn-student1' },
  { label: 'Student 2', username: 'student2', password: 'password123', cls: 'btn-student2' },
];

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
            <a href="/apply/status">Check application status</a>
          </div>
        </SignedOut>

        <SignedIn>
          <div className="bridge-status">
            <ClerkBridge />
          </div>
        </SignedIn>

        <div className="quick-login-strip">
          <p className="label">— Quick Login (Demo) —</p>
          <div className="quick-btns">
            {QUICK_LOGINS.map((q) => (
              <button
                key={q.username}
                type="button"
                className={q.cls}
                disabled={submitting}
                onClick={() => void doDemoLogin(q.username, q.password)}
              >
                {q.label}
              </button>
            ))}
          </div>
          {demoError && (
            <p className="error" style={{ textAlign: 'center' }}>{demoError}</p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Mounted once the visitor is signed in via Clerk. Exchanges the Clerk JWT
 * for a Flask session via POST /auth/clerk-login, then sends the user to
 * /dashboard (or /change-password when UC-11 still applies).
 */
function ClerkBridge(): React.ReactElement {
  const { getToken, signOut } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [retryRedirect, setRetryRedirect] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const params = new URLSearchParams(window.location.search);
      if (params.get('signed_out') === '1') {
        // Came from Flask /logout while a Clerk session was still active.
        // Sign out of Clerk too, then reload `/` cleanly so the SignIn
        // widget can take over instead of us bridging the JWT right back
        // into a fresh Flask session.
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
