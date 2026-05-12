import React from 'react';

import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

const PERIOD_BLURB: Record<string, string> = {
  setup: '🔧 Courses are being configured.',
  registration: '📋 Registration is open — enroll in your courses!',
  special_registration: '📋 Special registration is open.',
  running: '📖 Classes are in session.',
  grading: '✅ Grading period — grades are being submitted.',
};

export function Dashboard(): React.ReactElement {
  const data = getPageData();
  const role = data.role || 'student';
  const username = data.username || '—';
  const semester = data.semester;
  const student = data.student_data;
  const grades = data.grades || [];

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <div className="welcome">
          <span className={`badge ${role}`}>{role.toUpperCase()}</span>
          <h2>Welcome back, {username}!</h2>
          {semester && (
            <p className="semester-banner">
              📅 <strong>{semester.name}</strong> &nbsp;|&nbsp; Period:{' '}
              <strong>{semester.current_period.toUpperCase()}</strong>
              &nbsp;|&nbsp; {PERIOD_BLURB[semester.current_period] || ''}
            </p>
          )}
        </div>

        <div className="cards">
          <a className="dash-card" href="/reviews/1">
            <h3>📝 Course Reviews</h3>
            <p>View and submit reviews for courses.</p>
          </a>
          <a className="dash-card" href="/warnings">
            <h3>⚠️ My Warnings</h3>
            <p>View all warnings on your account.</p>
          </a>
          <a className="dash-card" href="/complaints">
            <h3>📢 Complaints</h3>
            <p>File or manage complaints.</p>
          </a>

          {role === 'registrar' && (
            <>
              <a className="dash-card" href="/taboo">
                <h3>🚫 Taboo Words</h3>
                <p>Manage the list of banned words.</p>
              </a>
              <a className="dash-card" href="/semester">
                <h3>📅 Semester Management</h3>
                <p>Advance the semester period.</p>
              </a>
              <a className="dash-card" href="/courses/create">
                <h3>➕ Courses</h3>
                <p>Add or manage courses in the system.</p>
              </a>
              <a className="dash-card" href="/graduation/resolve">
                <h3>🎓 Graduation Applications</h3>
                <p>Review and resolve student graduation requests.</p>
              </a>
              <a className="dash-card" href="/registrar/applications">
                <h3>📝 Account Applications</h3>
                <p>Approve or reject pending student / instructor applications.</p>
              </a>
              <a className="dash-card" href="/registrar/users">
                <h3>👥 Manage Users</h3>
                <p>Suspend, terminate, or reactivate accounts.</p>
              </a>
            </>
          )}

          {role === 'student' && student && (
            <div className="card" style={{ flexBasis: '100%' }}>
              <h3>📊 Academic Summary</h3>
              <div className="stat-row">
                <div className="stat">
                  <div className="stat-num">{(student.semester_gpa ?? 0).toFixed(2)}</div>
                  <div className="stat-label">Semester GPA</div>
                </div>
                <div className="stat">
                  <div className="stat-num">{(student.cumulative_gpa ?? 0).toFixed(2)}</div>
                  <div className="stat-label">Cumulative GPA</div>
                </div>
                <div className="stat">
                  <div className="stat-num">{student.credits_earned ?? 0}</div>
                  <div className="stat-label">Credits Earned</div>
                </div>
              </div>
              <StandingBanner student={student} />
              {grades.length > 0 ? (
                <table>
                  <thead>
                    <tr>
                      <th>Course</th>
                      <th>Semester</th>
                      <th>Grade</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grades.map((g, i) => (
                      <tr key={i}>
                        <td>{g.course_name}</td>
                        <td>{g.semester_name}</td>
                        <td style={{ fontWeight: 'bold' }}>{g.letter_grade}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted" style={{ marginTop: 10 }}>No grades on record yet.</p>
              )}
            </div>
          )}

          {role === 'student' && (
            <>
              <a className="dash-card" href="/courses/register">
                <h3>📚 Course Registration</h3>
                <p>Browse and register for available courses.</p>
              </a>
              <div className="dash-card">
                <h3>🎓 Apply for Graduation</h3>
                <p>Submit your graduation application.</p>
                <form method="POST" action="/graduation/apply">
                  <button type="submit">Apply</button>
                </form>
              </div>
            </>
          )}

          {role === 'instructor' && (
            <a className="dash-card" href="/instructor/courses">
              <h3>📚 My Courses</h3>
              <p>View your courses and manage student rosters.</p>
            </a>
          )}
        </div>
      </div>
    </>
  );
}

function StandingBanner({ student }: { student: NonNullable<ReturnType<typeof getPageData>['student_data']> }): React.ReactElement {
  const semGpa = student.semester_gpa ?? 0;
  const cumGpa = student.cumulative_gpa ?? 0;
  const honor = (student.honor_roll ?? 0) > 0 && (semGpa > 3.75 || cumGpa > 3.5);

  if (honor) {
    return <div className="standing honor">🏆 Honor Roll</div>;
  }
  if (student.status === 'probation') {
    return (
      <div className="standing probation">
        ⚠️ Academic Probation — Your GPA must improve above 2.25
      </div>
    );
  }
  if (student.status === 'terminated') {
    return (
      <div className="standing terminated">
        ❌ Your enrollment has been terminated due to academic performance
        (GPA below 2.0 or failed the same course twice). Please contact the registrar.
      </div>
    );
  }
  return <div className="standing good">✅ Good Standing</div>;
}
