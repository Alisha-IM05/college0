import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function ClassDetail(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'instructor';
  const course = data.course;
  const semester = data.semester;
  const enrolled = data.enrolled || [];
  const waitlist = data.waitlist || [];

  if (!course) {
    return (
      <>
        <Navbar username={username} />
        <div className="container"><p className="muted">Course not found.</p></div>
      </>
    );
  }

  const isGrading = semester?.current_period === 'grading';

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <a href="/instructor/courses" style={{ color: '#2E4A7A', fontSize: '14px' }}>← Back to My Courses</a>
        <h2 style={{ marginTop: '.5rem' }}>{course.course_name}</h2>
        <p className="muted">Time Slot: {course.time_slot} &nbsp;|&nbsp; Capacity: {course.capacity} &nbsp;|&nbsp; Enrolled: {course.enrolled_count}</p>

        {/* Enrolled students */}
        <div className="card" style={{ marginTop: '1.5rem', padding: 0 }}>
          <h3 style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #eee', margin: 0 }}>Enrolled Students</h3>
          {enrolled.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Grade</th>
                  {role === 'instructor' && isGrading && <th>Submit Grade</th>}
                  {role === 'instructor' && !isGrading && <th>Grading</th>}
                </tr>
              </thead>
              <tbody>
                {enrolled.map((s: any) => (
                  <tr key={s.id}>
                    <td>{s.username}</td>
                    <td>{s.letter_grade || '—'}</td>
                    {role === 'instructor' && isGrading && (
                      <td>
                        <form method="POST" action={`/courses/${course.id}/grade`} style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
                          <input type="hidden" name="student_id" value={s.id} />
                          <select name="letter_grade" style={{ width: 'auto', padding: '4px 8px' }} defaultValue={s.letter_grade || 'A'}>
                            {['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','F'].map(g => (
                              <option key={g} value={g}>{g}</option>
                            ))}
                          </select>
                          <button type="submit" className="btn-sm">Save</button>
                        </form>
                      </td>
                    )}
                    {role === 'instructor' && !isGrading && (
                      <td className="muted">Not grading period</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted" style={{ padding: '1rem 1.5rem' }}>No students enrolled yet.</p>
          )}
        </div>

        {/* Waitlist */}
        {role === 'instructor' && waitlist.length > 0 && (
          <div className="card" style={{ padding: 0 }}>
            <h3 style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #eee', margin: 0 }}>Waitlist</h3>
            <table>
              <thead>
                <tr><th>Position</th><th>Student</th><th>Action</th></tr>
              </thead>
              <tbody>
                {waitlist.map((s: any) => (
                  <tr key={s.id}>
                    <td>{s.position}</td>
                    <td>{s.username}</td>
                    <td style={{ display: 'flex', gap: '.5rem' }}>
                      <form method="POST" action={`/courses/${course.id}/admit`}>
                        <input type="hidden" name="student_id" value={s.id} />
                        <button type="submit" className="btn-sm btn-approve">Admit</button>
                      </form>
                      <form method="POST" action={`/courses/${course.id}/reject`}>
                        <input type="hidden" name="student_id" value={s.id} />
                        <button type="submit" className="btn-sm btn-reject">Reject</button>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}