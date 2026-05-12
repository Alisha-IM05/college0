import React, { useEffect, useState } from 'react';
import { SignedIn, SignedOut, SignIn, useAuth } from '@clerk/clerk-react';

import { getPageData, ApplicationRow } from '../lib/data';
import { Pill } from '../components/Pill';

export function ApplyStatus(): React.ReactElement {
  const data = getPageData();
  return (
    <div className="wrap-wide">
      <div className="card card-narrow">
        <h1>Application Status</h1>
        <p className="subtitle">
          Sign in with Clerk to see the status of applications you've submitted.
        </p>

        <SignedOut>
          <p className="muted">
            You're not signed in. Use the widget below to sign in with the Clerk
            account you used when applying.
          </p>
          <div style={{ marginTop: 12 }}>
            <SignIn
              routing="hash"
              signUpUrl="/apply"
              forceRedirectUrl="/apply/status"
            />
          </div>
        </SignedOut>

        <SignedIn>
          <StatusBody serverApplications={data.applications || []}
                      serverSignedIn={data.signed_in === true} />
        </SignedIn>
      </div>

      <div className="links">
        <a href="/apply">Apply</a> | <a href="/">Log in</a>
      </div>
    </div>
  );
}

interface StatusBodyProps {
  serverApplications: ApplicationRow[];
  serverSignedIn: boolean;
}

function StatusBody({ serverApplications, serverSignedIn }: StatusBodyProps): React.ReactElement {
  const { getToken, signOut } = useAuth();
  const [applications, setApplications] = useState<ApplicationRow[]>(serverApplications);
  const [loading, setLoading] = useState(!serverSignedIn);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If server didn't recognize us as signed in (no Bearer token on the GET),
    // refetch with a token so we can pick up our applications.
    if (serverSignedIn) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        const resp = await fetch('/apply/status.json', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: 'same-origin',
        });
        if (cancelled) return;
        if (resp.ok) {
          const j = (await resp.json()) as { applications: ApplicationRow[] };
          setApplications(j.applications || []);
        } else {
          setError(`Could not load applications (${resp.status}).`);
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
  }, [serverSignedIn, getToken]);

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
          Sign out
        </a>
      </p>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : applications.length === 0 ? (
        <>
          <p className="muted">You haven't submitted any applications yet.</p>
          <a className="cta" href="/apply">Submit an application</a>
        </>
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
                  <td><Pill status={a.status} /></td>
                </tr>,
              ];
              if (a.status === 'approved' && a.issued_username) {
                rows.push(
                  <tr key={`creds-${a.id}`}>
                    <td colSpan={4}>
                      {a.issued_temp_password ? (
                        <>
                          <div className="creds">
                            <div><span className="label">Your username:</span> {a.issued_username}</div>
                            <div><span className="label">Temporary password:</span> {a.issued_temp_password}</div>
                          </div>
                          <div className="note">
                            Save these credentials. Sign in at the home page with the
                            same Clerk account you used to apply — you'll then be
                            asked to enter this temporary password and choose a new one.
                          </div>
                          <a className="cta" href="/">Go to login</a>
                        </>
                      ) : (
                        <div className="note">
                          You've already logged in and changed your password.
                          Sign in at the home page with your Clerk account to access
                          <strong> {a.issued_username}</strong>.<br />
                          <a className="cta" href="/">Go to login</a>
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
                      Your application was not approved by the registrar.
                      Reviewed on {a.reviewed_at}.
                    </td>
                  </tr>,
                );
              }
              return rows;
            })}
          </tbody>
        </table>
      )}
    </>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
