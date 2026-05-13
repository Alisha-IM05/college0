import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function Taboo(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const words = data.words || [];
  const message = data.message;
  const messageType = data.message_type;

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Taboo Word Manager</h2>

        {message && (
          <div className={messageType === 'success' ? 'info' : messageType === 'error' ? 'error' : 'warn-note'}>
            {message}
          </div>
        )}

        <div className="card">
          <h3>Add a Taboo Word</h3>
          <form method="POST" action="/taboo/add" style={{ display: 'flex', gap: '.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label>Word or phrase to ban</label>
              <input type="text" name="word" placeholder="Enter word..." required />
            </div>
            <button type="submit" style={{ marginBottom: '1px' }}>Add Word</button>
          </form>
        </div>

        <div className="card">
          <h3>Current Taboo Words</h3>
          {words.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem' }}>
              {words.map((word: string, i: number) => (
                <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', background: '#f8d7da', color: '#721c24', padding: '6px 12px', borderRadius: '99px', fontSize: '.875rem', border: '1px solid #f5c6cb' }}>
                  {word}
                  <a href={`/taboo/remove/${word}`} style={{ color: '#721c24', fontWeight: 700, textDecoration: 'none' }} title="Remove">✕</a>
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">No taboo words added yet.</p>
          )}
        </div>
      </div>
    </>
  );
}