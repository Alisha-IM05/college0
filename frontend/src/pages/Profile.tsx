import React, { useState, useEffect } from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

const TUTORIAL_STEPS = [
  {
    icon: '📋',
    title: 'Register for Courses',
    desc: 'During the registration period, go to Registration in the sidebar to browse and enroll in courses. You can register for up to 4 courses per semester.',
  },
  {
    icon: '⏳',
    title: 'Waitlists',
    desc: 'If a course is full, you can join the waitlist. Your instructor will admit or reject waitlisted students once the semester starts.',
  },
  {
    icon: '📊',
    title: 'Track Your GPA',
    desc: 'Your semester and cumulative GPA are shown on your dashboard after instructors submit grades during the grading period.',
  },
  {
    icon: '📝',
    title: 'Leave Course Reviews',
    desc: 'After each semester you can review your courses. Reviews are anonymous and help improve course quality.',
  },
  {
    icon: '⚠️',
    title: 'Academic Standing',
    desc: 'Maintain a GPA above 2.25 to stay in good standing. Below 2.0 puts you on probation. Honor Roll is awarded for GPA above 3.75.',
  },
  {
    icon: '🎓',
    title: 'Graduation',
    desc: 'Once you have earned 8 credits, you can apply for graduation during the grading period. The registrar will review your application.',
  },
];

export function Profile(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const user = data.user || {};
  const student = data.student || null;

  // Tutorial modal state — show on first visit (stored in localStorage)
  const tutorialKey = `college0_tutorial_done_${username}`;
  const [showTutorial, setShowTutorial] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (role === 'student') {
      const done = localStorage.getItem(tutorialKey);
      if (!done) setShowTutorial(true);
    }
  }, []);

  const closeTutorial = () => {
    localStorage.setItem(tutorialKey, 'true');
    setShowTutorial(false);
  };

  return (
    <PageLayout username={username} role={role} activePage="profile">

      {/* ── TUTORIAL MODAL ── */}
      {showTutorial && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: '1rem',
        }}>
          <div style={{
            background: 'white', borderRadius: 14, padding: '2rem',
            maxWidth: 480, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,.25)',
          }}>
            {/* Progress dots */}
            <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: '1.5rem' }}>
              {TUTORIAL_STEPS.map((_, i) => (
                <div key={i} style={{ width: i === step ? 20 : 8, height: 8, borderRadius: 99, background: i === step ? '#2E4A7A' : i < step ? '#93c5fd' : '#e2e8f0', transition: 'all .3s' }} />
              ))}
            </div>

            {/* Step content */}
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: 48, marginBottom: '1rem' }}>{TUTORIAL_STEPS[step].icon}</div>
              <h3 style={{ fontSize: '1.2rem', marginBottom: '.75rem' }}>{TUTORIAL_STEPS[step].title}</h3>
              <p style={{ color: '#64748b', lineHeight: 1.7, fontSize: 14 }}>{TUTORIAL_STEPS[step].desc}</p>
            </div>

            {/* Navigation */}
            <div style={{ display: 'flex', gap: '.75rem', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                onClick={() => setStep(s => Math.max(0, s - 1))}
                style={{ background: '#f1f5f9', color: '#64748b', border: 'none', visibility: step === 0 ? 'hidden' : 'visible' }}
              >← Back</button>

              <span style={{ fontSize: 12, color: '#94a3b8' }}>{step + 1} of {TUTORIAL_STEPS.length}</span>

              {step < TUTORIAL_STEPS.length - 1 ? (
                <button onClick={() => setStep(s => s + 1)}>Next →</button>
              ) : (
                <button onClick={closeTutorial} style={{ background: '#15803d' }}>Get Started ✓</button>
              )}
            </div>

            {/* Skip */}
            <div style={{ textAlign: 'center', marginTop: '1rem' }}>
              <button onClick={closeTutorial} style={{ background: 'none', color: '#94a3b8', fontSize: 12, border: 'none', cursor: 'pointer', padding: 0 }}>
                Skip tutorial
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── PROFILE PAGE ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <h2 style={{ margin: 0 }}>My Profile</h2>
        {role === 'student' && (
          <button
            onClick={() => { setStep(0); setShowTutorial(true); }}
            style={{ background: '#eef2f9', color: '#2E4A7A', border: '1px solid #c8d3e8', fontSize: 13 }}
          >
            📖 View Tutorial
          </button>
        )}
      </div>

      {/* Basic info */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1.25rem' }}>
          <div style={{
            width: 64, height: 64, background: '#2E4A7A', borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontWeight: 700, fontSize: 24, flexShrink: 0,
          }}>
            {username.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 style={{ margin: '0 0 .25rem' }}>{username}</h3>
            <span style={{
              background: role === 'registrar' ? '#fef3c7' : role === 'instructor' ? '#dcfce7' : '#dbeafe',
              color: role === 'registrar' ? '#92400e' : role === 'instructor' ? '#166534' : '#1e40af',
              padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: .5,
            }}>{role}</span>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>Username</div>
            <div style={{ fontWeight: 500 }}>{user.username || '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>Email</div>
            <div style={{ fontWeight: 500 }}>{user.email || '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>Role</div>
            <div style={{ fontWeight: 500, textTransform: 'capitalize' }}>{user.role || '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>Account Status</div>
            <div>
              <span className={`pill ${user.status === 'active' ? 's-active' : user.status === 'suspended' ? 's-suspended' : 's-terminated'}`}>
                {user.status || 'active'}
              </span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>Member Since</div>
            <div style={{ fontWeight: 500 }}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</div>
          </div>
        </div>
      </div>

      {/* Student academic info */}
      {role === 'student' && student && (
        <div className="card">
          <h3 style={{ marginBottom: '1.25rem' }}>Academic Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '1rem', marginBottom: '1rem' }}>
            {[
              { label: 'Semester GPA', value: (student.semester_gpa ?? 0).toFixed(2) },
              { label: 'Cumulative GPA', value: (student.cumulative_gpa ?? 0).toFixed(2) },
              { label: 'Credits Earned', value: String(student.credits_earned ?? 0) },
            ].map(s => (
              <div key={s.label} style={{ background: '#f8fafd', borderRadius: 8, padding: '1rem', textAlign: 'center', border: '1px solid #dbe2f0', borderTop: '3px solid #2E4A7A' }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#2E4A7A', lineHeight: 1.1, marginBottom: 4 }}>{s.value}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5 }}>{s.label}</div>
              </div>
            ))}
          </div>
          <div className={`standing ${student.status === 'probation' ? 'probation' : (student.honor_roll ?? 0) > 0 ? 'honor' : 'good'}`}>
            {student.status === 'probation' ? '⚠️ Academic Probation — GPA must improve above 2.25' : (student.honor_roll ?? 0) > 0 ? '🏆 Honor Roll — Outstanding academic achievement!' : '✅ Good Standing'}
          </div>
        </div>
      )}

      {/* Change password link */}
      <div className="card" style={{ marginTop: '1rem' }}>
        <h3 style={{ marginBottom: '.75rem' }}>Account Settings</h3>
        <a href="/change-password" className="btn" style={{ fontSize: 13 }}>Change Password</a>
      </div>

    </PageLayout>
  );
}