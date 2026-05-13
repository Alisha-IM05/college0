import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function InstructorCourses(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const courses = data.courses || [];

  const periodMsg: Record<string, string> = {
    grading: 'You can submit grades now.',
    running: 'Classes are in session. Manage your roster below.',
    registration: 'Registration is open. Students can enroll in your courses.',
    setup: 'Semester is in setup. Courses are being configured.',
  };

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>My Courses</h2>

        {semester && (
          <p className="semester-banner" style={{ marginBottom: '1.5rem' }}>
            📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; Period: <strong>{semester.current_period.toUpperCase()}</strong>
            &nbsp;|&nbsp; {periodMsg[semester.current_period] || ''}
          </p>
        )}

        {courses.length > 0 ? (
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Time Slot</th>
                  <th>Semester</th>
                  <th>Period</th>
                  <th>Enrolled</th>
                  <th>Waitlist</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {courses.map((c: any) => (
                  <tr key={c.id}>
                    <td>{c.course_name}</td>
                    <td>{c.time_slot}</td>
                    <td>{c.semester_name}</td>
                    <td><span className="pill p-pending">{c.current_period?.toUpperCase()}</span></td>
                    <td>{c.enrolled_count} / {c.capacity}</td>
                    <td>
                      {c.waitlist_count > 0
                        ? <span className="pill p-pending">{c.waitlist_count} waiting</span>
                        : <span className="muted">None</span>
                      }
                    </td>
                    <td>
                      <a className="btn btn-sm" href={`/courses/${c.id}`}>
                        {c.waitlist_count > 0 ? 'Manage Waitlist' : 'View Roster'}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card">
            <p className="muted">You have no courses assigned this semester.</p>
          </div>
        )}
      </div>
    </>
  );
}