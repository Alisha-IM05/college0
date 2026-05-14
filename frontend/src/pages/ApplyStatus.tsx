import React, { useEffect, useState } from 'react';

import { getPageData, ApplicationRow } from '../lib/data';
import { Pill } from '../components/Pill';

function tokenFromLocation(): string {
  const q = new URLSearchParams(window.location.search);
  return (q.get('token') || '').trim();
}

export function ApplyStatus(): React.ReactElement {
  const data = getPageData();
  const initialToken = (data.token as string | undefined) || tokenFromLocation();
  const serverLoggedIn = data.logged_in === true;
  const [applications, setApplications] = useState<ApplicationRow[]>(data.applications || []);
  const [missingToken, setMissingToken] = useState<boolean>(
    data.missing_token === true || (!initialToken && !serverLoggedIn),
  );
  const [loading, setLoading] = useState(() => Boolean(initialToken || serverLoggedIn));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = initialToken || tokenFromLocation();
    const loggedIn = serverLoggedIn;

    if (!token && !loggedIn) {
      setMissingToken(true);
      setApplications([]);
      setLoading(false);
      return;
    }

    setMissingToken(false);
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const url = token
          ? `/apply/status.json?token=${encodeURIComponent(token)}`
          : '/apply/status.json';
        const resp = await fetch(url, { credentials: 'same-origin' });
        if (cancelled) return;
        if (resp.ok) {
          const j = (await resp.json()) as {
            applications: ApplicationRow[];
            missing_token?: boolean;
            logged_in?: boolean;
          };
          setApplications(j.applications || []);
          setMissingToken(!!j.missing_token);
        } else {
          setError(`Could not load status (${resp.status}).`);
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message || 'Network error.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialToken, serverLoggedIn]);

  const subtitle = serverLoggedIn
    ? 'Showing applications associated with your account email. You can also open your saved private status link (includes ?token= in the URL).'
    : 'Use the private status link from your browser after you applied (includes ?token= in the address bar), or sign in to see applications for your email.';

  return (
    <div className="wrap-wide">
      <div className="card card-narrow">
        <h1>Application Status</h1>
        <p className="subtitle">{subtitle}</p>

        {error && <div className="error">{error}</div>}
        {missingToken ? (
          <p className="muted">
            No status token and you are not signed in. Use the private link from your browser after
            you submitted your application, or{' '}
            <a href="/login">log in</a> to view applications tied to your account.
          </p>
        ) : loading ? (
          <p className="muted">Loading…</p>
        ) : applications.length === 0 ? (
          <p className="muted">No applications found. The link may be invalid, or there are none for your account.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Submitted</th>
                <th>Role</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {applications.flatMap((a) => {
                const rows: React.ReactNode[] = [
                  <tr key={`row-${a.id}`}>
                    <td>{a.submitted_at}</td>
                    <td>{capitalize(a.role_applied)}</td>
                    <td>{a.email}</td>
                    <td>
                      <Pill status={a.status} />
                    </td>
                  </tr>,
                ];
                const showCreds =
                  (a.status === 'pending' || a.status === 'approved') && Boolean(a.issued_username);
                if (showCreds) {
                  rows.push(
                    <tr key={`creds-${a.id}`}>
                      <td colSpan={4}>
                        {a.issued_temp_password ? (
                          <>
                            <div className="creds">
                              <div>
                                <span className="label">Your username:</span> {a.issued_username}
                              </div>
                              <div>
                                <span className="label">Temporary password:</span>{' '}
                                {a.issued_temp_password}
                              </div>
                            </div>
                            <div className="note">
                              {a.status === 'pending' ? (
                                <>
                                  Save this page or bookmark the URL — your login details are not
                                  sent by email. After the registrar approves you, full portal access
                                  is enabled; you keep the same username and password until you
                                  change it.
                                </>
                              ) : (
                                <>
                                  Your application was approved. Sign in at{' '}
                                  <a href="/login">Log in</a> with the username above; use your
                                  temporary password on the change-password screen if you have not
                                  set a new password yet.
                                </>
                              )}
                            </div>
                            <a className="cta" href="/login">
                              Go to login
                            </a>
                          </>
                        ) : (
                          <div className="note">
                            You have already changed your password. Sign in at{' '}
                            <a href="/login">Log in</a> with username <strong>{a.issued_username}</strong>.
                          </div>
                        )}
                      </td>
                    </tr>,
                  );
                }
                if (a.status === 'rejected') {
                  rows.push(
                    <tr key={`rej-${a.id}`}>
                      <td colSpan={4} className="muted">
                        Your application was not approved by the registrar. Reviewed on {a.reviewed_at}.
                      </td>
                    </tr>,
                  );
                }
                return rows;
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="links">
        <a href="/">Home</a> | <a href="/apply">Apply</a> | <a href="/login">Log in</a>
      </div>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
