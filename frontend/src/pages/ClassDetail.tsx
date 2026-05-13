import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function ClassDetail(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'instructor';
  const course = data.course;
  const semester = data.semester;
  const enrolled = data.enrolled || [];
  const waitlist = data.waitlist || [];
  const isGrading = semester?.current_period === 'grading';
 
  return (
    <PageLayout username={username} role={role} activePage="instructor_courses">
      <a href="/instructor/courses" style={{ color: '#2E4A7A', fontSize: 14, display: 'inline-block', marginBottom: '1rem' }}>← Back to My Courses</a>
      <h2 style={{ marginBottom: '.25rem' }}>{course?.course_name || 'Course'}</h2>
      <p className="muted" style={{ marginBottom: '1.5rem' }}>Time Slot: {course?.time_slot} &nbsp;|&nbsp; Capacity: {course?.capacity} &nbsp;|&nbsp; Enrolled: {course?.enrolled_count}</p>
 
      <div className="card" style={{ marginBottom: '1rem', padding: 0 }}>
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #dbe2f0' }}><h3 style={{ margin: 0 }}>Enrolled Students</h3></div>
        {enrolled.length > 0 ? (
          <table>
            <thead><tr><th>Student</th><th>Grade</th>{role === 'instructor' && isGrading && <th>Submit Grade</th>}{role === 'instructor' && !isGrading && <th>Grading</th>}</tr></thead>
            <tbody>
              {enrolled.map((s: any) => (
                <tr key={s.id}>
                  <td><strong>{s.username}</strong></td>
                  <td>{s.letter_grade || '—'}</td>
                  {role === 'instructor' && isGrading && (
                    <td>
                      <form method="POST" action={`/courses/${course.id}/grade`} style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
                        <input type="hidden" name="student_id" value={s.id} />
                        <select name="letter_grade" style={{ width: 'auto', padding: '4px 8px' }} defaultValue={s.letter_grade || 'A'}>
                          {['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','F'].map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                        <button type="submit" className="btn-sm">Save</button>
                      </form>
                    </td>
                  )}
                  {role === 'instructor' && !isGrading && <td className="muted">Not grading period</td>}
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted" style={{ padding: '1.5rem' }}>No students enrolled yet.</p>}
      </div>
 
      {role === 'instructor' && waitlist.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid #dbe2f0' }}><h3 style={{ margin: 0 }}>Waitlist</h3></div>
          <table>
            <thead><tr><th>Position</th><th>Student</th><th>Action</th></tr></thead>
            <tbody>
              {waitlist.map((s: any) => (
                <tr key={s.id}>
                  <td>{s.position}</td>
                  <td><strong>{s.username}</strong></td>
                  <td style={{ display: 'flex', gap: '.5rem' }}>
                    <form method="POST" action={`/courses/${course.id}/admit`}><input type="hidden" name="student_id" value={s.id} /><button type="submit" className="btn-sm btn-approve">Admit</button></form>
                    <form method="POST" action={`/courses/${course.id}/reject`}><input type="hidden" name="student_id" value={s.id} /><button type="submit" className="btn-sm btn-reject">Reject</button></form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}