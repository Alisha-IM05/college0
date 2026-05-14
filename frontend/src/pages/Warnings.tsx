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
  const honorRoll = data.honor_roll || 0;

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

        {role === 'student' && honorRoll > 0 && (
          <div style={{ marginTop: '1rem', padding: '12px 16px', background: '#fefce8', border: '1px solid #fde047', borderRadius: 8 }}>
            <strong>🏅 Honor Roll Distinctions Available: {honorRoll}</strong>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              You can use one honor roll distinction to remove a warning. Click "Remove with Honor Roll" next to any warning below.
            </p>
          </div>
        )}
      </div>

      <div className="card">
        {warnings.length > 0 ? warnings.map((w: any, i: number) => (
          <div key={i} style={{ borderLeft: '4px solid #ef4444', padding: '1rem 1.25rem', marginBottom: '.75rem', background: '#fff5f5', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <p style={{ marginBottom: 4 }}><strong>Reason:</strong> {w.reason}</p>
              <p className="muted">Date: {w.created_at}</p>
            </div>
            {role === 'student' && honorRoll > 0 && (
              <form method="POST" action={`/warnings/remove/${w.id}`} style={{ flexShrink: 0 }}>
                <button type="submit" className="btn btn-sm" style={{ background: '#ca8a04', borderColor: '#ca8a04', color: 'white', whiteSpace: 'nowrap' }}
                  onClick={e => { if (!confirm('Use 1 honor roll distinction to remove this warning?')) e.preventDefault(); }}>
                  🏅 Remove with Honor Roll
                </button>
              </form>
            )}
          </div>
        )) : (
          <p className="muted" style={{ textAlign: 'center', padding: '2rem' }}>✅ You have no warnings. Keep up the good work!</p>
        )}
      </div>
    </PageLayout>
  );
}