import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function InstructorCourses(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const courses = data.courses || [];
 
  return (
    <PageLayout username={username} role="instructor" activePage="instructor_courses">
      <h2 style={{ marginBottom: '1.5rem' }}>My Courses</h2>
      {semester && (
        <div className="semester-banner" style={{ marginBottom: '1.5rem', display: 'inline-flex' }}>
          📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; <strong>{semester.current_period.toUpperCase()}</strong>
        </div>
      )}
      {courses.length > 0 ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead><tr><th>Course</th><th>Time Slot</th><th>Semester</th><th>Enrolled</th><th>Waitlist</th><th>Action</th></tr></thead>
            <tbody>
              {courses.map((c: any) => (
                <tr key={c.id}>
                  <td><strong>{c.course_name}</strong></td>
                  <td>{c.time_slot}</td>
                  <td>{c.semester_name}</td>
                  <td>{c.enrolled_count} / {c.capacity}</td>
                  <td>{c.waitlist_count > 0 ? <span className="pill p-pending">{c.waitlist_count} waiting</span> : <span className="muted">None</span>}</td>
                  <td><a className="btn btn-sm" href={`/courses/${c.id}`}>{c.waitlist_count > 0 ? 'Manage' : 'View'}</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="card"><p className="muted">No courses assigned this semester.</p></div>}
    </PageLayout>
  );
}