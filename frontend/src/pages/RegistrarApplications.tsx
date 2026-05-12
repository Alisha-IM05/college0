import React, { useState } from 'react';

import { getPageData, ApplicationRow, IssuedCredentials } from '../lib/data';
import { postForm } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { Pill } from '../components/Pill';

export function RegistrarApplications(): React.ReactElement {
  const data = getPageData();
  const [pending, setPending] = useState<ApplicationRow[]>(data.pending || []);
  const [reviewed, setReviewed] = useState<ApplicationRow[]>(data.reviewed || []);
  const [issued, setIssued] = useState<IssuedCredentials | null>(data.issued ?? null);
  const [busy, setBusy] = useState<number | null>(null);

  async function act(applicationId: number, action: 'approve' | 'reject') {
    setBusy(applicationId);
    const resp = await postForm(`/registrar/applications/${applicationId}/${action}`, {});
    setBusy(null);
    if (resp.data) {
      if ((resp.data as { issued?: IssuedCredentials }).issued !== undefined) {
        setIssued((resp.data as { issued: IssuedCredentials }).issued);
      }
      const d = resp.data as { pending?: ApplicationRow[]; reviewed?: ApplicationRow[] };
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
                    <td><Pill status={a.status} /></td>
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
  return (
    <div className="card" style={{ border: '2px solid #27ae60' }}>
      <h2>New account issued</h2>
      <p className="muted">
        Share these credentials with the new {issued.role} ({issued.email}). They sign
        in at the home page with their Clerk account, then enter the temporary password
        below on the change-password screen.
      </p>
      <div className="creds">
        <div><span className="label">User ID:</span> {issued.user_id}</div>
        <div><span className="label">Username:</span> {issued.username}</div>
        <div><span className="label">Temporary password:</span> {issued.temp_password}</div>
      </div>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
