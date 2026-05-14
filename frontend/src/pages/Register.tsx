import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function Register(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const semester = data.semester;
  const courses = data.courses || [];
  const enrolled = data.enrolled || [];
  const waitlisted = data.waitlisted || [];
  const cancelledCourses = data.cancelled_courses || [];
  const specialRegistration = data.special_registration || false;
  const message = data.message;
  const enrolledIds = enrolled.map((c: any) => c.id);
  const waitlistedCourseIds = waitlisted.map((w: any) => w.course_id);
  const enrolledCount = enrolled.length;
 
  return (
    <PageLayout username={username} role={role} activePage="register">
      <h2 style={{ marginBottom: '1.5rem' }}>Course Registration</h2>
      {semester && <div className="semester-banner" style={{ marginBottom: '1rem', display: 'inline-flex' }}>📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; <strong>{semester.current_period.toUpperCase()}</strong></div>}
      {message && <div className={message.toLowerCase().includes('conflict') ? 'error' : 'info'} style={{ marginBottom: '1rem' }}>{message}</div>}
      {semester?.current_period === 'registration' && role === 'student' && (
        <div className={enrolledCount < 2 ? 'warn-note' : 'info'} style={{ marginBottom: '1rem' }}>
          {enrolledCount === 0 && '⚠️ You are not registered for any courses. Register for at least 2.'}
          {enrolledCount === 1 && '⚠️ You need at least 1 more course.'}
          {enrolledCount >= 4 && '⚠️ You have reached the maximum of 4 courses.'}
          {enrolledCount >= 2 && enrolledCount < 4 && `✅ Registered for ${enrolledCount} course(s). Up to ${4 - enrolledCount} more available.`}
        </div>
      )}
 
      {(semester?.current_period === 'registration' || (semester?.current_period === 'special_registration' && specialRegistration)) && (
        <div className="card" style={{ padding: 0, marginBottom: '1rem' }}>
          <table>
            <thead><tr><th>Course</th><th>Time Slot</th><th>Instructor</th><th>Spots</th><th>Action</th></tr></thead>
            <tbody>
              {courses.map((c: any) => {
                const isEnrolled = enrolledIds.includes(c.id);
                const isWaitlisted = waitlistedCourseIds.includes(c.id);
                const spots = c.capacity - c.enrolled_count;
                return (
                  <tr key={c.id}>
                    <td><strong>{c.course_name}</strong></td>
                    <td>{c.display_slot}</td>
                    <td>{c.instructor_name || 'TBA'}</td>
                    <td>{spots}</td>
                    <td>
                      {isEnrolled ? <span className="pill p-approved">✓ Enrolled</span>
                        : isWaitlisted ? <span className="pill p-pending">Waitlisted</span>
                        : spots <= 0 ? <form method="POST" action={`/courses/register/${c.id}`}><button className="btn-sm" style={{ background: '#e67e22' }} type="submit">Join Waitlist</button></form>
                        : <form method="POST" action={`/courses/register/${c.id}`}><button className="btn-sm" type="submit">Register</button></form>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
 
      {semester?.current_period !== 'registration' && !specialRegistration && (
        <div className="warn-note">
          {semester?.current_period === 'setup' ? '🔧 Semester is opening soon.' : semester?.current_period === 'running' ? '📖 Classes are in session. Registration is closed.' : semester?.current_period === 'grading' ? '✅ Grading period. Registration is closed.' : '⚠️ Registration is not currently open.'}
        </div>
      )}
 
      {role === 'student' && waitlisted.length > 0 && (
        <>
          <h3 style={{ margin: '1.5rem 0 1rem' }}>Your Waitlist</h3>
          <div className="card" style={{ padding: 0, marginBottom: '1rem' }}>
            <table>
              <thead><tr><th>Course</th><th>Time Slot</th><th>Position</th><th>Status</th></tr></thead>
              <tbody>{waitlisted.map((w: any, i: number) => (
                <tr key={i}><td>{w.course_name}</td><td>{w.time_slot}</td><td>{w.position}</td>
                  <td>{w.status === 'admitted' ? '✅ Admitted' : w.status === 'denied' ? '❌ Denied' : '⏳ Pending'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
 
      {role === 'student' && (
        <>
          <h3 style={{ margin: '1.5rem 0 1rem' }}>Your Current Schedule</h3>
          {enrolled.length > 0 ? (
            <div className="card" style={{ padding: 0 }}>
              <table>
                <thead><tr><th>Course</th><th>Time Slot</th><th>Instructor</th>{semester?.current_period === 'registration' && <th>Action</th>}</tr></thead>
                <tbody>{enrolled.map((c: any, i: number) => (
                  <tr key={i}>
                    <td><strong>{c.course_name}</strong></td>
                    <td>{c.time_slot} {c.start_time}-{c.end_time}</td>
                    <td>{c.instructor_name || 'TBA'}</td>
                    {semester?.current_period === 'registration' && <td><form method="POST" action={`/courses/drop/${c.id}`}><button className="btn-sm btn-reject" type="submit">Drop</button></form></td>}
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <p className="muted">Not currently enrolled in any courses.</p>}
        </>
      )}
    </PageLayout>
  );
}