import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function Taboo(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'registrar';
  const words = data.words || [];
  const message = data.message;
  const messageType = data.message_type;
 
  return (
    <PageLayout username={username} role={role} activePage="taboo">
      <h2 style={{ marginBottom: '1.5rem' }}>Taboo Word Manager</h2>
      {message && <div className={messageType === 'success' ? 'info' : messageType === 'error' ? 'error' : 'warn-note'} style={{ marginBottom: '1rem' }}>{message}</div>}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Add a Word</h3>
        <form method="POST" action="/taboo/add" style={{ display: 'flex', gap: '.75rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}><label>Word or phrase to ban</label><input type="text" name="word" placeholder="Enter word..." required /></div>
          <button type="submit" style={{ marginBottom: 1 }}>Add Word</button>
        </form>
      </div>
      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>Current Taboo Words ({words.length})</h3>
        {words.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem' }}>
            {words.map((word: string, i: number) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', background: '#fee2e2', color: '#991b1b', padding: '5px 12px', borderRadius: 99, fontSize: '.875rem', border: '1px solid #fca5a5' }}>
                {word}
                <a href={`/taboo/remove/${word}`} style={{ color: '#991b1b', fontWeight: 700, textDecoration: 'none' }}>✕</a>
              </span>
            ))}
          </div>
        ) : <p className="muted">No taboo words added yet.</p>}
      </div>
    </PageLayout>
  );
}