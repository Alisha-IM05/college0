import React from 'react';
import { getPageData } from '../lib/data';

export function Home(): React.ReactElement {
  const data = getPageData() as any;
  const semester = data.semester;
  const stats = data.stats || {};

  const PERIOD_LABELS: Record<string, string> = {
    setup: 'Class Setup',
    registration: 'Registration',
    special_registration: 'Special Registration',
    running: 'Classes Running',
    grading: 'Grading',
  };

  const PHASES = ['setup', 'registration', 'running', 'grading'];
  const PHASE_DESC: Record<string, string> = {
    setup: 'Registrars build the schedule, assign instructors, set class sizes.',
    registration: 'Students enroll in courses. Waitlists open when seats fill up.',
    running: 'Classes are in session. Instructors manage rosters.',
    grading: 'Instructors submit grades. Students apply for graduation.',
  };

  const currentPhase = semester?.current_period || 'setup';

  return (
    <div style={{ minHeight: '100vh', background: '#f0f4f8', fontFamily: 'Arial, sans-serif' }}>

      {/* ── NAVBAR ── */}
      <div className="navbar">
        <h1 style={{ color: 'white', textShadow: '0 1px 3px rgba(0,0,0,.3)' }}>College<span style={{ color: '#fbbf24' }}>0</span></h1>
        <div>
          <a href="/login">Sign In</a>
          <a href="/apply" style={{ marginLeft: 16, background: 'white', color: '#2E4A7A', padding: '6px 16px', borderRadius: 6, fontWeight: 600 }}>Apply</a>
        </div>
      </div>

      {/* ── HERO ── */}
      <div style={{ background: 'linear-gradient(135deg, #2E4A7A 0%, #3d5f99 100%)', color: 'white', padding: '80px 40px' }}>
        <div style={{ maxWidth: 700, margin: '0 auto', textAlign: 'center' }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', opacity: .6, marginBottom: 12 }}>CCNY · Software Engineering</p>
          <h1 style={{ color: 'white', fontSize: 42, lineHeight: 1.15, marginBottom: 20, fontWeight: 800 }}>
            A smarter system for college program management.
          </h1>
          <p style={{ opacity: .75, fontSize: 16, lineHeight: 1.7, marginBottom: 32 }}>
            One shared workspace for students, instructors, and registrars — from course setup through graduation.
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 32, justifyContent: 'center' }}>
            {['4 semester phases', 'Role-based dashboards', 'AI recommendations', 'Conduct system'].map(f => (
              <span key={f} style={{ background: 'rgba(255,255,255,.15)', border: '1px solid rgba(255,255,255,.25)', padding: '5px 14px', borderRadius: 99, fontSize: 13 }}>{f}</span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 32 }}>
            <a href="/apply?role=student" style={{ background: 'white', color: '#2E4A7A', padding: '10px 24px', borderRadius: 6, fontWeight: 700, textDecoration: 'none', fontSize: 14 }}>Apply as Student</a>
            <a href="/apply?role=instructor" style={{ background: 'rgba(255,255,255,.15)', color: 'white', padding: '10px 24px', borderRadius: 6, fontWeight: 600, textDecoration: 'none', fontSize: 14, border: '1px solid rgba(255,255,255,.3)' }}>Apply as Instructor</a>
            <a href="/apply/status" style={{ color: 'rgba(255,255,255,.7)', padding: '10px 16px', borderRadius: 6, fontWeight: 500, textDecoration: 'none', fontSize: 14 }}>Check Status →</a>
          </div>
          <div style={{ borderTop: '1px solid rgba(255,255,255,.15)', paddingTop: 28 }}>
            <div style={{ opacity: .75, fontSize: 15, marginBottom: 16 }}>Already have an account? Sign in to access your dashboard.</div>
            <a href="/login"
              style={{ background: 'white', color: '#2E4A7A', padding: '14px 40px', borderRadius: 10, fontWeight: 700, textDecoration: 'none', fontSize: 16, display: 'inline-flex', alignItems: 'center', gap: 10 }}
              onMouseOver={e => (e.currentTarget.style.opacity = '0.9')}
              onMouseOut={e => (e.currentTarget.style.opacity = '1')}
            >
              🔐 Sign In
            </a>
          </div>
        </div>
      </div>

      {/* ── SEMESTER STATUS ── */}
      {semester && (
        <div style={{ maxWidth: 900, margin: '40px auto', padding: '0 40px' }}>
          <div style={{ background: 'white', borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,.08)', padding: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: '#64748b', margin: 0 }}>ACTIVE SEMESTER</p>
                <h3 style={{ margin: '4px 0 0', color: '#2E4A7A' }}>{semester.name}</h3>
              </div>
              <span style={{ background: '#dbeafe', color: '#1e40af', padding: '4px 14px', borderRadius: 99, fontWeight: 700, fontSize: 13 }}>
                {PERIOD_LABELS[currentPhase] || currentPhase}
              </span>
            </div>

            {/* Phase progress */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
              {PHASES.map((p, i) => {
                const phaseIdx = PHASES.indexOf(currentPhase);
                const isPast = i < phaseIdx;
                const isActive = p === currentPhase || (currentPhase === 'special_registration' && p === 'registration');
                return (
                  <div key={p} style={{ flex: 1, height: 6, borderRadius: 99, background: isActive ? '#2E4A7A' : isPast ? '#93c5fd' : '#e2e8f0' }} />
                );
              })}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
              {PHASES.map((p) => {
                const phaseIdx = PHASES.indexOf(currentPhase === 'special_registration' ? 'registration' : currentPhase);
                const idx = PHASES.indexOf(p);
                const isActive = p === currentPhase || (currentPhase === 'special_registration' && p === 'registration');
                const isPast = idx < phaseIdx;
                return (
                  <div key={p} style={{
                    padding: '12px 14px',
                    borderRadius: 8,
                    background: isActive ? '#dbeafe' : isPast ? '#f0fdf4' : '#f8fafc',
                    border: `1px solid ${isActive ? '#93c5fd' : isPast ? '#bbf7d0' : '#e2e8f0'}`,
                  }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: isActive ? '#1e40af' : isPast ? '#166534' : '#94a3b8', marginBottom: 4 }}>
                      {isPast ? '✓ ' : ''}{PERIOD_LABELS[p]}
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.4 }}>{PHASE_DESC[p]}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── STATS ── */}
      <div style={{ maxWidth: 900, margin: '0 auto 40px', padding: '0 40px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
          {[
            { label: 'Active Students', value: stats.student_count || '—', icon: '🎓' },
            { label: 'Courses This Semester', value: stats.course_count || '—', icon: '📚' },
            { label: 'Instructors', value: stats.instructor_count || '—', icon: '👨‍🏫' },
          ].map(s => (
            <div key={s.label} style={{ background: 'white', borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,.08)', padding: '24px 28px', borderTop: '3px solid #2E4A7A' }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>{s.icon}</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: '#2E4A7A', lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── FOOTER ── */}
      <div style={{ borderTop: '1px solid #e2e8f0', padding: '24px 40px', textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
        College0 · CCNY Software Engineering · Group E
      </div>
    </div>
  );
}