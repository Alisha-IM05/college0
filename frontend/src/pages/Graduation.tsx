import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function Graduation(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const applications = data.applications || [];

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Graduation Applications</h2>

        {applications.length > 0 ? (
          <div className="card">
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
                    <td>{app.username}</td>
                    <td>{app.credits_earned} / 8</td>
                    <td>{app.applied_at}</td>
                    <td>
                      <form method="POST" action={`/graduation/resolve/${app.student_id}`} style={{ display: 'flex', gap: '.5rem' }}>
                        <button type="submit" name="decision" value="approved" className="btn-sm btn-approve">✓ Approve</button>
                        <button type="submit" name="decision" value="rejected" className="btn-sm btn-reject">✗ Reject</button>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card">
            <p className="muted">No pending graduation applications.</p>
          </div>
        )}
      </div>
    </>
  );
}