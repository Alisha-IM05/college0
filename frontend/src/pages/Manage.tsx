import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

const PERIODS = ['setup', 'registration', 'special_registration', 'running', 'grading'];
const LABELS: Record<string, string> = {
  setup: 'Setup',
  registration: 'Registration',
  special_registration: 'Special Reg.',
  running: 'Running',
  grading: 'Grading',
};

export function Manage(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const message = data.message;

  const currentIdx = semester ? PERIODS.indexOf(semester.current_period) : -1;

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Semester Management</h2>

        {message && <div className="info">{message}</div>}

        {semester ? (
          <div className="card">
            <h3>{semester.name}</h3>
            <p className="muted" style={{ marginBottom: '1rem' }}>
              Current Period: <strong>{semester.current_period.toUpperCase()}</strong>
              {semester.current_period === 'special_registration' && ' — Special registration is open for students with cancelled courses.'}
            </p>

            {/* Progress bar */}
            <div style={{ display: 'flex', gap: '4px', marginBottom: '1rem' }}>
              {PERIODS.map((p, i) => (
                <div key={p} style={{
                  flex: 1,
                  height: '6px',
                  borderRadius: '99px',
                  background: i < currentIdx ? '#2E4A7A' : i === currentIdx ? '#3b82f6' : '#dbe2f0'
                }} />
              ))}
            </div>

            {/* Period steps */}
            <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
              {PERIODS.map((p, i) => (
                <div key={p} style={{
                  padding: '5px 12px',
                  borderRadius: '99px',
                  fontSize: '.78rem',
                  fontWeight: 600,
                  background: i === currentIdx ? '#dbeafe' : i < currentIdx ? '#dcfce7' : '#f1f5f9',
                  color: i === currentIdx ? '#1e40af' : i < currentIdx ? '#166534' : '#64748b',
                  border: `1px solid ${i === currentIdx ? '#93c5fd' : i < currentIdx ? '#86efac' : '#dbe2f0'}`,
                }}>
                  {i < currentIdx ? '✓ ' : ''}{LABELS[p]}
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <form method="POST" action="/semester/advance">
                <input type="hidden" name="semester_id" value={semester.id} />
                <button type="submit">Advance to Next Period →</button>
              </form>
              <form method="POST" action="/semester/retreat">
                <input type="hidden" name="semester_id" value={semester.id} />
                <button type="submit" style={{ background: '#64748b' }}>← Go Back One Period</button>
              </form>
            </div>
          </div>
        ) : (
          <div className="card">
            <p className="muted">No semester found.</p>
          </div>
        )}
      </div>
    </>
  );
}