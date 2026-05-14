import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

const PERIODS = ['setup', 'registration', 'special_registration', 'running', 'grading'];
const LABELS: Record<string, string> = { setup: 'Setup', registration: 'Registration', special_registration: 'Special Reg.', running: 'Running', grading: 'Grading' };
 
export function Manage(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const semester = data.semester;
  const message = data.message;
  const currentIdx = semester ? PERIODS.indexOf(semester.current_period) : -1;
 
  return (
    <PageLayout username={username} role="registrar" activePage="manage">
      <h2 style={{ marginBottom: '1.5rem' }}>Semester Management</h2>
      {message && <div className="info" style={{ marginBottom: '1rem' }}>{message}</div>}
      {data.special_reg_students && data.special_reg_students.length > 0 && semester?.current_period === 'special_registration' && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginBottom: '.5rem' }}>Students with Special Registration</h3>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {data.special_reg_students.map((s: any) => (
              <li key={s.username} style={{ padding: '4px 0', color: '#1e40af', fontWeight: 600 }}>{s.username}</li>
            ))}
          </ul>
        </div>
      )}
      {semester ? (
        <div className="card">
          <h3 style={{ marginBottom: '.5rem' }}>{semester.name}</h3>
          <p className="muted" style={{ marginBottom: '1rem' }}>Current Period: <strong>{semester.current_period.toUpperCase()}</strong></p>
          <div style={{ display: 'flex', gap: 4, marginBottom: '1rem' }}>
            {PERIODS.map((p, i) => <div key={p} style={{ flex: 1, height: 6, borderRadius: 99, background: i < currentIdx ? '#2E4A7A' : i === currentIdx ? '#3b82f6' : '#dbe2f0' }} />)}
          </div>
          <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
            {PERIODS.map((p, i) => (
              <div key={p} style={{ padding: '5px 12px', borderRadius: 99, fontSize: '.78rem', fontWeight: 600, background: i === currentIdx ? '#dbeafe' : i < currentIdx ? '#dcfce7' : '#f1f5f9', color: i === currentIdx ? '#1e40af' : i < currentIdx ? '#166534' : '#64748b', border: `1px solid ${i === currentIdx ? '#93c5fd' : i < currentIdx ? '#86efac' : '#dbe2f0'}` }}>
                {i < currentIdx ? '✓ ' : ''}{LABELS[p]}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <form method="POST" action="/semester/advance"><input type="hidden" name="semester_id" value={semester.id} /><button type="submit">Advance to Next Period →</button></form>
            <form method="POST" action="/semester/retreat"><input type="hidden" name="semester_id" value={semester.id} /><button type="submit" style={{ background: '#64748b' }}>← Go Back</button></form>
          </div>
        </div>
      ) : <div className="card"><p className="muted">No semester found.</p></div>}
    </PageLayout>
  );
}