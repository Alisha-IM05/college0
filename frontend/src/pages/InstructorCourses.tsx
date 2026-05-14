import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function InstructorCourses(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const allCourses = data.courses || [];
  const isGrading = semester?.current_period === 'grading';

  const activeCourses = allCourses.filter((c: any) => c.status === 'active');
  const cancelledCourses = allCourses.filter((c: any) => c.status === 'cancelled');

  const CourseTable = ({ courses, cancelled }: { courses: any[], cancelled?: boolean }) => (
    <div className="card" style={{ padding: 0, marginBottom: cancelled ? 0 : '1.5rem' }}>
      {cancelled && (
        <div style={{ padding: '12px 20px', background: '#fef2f2', borderBottom: '1px solid #fecaca' }}>
          <strong style={{ color: '#dc2626' }}>⚠ Cancelled Courses</strong>
          <span style={{ color: '#dc2626', fontSize: 13, marginLeft: 8 }}>These courses were cancelled due to low enrollment</span>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Course</th>
            <th>Time Slot</th>
            <th>Semester</th>
            <th>Enrolled</th>
            {!cancelled && (isGrading
              ? <th>Graded</th>
              : <th>Waitlist</th>
            )}
            {!cancelled && <th>Action</th>}
          </tr>
        </thead>
        <tbody>
          {courses.map((c: any) => (
            <tr key={c.id} style={cancelled ? { opacity: 0.7 } : {}}>
              <td>
                <strong style={cancelled ? { color: '#dc2626', textDecoration: 'line-through' } : {}}>
                  {c.course_name}
                </strong>
                {cancelled && <span style={{ marginLeft: 8, fontSize: 12, color: '#dc2626', fontWeight: 600 }}>CANCELLED</span>}
              </td>
              <td>{c.time_slot}</td>
              <td>{c.semester_name}</td>
              <td>{c.enrolled_count} / {c.capacity}</td>
              {!cancelled && (isGrading ? (
                <td>
                  <span style={{
                    padding: '3px 10px', borderRadius: 99, fontSize: 12, fontWeight: 600,
                    background: c.graded_count >= c.enrolled_count ? '#dcfce7' : '#fef9c3',
                    color: c.graded_count >= c.enrolled_count ? '#166534' : '#854d0e'
                  }}>
                    {c.graded_count} / {c.enrolled_count} graded
                  </span>
                </td>
              ) : (
                <td>{c.waitlist_count > 0
                  ? <span className="pill p-pending">{c.waitlist_count} waiting</span>
                  : <span className="muted">None</span>}
                </td>
              ))}
              {!cancelled && (
                <td><a className="btn btn-sm" href={`/courses/${c.id}`}>{c.waitlist_count > 0 ? 'Manage' : 'View'}</a></td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <PageLayout username={username} role="instructor" activePage="instructor_courses">
      <h2 style={{ marginBottom: '1.5rem' }}>My Courses</h2>
      {semester && (
        <div className="semester-banner" style={{ marginBottom: '1.5rem', display: 'inline-flex' }}>
          📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; <strong>{semester.current_period.toUpperCase()}</strong>
        </div>
      )}
      {activeCourses.length > 0
        ? <CourseTable courses={activeCourses} />
        : <div className="card"><p className="muted">No active courses this semester.</p></div>
      }
      {cancelledCourses.length > 0 && <CourseTable courses={cancelledCourses} cancelled />}
    </PageLayout>
  );
}