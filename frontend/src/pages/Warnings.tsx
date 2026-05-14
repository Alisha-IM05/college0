// ── Warnings.tsx ──────────────────────────────────────────────────────────────
import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function Warnings(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const warnings = data.warnings || [];
  const count = data.count || 0;

  return (
    <PageLayout username={username} role={role} activePage="warnings">
      <h2 style={{ marginBottom: '1.5rem' }}>My Warnings</h2>
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '.75rem' }}>Warning Summary for {username}</h3>
        <div className={`standing ${count >= 3 ? 'terminated' : count >= 2 ? 'probation' : 'good'}`}>
          Total Warnings: {count} / 3
          {count >= 3 && ' — You have been suspended!'}
          {count === 2 && ' — One more warning results in suspension!'}
          {count < 2 && ' — You are in good standing.'}
        </div>
      </div>
      <div className="card">
        {warnings.length > 0 ? warnings.map((w: any, i: number) => (
          <div key={i} style={{ borderLeft: '4px solid #ef4444', padding: '1rem 1.25rem', marginBottom: '.75rem', background: '#fff5f5', borderRadius: 6 }}>
            <p style={{ marginBottom: 4 }}><strong>Reason:</strong> {w.reason}</p>
            <p className="muted">Date: {w.created_at}</p>
          </div>
        )) : (
          <p className="muted" style={{ textAlign: 'center', padding: '2rem' }}>✅ You have no warnings. Keep up the good work!</p>
        )}
      </div>
    </PageLayout>
  );
}