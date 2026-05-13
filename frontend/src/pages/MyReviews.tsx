import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function MyReviews(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const courses = data.courses || [];
 
  return (
    <PageLayout username={username} role={role} activePage="reviews">
      <h2 style={{ marginBottom: '1.5rem' }}>Course Reviews</h2>
      {courses.length > 0 ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead><tr>
              <th>Course</th><th>Semester</th><th>Time Slot</th>
              {role === 'student' && <th>Status</th>}
              {role !== 'student' && <><th>Avg Rating</th><th>Reviews</th></>}
              <th>Action</th>
            </tr></thead>
            <tbody>
              {courses.map((c: any) => (
                <tr key={c.id}>
                  <td><strong>{c.course_name}</strong></td>
                  <td>{c.semester_name}</td>
                  <td>{c.time_slot || '—'}</td>
                  {role === 'student' && <td><span className={`pill ${c.review_id ? 'p-approved' : 'p-pending'}`}>{c.review_id ? '✓ Reviewed' : 'Not reviewed'}</span></td>}
                  {role !== 'student' && <><td>{c.avg_rating ? Number(c.avg_rating).toFixed(1) + ' ⭐' : '—'}</td><td>{c.review_count || 0}</td></>}
                  <td><a className="btn btn-sm" href={`/reviews/${c.id}`}>{role === 'student' ? (c.review_id ? 'View' : 'Write Review') : 'View'}</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="card"><p className="muted">No courses to review.</p></div>}
    </PageLayout>
  );
}