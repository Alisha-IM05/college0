import React, { useState } from 'react';

import { getPageData, ApplicationRow, IssuedCredentials } from '../lib/data';
import { postForm } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { Pill } from '../components/Pill';

export function RegistrarApplications(): React.ReactElement {
  const data = getPageData();
  const mailOk = data.mail_configured === true;
  const [pending, setPending] = useState<ApplicationRow[]>(data.pending || []);
  const [reviewed, setReviewed] = useState<ApplicationRow[]>(data.reviewed || []);
  const [issued, setIssued] = useState<IssuedCredentials | null>(data.issued ?? null);
  const [busy, setBusy] = useState<number | null>(null);

  async function act(applicationId: number, action: 'approve' | 'reject') {
    setBusy(applicationId);
    const resp = await postForm(`/registrar/applications/${applicationId}/${action}`, {});
    setBusy(null);
    if (resp.data) {
      const d = resp.data as { issued?: IssuedCredentials; pending?: ApplicationRow[]; reviewed?: ApplicationRow[] };
      if (d.issued !== undefined) {
        setIssued(d.issued);
      }
      if (d.pending) setPending(d.pending);
      if (d.reviewed) setReviewed(d.reviewed);
    } else if (!resp.ok && resp.error) {
      setIssued({ error: resp.error });
    }
  }

  return (
    <>
      <Navbar
        username={data.username}
        extras={
          <>
            <a href="/dashboard">Dashboard</a>
            <a href="/registrar/users">Users</a>
          </>
        }
      />
      <div className="container">
        {!mailOk && (
          <div className="banner-info" style={{ marginBottom: 16 }}>
            Optional: configure <code>MAIL_SERVER</code> and <code>MAIL_FROM</code> if you want outbound
            email (for example rejection notices). Submit and approve work without it; applicants see
            their username and temporary password on the application status page, not by email.
          </div>
        )}

        {issued && <IssuedBanner issued={issued} />}

        <div className="card">
          <h2>Pending applications ({pending.length})</h2>
          {pending.length === 0 ? (
            <p className="muted">No pending applications.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Submitted</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((a) => (
                  <tr key={a.id}>
                    <td>{a.submitted_at}</td>
                    <td>{a.name}</td>
                    <td>{a.email}</td>
                    <td>{capitalize(a.role_applied)}</td>
                    <td>
                      <button
                        className="btn btn-sm btn-approve"
                        disabled={busy === a.id}
                        onClick={() => void act(a.id, 'approve')}
                        style={{ marginRight: 6 }}
                      >
                        Approve
                      </button>
                      <button
                        className="btn btn-sm btn-reject"
                        disabled={busy === a.id}
                        onClick={() => void act(a.id, 'reject')}
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <h2>Reviewed applications ({reviewed.length})</h2>
          {reviewed.length === 0 ? (
            <p className="muted">No reviewed applications yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Reviewed</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {reviewed.map((a) => (
                  <tr key={a.id}>
                    <td>{a.reviewed_at}</td>
                    <td>{a.name}</td>
                    <td>{a.email}</td>
                    <td>{capitalize(a.role_applied)}</td>
                    <td>
                      <Pill status={a.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}

function IssuedBanner({ issued }: { issued: IssuedCredentials }): React.ReactElement {
  if (issued.error) {
    return <div className="banner-error">{issued.error}</div>;
  }
  if (issued.rejected) {
    return <div className="banner-info">{issued.message || 'Application rejected.'}</div>;
  }
  if (!issued.username) return <></>;
  if (issued.account_activated) {
    return (
      <div className="card" style={{ border: '2px solid #27ae60', marginBottom: 16 }}>
        <h2>Application approved</h2>
        <p className="muted">
          Full portal access is now enabled for <strong>{issued.email}</strong>. They keep the same
          username and temporary password they received when they applied (shown on their application
          status page). They should sign in and set a new password if they have not already.
        </p>
        <details>
          <summary className="muted" style={{ cursor: 'pointer' }}>
            Registrar copy (support only)
          </summary>
          <div className="creds" style={{ marginTop: 8 }}>
            <div>
              <span className="label">User ID:</span> {issued.user_id}
            </div>
            <div>
              <span className="label">Username:</span> {issued.username}
            </div>
          </div>
        </details>
      </div>
    );
  }
  return (
    <div className="card" style={{ border: '2px solid #27ae60', marginBottom: 16 }}>
      <h2>Application updated</h2>
      <p className="muted">Summary below is for registrar support only.</p>
      <details>
        <summary className="muted" style={{ cursor: 'pointer' }}>
          Registrar copy (support)
        </summary>
        <div className="creds" style={{ marginTop: 8 }}>
          <div>
            <span className="label">User ID:</span> {issued.user_id}
          </div>
          <div>
            <span className="label">Username:</span> {issued.username}
          </div>
          {issued.temp_password != null && issued.temp_password !== '' && (
            <div>
              <span className="label">Temporary password:</span> {issued.temp_password}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
