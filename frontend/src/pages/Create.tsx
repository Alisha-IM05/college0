import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

const TIMES = ['08:00','08:30','09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30',
               '13:00','13:30','14:00','14:30','15:00','15:30','16:00','16:30','17:00','17:30',
               '18:00','18:30','19:00','19:30'];
const END_TIMES = [...TIMES, '20:00'];

export function Create(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const semesters = data.semesters || [];
  const instructors = data.instructors || [];
  const currentCourses = data.current_courses || [];
  const message = data.message;

  const setupSemesters = semesters.filter((s: any) => s.current_period === 'setup');
  const isSetup = setupSemesters.length > 0;

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>{isSetup ? 'Create New Course' : semester?.current_period === 'registration' ? 'Available Courses' : 'Current Courses'}</h2>

        {message && <div className="info">{message}</div>}

        {isSetup ? (
          <>
            <p className="semester-banner" style={{ marginBottom: '1.5rem' }}>
              📅 <strong>{setupSemesters[0].name}</strong> &nbsp;|&nbsp; Current Period: <strong>SETUP</strong>
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', alignItems: 'start' }}>
              <div className="card">
                <h3>New Course</h3>
                <form method="POST" action="/courses/create">
                  <label>Course ID (e.g. CSC32200)</label>
                  <input type="text" name="course_id" required />
                  <label>Course Name</label>
                  <input type="text" name="name" required />
                  <label>Instructor</label>
                  <select name="instructor_id" required>
                    <option value="">— Select instructor —</option>
                    {instructors.map((i: any) => (
                      <option key={i.id} value={i.id}>{i.username}</option>
                    ))}
                  </select>
                  <label>Days</label>
                  <select name="day_of_week" required>
                    <option value="1">Monday / Wednesday</option>
                    <option value="3">Tuesday / Thursday</option>
                    <option value="5">Friday</option>
                    <option value="4">Wednesday / Friday</option>
                  </select>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '.75rem' }}>
                    <div>
                      <label>Start Time</label>
                      <select name="start_time" required>
                        {TIMES.map(t => <option key={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label>End Time</label>
                      <select name="end_time" required>
                        {END_TIMES.map(t => <option key={t}>{t}</option>)}
                      </select>
                    </div>
                  </div>
                  <label>Capacity</label>
                  <input type="number" name="capacity" required />
                  <input type="hidden" name="semester_id" value={setupSemesters[0].id} />
                  <button type="submit" className="block">Create Course</button>
                </form>
              </div>

              <div>
                <h3>Courses This Semester</h3>
                {currentCourses.length > 0 ? (
                  <div className="card" style={{ padding: 0 }}>
                    <table>
                      <thead>
                        <tr><th>Course</th><th>Instructor</th><th>Enrolled</th><th>Action</th></tr>
                      </thead>
                      <tbody>
                        {currentCourses.map((c: any) => (
                          <tr key={c.id}>
                            <td>{c.course_name}</td>
                            <td>{c.instructor_name}</td>
                            <td>{c.enrolled_count} / {c.capacity}</td>
                            <td>
                              <form method="POST" action={`/courses/delete/${c.id}`}>
                                <button type="submit" className="btn-sm btn-reject">Delete</button>
                              </form>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="card"><p className="muted">No courses created yet.</p></div>
                )}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="warn-note">Course creation is only available during the setup period.</div>
            {semester && <p>Current period: <strong>{semester.current_period.toUpperCase()}</strong></p>}
            {currentCourses.length > 0 && (
              <div className="card" style={{ padding: 0, marginTop: '1rem' }}>
                <table>
                  <thead>
                    <tr><th>Course</th><th>Instructor</th><th>Schedule</th><th>Enrolled</th></tr>
                  </thead>
                  <tbody>
                    {currentCourses.map((c: any) => (
                      <tr key={c.id}>
                        <td>{c.course_name}</td>
                        <td>{c.instructor_name}</td>
                        <td>{c.time_slot}</td>
                        <td>{c.enrolled_count} / {c.capacity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}