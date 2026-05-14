// ── Suspended.tsx ─────────────────────────────────────────────────────────────
// Shown to any user whose status = 'suspended'.
// Displays fine info, warning history, and a Pay Fine button.
import React, { useState } from 'react';
import { getPageData } from '../lib/data';

export function Suspended(): React.ReactElement {
  const data = getPageData();
  const username: string = data.username || '—';
  const warningCount: number = data.warning_count || 0;
  const warnings: { reason: string; created_at: string }[] = data.warnings || [];
  const fine: { amount: number; paid: number; approved: number; reason: string } | null = data.fine || null;

  const [paying, setPaying] = useState(false);
  const [paid, setPaid] = useState(fine?.paid === 1);
  const [msg, setMsg] = useState('');

  async function handlePay() {
    setPaying(true);
    try {
      const res = await fetch('/suspension/pay', {
        method: 'POST',
        headers: { 'X-Requested-With': 'fetch' },
      });
      const json = await res.json();
      if (json.ok) {
        setPaid(true);
        setMsg(json.message);
      } else {
        setMsg(json.message || 'Something went wrong.');
      }
    } catch {
      setMsg('Network error. Please try again.');
    } finally {
      setPaying(false);
    }
  }

  const fineAmount = fine?.amount ?? 200;
  const fineAlreadyApproved = fine?.approved === 1;

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1923',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'Inter, system-ui, sans-serif',
      padding: '2rem',
    }}>
      <div style={{ width: '100%', maxWidth: 560 }}>

        {/* Header card */}
        <div style={{
          background: '#1a0a0a',
          border: '1px solid #7f1d1d',
          borderRadius: 16,
          padding: '2rem',
          marginBottom: '1.25rem',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🚫</div>
          <h1 style={{ color: '#fca5a5', fontSize: '1.5rem', fontWeight: 800, margin: '0 0 .5rem' }}>
            Account Suspended
          </h1>
          <p style={{ color: 'rgba(255,255,255,.5)', fontSize: 14, margin: 0 }}>
            Hi <strong style={{ color: 'rgba(255,255,255,.75)' }}>{username}</strong> — your account has been suspended
            due to repeated conduct violations ({warningCount} warnings).
            You cannot access courses, reviews, or academic dashboards until this is resolved.
          </p>
        </div>

        {/* Fine card */}
        <div style={{
          background: '#1c1107',
          border: `1px solid ${fineAlreadyApproved ? '#14532d' : paid ? '#713f12' : '#92400e'}`,
          borderRadius: 16,
          padding: '1.75rem',
          marginBottom: '1.25rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={{ fontSize: 22 }}>💰</span>
            <h2 style={{ color: '#fcd34d', fontSize: '1rem', fontWeight: 700, margin: 0 }}>
              Disciplinary Fine
            </h2>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 8,
            marginBottom: 8,
          }}>
            <span style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fbbf24' }}>
              ${fineAmount.toFixed(2)}
            </span>
            <span style={{
              fontSize: 12,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: 20,
              background: fineAlreadyApproved ? '#14532d' : paid ? '#713f12' : '#7f1d1d',
              color: fineAlreadyApproved ? '#86efac' : paid ? '#fde68a' : '#fca5a5',
            }}>
              {fineAlreadyApproved ? '✅ APPROVED' : paid ? '⏳ PAYMENT SUBMITTED — AWAITING APPROVAL' : '⚠️ OUTSTANDING'}
            </span>
          </div>

          <p style={{ color: 'rgba(255,255,255,.45)', fontSize: 13, margin: '0 0 1.25rem' }}>
            {fine?.reason || 'Disciplinary suspension fine.'}
          </p>

          {msg && (
            <div style={{
              background: '#0f2a1a',
              border: '1px solid #166534',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: 13,
              color: '#86efac',
              marginBottom: '1rem',
            }}>
              {msg}
            </div>
          )}

          {!fineAlreadyApproved && (
            paid ? (
              <div style={{ fontSize: 13, color: 'rgba(255,255,255,.45)', textAlign: 'center', padding: '10px 0' }}>
                Payment submitted. The registrar will review and reactivate your account shortly.
              </div>
            ) : (
              <button
                onClick={handlePay}
                disabled={paying}
                style={{
                  width: '100%',
                  background: paying ? '#374151' : '#b45309',
                  color: 'white',
                  border: 'none',
                  borderRadius: 10,
                  padding: '14px',
                  fontSize: 15,
                  fontWeight: 700,
                  cursor: paying ? 'not-allowed' : 'pointer',
                  transition: 'background .15s',
                }}
                onMouseOver={e => { if (!paying) (e.currentTarget as HTMLButtonElement).style.background = '#d97706'; }}
                onMouseOut={e => { if (!paying) (e.currentTarget as HTMLButtonElement).style.background = '#b45309'; }}
              >
                {paying ? 'Submitting…' : `💳 Pay $${fineAmount.toFixed(2)} Fine`}
              </button>
            )
          )}
        </div>

        {/* Warnings history */}
        <div style={{
          background: '#111827',
          border: '1px solid rgba(255,255,255,.07)',
          borderRadius: 16,
          padding: '1.75rem',
          marginBottom: '1.25rem',
        }}>
          <h2 style={{ color: 'rgba(255,255,255,.75)', fontSize: '1rem', fontWeight: 700, margin: '0 0 1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>⚠️</span> Conduct History
            <span style={{
              fontSize: 11,
              fontWeight: 700,
              background: '#7f1d1d',
              color: '#fca5a5',
              padding: '2px 8px',
              borderRadius: 20,
              marginLeft: 4,
            }}>{warningCount} warnings</span>
          </h2>
          {warnings.length === 0 ? (
            <p style={{ color: 'rgba(255,255,255,.3)', fontSize: 13 }}>No warnings on record.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {warnings.map((w, i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,.04)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  borderLeft: '3px solid #7f1d1d',
                }}>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,.65)', marginBottom: 3 }}>{w.reason}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,.25)' }}>{w.created_at}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10 }}>
          <a
            href="/logout"
            style={{
              flex: 1,
              background: 'rgba(255,255,255,.06)',
              color: 'rgba(255,255,255,.6)',
              border: '1px solid rgba(255,255,255,.1)',
              borderRadius: 10,
              padding: '12px',
              fontSize: 14,
              fontWeight: 600,
              textAlign: 'center',
              textDecoration: 'none',
              display: 'block',
            }}
          >
            ⏻ Log Out
          </a>
        </div>

        <p style={{ textAlign: 'center', color: 'rgba(255,255,255,.2)', fontSize: 12, marginTop: '1.5rem' }}>
          Questions? Contact the registrar's office directly.
        </p>
      </div>
    </div>
  );
}