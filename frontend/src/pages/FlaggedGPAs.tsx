import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function FlaggedGPAs(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'registrar';
  const flags = data.flags || [];

  return (
    <PageLayout username={username} role={role} activePage="flagged_gpas">
      <h2 style={{ marginBottom: '1.5rem' }}>Flagged Course GPAs</h2>

      {flags.length > 0 ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Course</th>
                <th>Instructor</th>
                <th>Avg GPA</th>
                <th>Flagged At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((f: any, i: number) => (
                <tr key={i}>
                  <td><strong>{f.course_name}</strong></td>
                  <td>{f.instructor_name || '—'}</td>
                  <td>
                    <span style={{ color: '#b91c1c', fontWeight: 700 }}>
                      {f.avg_gpa ? Number(f.avg_gpa).toFixed(2) : '—'}
                    </span>
                  </td>
                  <td className="muted">{f.flagged_at}</td>
                  <td>
                    <form method="POST" action={`/flagged-gpas/resolve/${f.id}`} style={{ display: 'inline' }}>
                      <button type="submit" className="btn-sm btn-approve">Resolve</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card">
          <p className="muted" style={{ textAlign: 'center', padding: '2rem' }}>
            No flagged courses to review.
          </p>
        </div>
      )}
    </PageLayout>
  );
}