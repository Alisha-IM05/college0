// ── Dashboard.tsx ──────────────────────────────────────────────────────────────
import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

const PERIOD_BLURB: Record<string, string> = {
  setup: 'Courses are being configured.',
  registration: 'Registration is open — enroll in your courses!',
  special_registration: 'Special registration is open.',
  running: 'Classes are in session.',
  grading: 'Grading period — grades are being submitted.',
};

export function Dashboard(): React.ReactElement {
  const data = getPageData() as any;
  const role = data.role || 'student';
  const username = data.username || '—';
  const semester = data.semester;
  const student = data.student_data;
  const grades = data.grades || [];

  return (
    <PageLayout username={username} role={role} activePage="dashboard">
      {/* Hero */}
      <div style={{ background: 'linear-gradient(135deg,#2E4A7A,#3d5f99)', borderRadius: 12, padding: '1.75rem 2rem', color: 'white', marginBottom: '1.5rem' }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', opacity: .6, marginBottom: 6 }}>{role.toUpperCase()} WORKSPACE</div>
        <h2 style={{ color: 'white', fontSize: '1.6rem', margin: '0 0 .5rem', fontWeight: 800 }}>Welcome back, {username}!</h2>
        {semester && <p style={{ opacity: .75, margin: '0 0 1rem', fontSize: 14 }}>{PERIOD_BLURB[semester.current_period]}</p>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {semester && <Chip>{semester.name}</Chip>}
          {student && <Chip>{student.status === 'probation' ? '⚠️ Probation' : (student.honor_roll ?? 0) > 0 ? '🏆 Honor Roll' : '✅ Good Standing'}</Chip>}
        </div>
      </div>

      {/* Student stats */}
      {role === 'student' && student && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '1rem', marginBottom: '1rem' }}>
            <StatCard label="Semester GPA" value={(student.semester_gpa ?? 0).toFixed(2)} />
            <StatCard label="Cumulative GPA" value={(student.cumulative_gpa ?? 0).toFixed(2)} />
            <StatCard label="Credits Earned" value={String(student.credits_earned ?? 0)} />
          </div>
          {grades.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>📊 Grade History</h3>
              <table>
                <thead><tr><th>Course</th><th>Semester</th><th>Grade</th></tr></thead>
                <tbody>{grades.map((g: any, i: number) => (
                  <tr key={i}><td>{g.course_name}</td><td style={{ color: '#64748b' }}>{g.semester_name}</td><td><strong>{g.letter_grade}</strong></td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </>
      )}
      {/* Registrar: all students + instructor stats */}
      {role === 'registrar' && (
        <>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>🎓 All Students</h3>
            <table>
              <thead><tr><th>Username</th><th>Status</th><th>Semester GPA</th><th>Cumulative GPA</th><th>Credits</th><th>Honor Roll</th></tr></thead>
              <tbody>{(data.all_students || []).map((s: any, i: number) => (
                <tr key={i}>
                  <td>{s.username}</td>
                  <td>{s.status}</td>
                  <td>{(s.semester_gpa ?? 0).toFixed(2)}</td>
                  <td>{(s.cumulative_gpa ?? 0).toFixed(2)}</td>
                  <td>{s.credits_earned ?? 0}</td>
                  <td>{s.honor_roll > 0 ? '🏆 ' + s.honor_roll : '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>👨‍🏫 Instructor Stats</h3>
            <table>
              <thead><tr><th>Username</th><th>Status</th><th>Courses This Semester</th><th>Avg Class GPA</th></tr></thead>
              <tbody>{(data.all_instructors || []).map((ins: any, i: number) => (
                <tr key={i}>
                  <td>{ins.username}</td>
                  <td>{ins.status}</td>
                  <td>{ins.course_count ?? 0}</td>
                  <td>{ins.avg_class_gpa != null ? Number(ins.avg_class_gpa).toFixed(2) : '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}

      {/* Quick links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: '1rem', marginTop: '1rem' }}>
        <QuickCard href="/complaints" icon="📢" title="Complaints" desc="File or manage complaints." />
        {role === 'registrar' && <>
          <QuickCard href="/flagged-gpas" icon="🚩" title="Flagged GPAs" desc="Review instructors with unusual class GPAs." />
          <QuickCard href="/taboo" icon="🚫" title="Taboo Words" desc="Manage banned words." />
          <QuickCard href="/semester" icon="📅" title="Semester" desc="Advance the semester period." />
          <QuickCard href="/courses/create" icon="➕" title="Courses" desc="Add or manage courses." />
          <QuickCard href="/graduation/resolve" icon="🎓" title="Graduation" desc="Review graduation requests." />
          <QuickCard href="/registrar/applications" icon="📝" title="Applications" desc="Approve pending applications." />
          <QuickCard href="/registrar/users" icon="👥" title="Users" desc="Manage user accounts." />
          
        </>}
        {role === 'student' && <>
          <QuickCard href="/courses/register" icon="📚" title="Registration" desc="Browse and register for courses." />
          <QuickCard href="/reviews" icon="📝" title="Course Reviews" desc="View and submit reviews." />
          <QuickCard href="/warnings" icon="⚠️" title="Warnings" desc="View warnings on your account." />
          <div className="dash-card">
            <div style={{ fontSize: 22, marginBottom: 8 }}>🎓</div>
            <h3>Apply for Graduation</h3>
            <p>Submit your graduation application.</p>
            <form method="POST" action="/graduation/apply" style={{ marginTop: '.75rem' }}>
              <button type="submit" style={{ padding: '6px 16px', fontSize: 13 }}>Apply</button>
            </form>
          </div>
        </>}
        {role === 'instructor' && <>
          <QuickCard href="/instructor/courses" icon="📚" title="My Courses" desc="View and manage your courses." />
          <QuickCard href="/warnings" icon="⚠️" title="Warnings" desc="View warnings on your account." />
          <QuickCard href="/flagged-gpas" icon="🚩" title="GPA Review" desc="Submit justification for flagged class GPAs." />
        </>}
      </div>
    </PageLayout>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span style={{ background: 'rgba(255,255,255,.15)', border: '1px solid rgba(255,255,255,.25)', padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600 }}>{children}</span>;
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: 'white', borderRadius: 10, padding: '1.25rem', borderTop: '3px solid #2E4A7A', boxShadow: '0 1px 4px rgba(46,74,122,.08)', border: '1px solid #dbe2f0', borderTopColor: '#2E4A7A' }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: '#2E4A7A', lineHeight: 1.1, marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .6 }}>{label}</div>
    </div>
  );
}

function QuickCard({ href, icon, title, desc }: { href: string; icon: string; title: string; desc: string }) {
  return (
    <a href={href} className="dash-card">
      <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </a>
  );
}