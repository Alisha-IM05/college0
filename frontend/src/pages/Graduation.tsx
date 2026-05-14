import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function Graduation(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'registrar';
  const applications = data.applications || [];

  return (
    <PageLayout username={username} role={role} activePage="graduation">
      <h2 style={{ marginBottom: '1.5rem' }}>Graduation Applications</h2>
      {applications.length > 0 ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Credits Earned</th>
                <th>Applied At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((app: any) => (
                <tr key={app.student_id}>
                  <td><strong>{app.username}</strong></td>
                  <td>{app.credits_earned} / 8</td>
                  <td>{app.applied_at}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '.5rem' }}>
                      <button className="btn-sm btn-approve" onClick={() => {
                        fetch(`/graduation/resolve/${app.student_id}`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                          body: 'decision=approved'
                        }).then(() => window.location.reload());
                      }}>✓ Approve</button>
                      <button className="btn-sm btn-reject" onClick={() => {
                        fetch(`/graduation/resolve/${app.student_id}`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                          body: 'decision=rejected'
                        }).then(() => window.location.reload());
                      }}>✗ Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card"><p className="muted">No pending graduation applications.</p></div>
      )}
    </PageLayout>
  );
}