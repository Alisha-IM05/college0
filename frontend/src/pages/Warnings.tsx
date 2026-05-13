import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function Warnings(): React.ReactElement {
  const data = getPageData();
  const username = data.username || '—';
  const warnings = (data as any).warnings || [];
  const count = (data as any).count || 0;

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>My Warnings</h2>

        <div className="card">
          <h3>Warning Summary for {username}</h3>
          <div
            className={`standing ${count >= 3 ? 'terminated' : count >= 2 ? 'probation' : 'good'}`}
            style={{ marginBottom: '1rem' }}
          >
            Total Warnings: {count} / 3
            {count >= 3 && ' — You have been suspended!'}
            {count === 2 && ' — One more warning results in suspension!'}
            {count < 2 && ' — You are in good standing.'}
          </div>
        </div>

        <div className="card">
          {warnings.length > 0 ? (
            warnings.map((w: any, i: number) => (
              <div key={i} style={{ borderLeft: '4px solid #dc2626', padding: '1rem', marginBottom: '.75rem', background: '#fff5f5', borderRadius: '6px' }}>
                <p><strong>Reason:</strong> {w.reason}</p>
                <p className="muted">Date: {w.created_at}</p>
              </div>
            ))
          ) : (
            <p className="muted">You have no warnings. Keep up the good work!</p>
          )}
        </div>
      </div>
    </>
  );
}