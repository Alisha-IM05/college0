import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

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

  const periodMsg: Record<string, string> = {
    setup: '🔧 The semester is opening soon. Please wait for registration to open.',
    running: '📖 Classes are in session. Registration is closed.',
    grading: '✅ Grading period is active. Registration is closed.',
  };

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Course Registration</h2>

        {semester && (
          <p className="semester-banner" style={{ marginBottom: '1rem' }}>
            📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; Period: <strong>{semester.current_period.toUpperCase()}</strong>
          </p>
        )}

        {message && (
          <div className={message.toLowerCase().includes('conflict') ? 'error' : 'info'}>{message}</div>
        )}

        {/* Enrollment status warnings */}
        {semester?.current_period === 'registration' && role === 'student' && (
          <>
            {enrolledCount === 0 && <div className="warn-note">⚠️ You are not registered for any courses. You must register for at least 2 before registration closes.</div>}
            {enrolledCount === 1 && <div className="warn-note">⚠️ You are registered for 1 course. You need at least 1 more before registration closes.</div>}
            {enrolledCount >= 4 && <div className="warn-note">⚠️ You have reached the maximum of 4 courses.</div>}
            {enrolledCount >= 2 && enrolledCount < 4 && <div className="info">✅ You are registered for {enrolledCount} course(s). You can register for up to {4 - enrolledCount} more.</div>}
          </>
        )}

        {/* Available courses table */}
        {(semester?.current_period === 'registration' || specialRegistration) ? (
          <>
            {specialRegistration && semester?.current_period !== 'registration' && (
              <div className="info">🔄 One of your courses was cancelled. You have been given a special registration period to choose another course.</div>
            )}
            <div className="card" style={{ padding: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>Course</th>
                    <th>Time Slot</th>
                    <th>Instructor</th>
                    <th>Spots</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map((c: any) => {
                    const isEnrolled = enrolledIds.includes(c.id);
                    const isWaitlisted = waitlistedCourseIds.includes(c.id);
                    const spots = c.capacity - c.enrolled_count;
                    return (
                      <tr key={c.id}>
                        <td>{c.course_name}</td>
                        <td>{c.display_slot}</td>
                        <td>{c.instructor_name || 'TBA'}</td>
                        <td>{spots}</td>
                        <td>
                          {isEnrolled ? (
                            <span className="pill p-approved">✓ Enrolled</span>
                          ) : isWaitlisted ? (
                            <span className="pill p-pending">On Waitlist</span>
                          ) : spots <= 0 ? (
                            <form method="POST" action={`/courses/register/${c.id}`}>
                              <button type="submit" className="btn-sm" style={{ background: '#e67e22' }}>Join Waitlist</button>
                            </form>
                          ) : (
                            <form method="POST" action={`/courses/register/${c.id}`}>
                              <button type="submit" className="btn-sm">Register</button>
                            </form>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="warn-note">
            {periodMsg[semester?.current_period || ''] || '⚠️ Registration is not currently open.'}
          </div>
        )}

        {/* Waitlist */}
        {role === 'student' && waitlisted.length > 0 && (
          <>
            <h3 style={{ marginTop: '1.5rem' }}>Your Waitlist</h3>
            <div className="card" style={{ padding: 0 }}>
              <table>
                <thead>
                  <tr><th>Course</th><th>Time Slot</th><th>Position</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {waitlisted.map((w: any, i: number) => (
                    <tr key={i}>
                      <td>{w.course_name}</td>
                      <td>{w.time_slot}</td>
                      <td>{w.position}</td>
                      <td>
                        {w.status === 'admitted' ? '✅ Admitted' : w.status === 'denied' ? '❌ Denied' : '⏳ Pending'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Cancelled courses */}
        {role === 'student' && cancelledCourses.length > 0 && (
          <>
            <h3 style={{ marginTop: '1.5rem' }}>⚠️ Cancelled Courses</h3>
            <div className="card" style={{ padding: 0 }}>
              <table>
                <thead>
                  <tr><th>Course</th><th>Time Slot</th><th>Instructor</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {cancelledCourses.map((c: any, i: number) => (
                    <tr key={i}>
                      <td>{c.course_name}</td>
                      <td>{c.time_slot} {c.start_time}-{c.end_time}</td>
                      <td>{c.instructor_name || 'TBA'}</td>
                      <td style={{ color: '#dc2626', fontWeight: 'bold' }}>❌ Cancelled due to low enrollment</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Current schedule */}
        {role === 'student' && (
          <>
            <h3 style={{ marginTop: '1.5rem' }}>Your Current Schedule</h3>
            {enrolled.length > 0 ? (
              <div className="card" style={{ padding: 0 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Course</th><th>Time Slot</th><th>Instructor</th>
                      {semester?.current_period === 'registration' && <th>Action</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {enrolled.map((c: any, i: number) => (
                      <tr key={i}>
                        <td>{c.course_name}</td>
                        <td>{c.time_slot} {c.start_time}-{c.end_time}</td>
                        <td>{c.instructor_name || 'TBA'}</td>
                        {semester?.current_period === 'registration' && (
                          <td>
                            <form method="POST" action={`/courses/drop/${c.id}`}>
                              <button type="submit" className="btn-sm btn-reject">Drop</button>
                            </form>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">You are not currently enrolled in any courses.</p>
            )}
          </>
        )}
      </div>
    </>
  );
}