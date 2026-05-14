import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

export function Complaints(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const complaints = data.complaints || [];
  const allUsers = data.all_users || [];
  const myStudents = data.my_students || [];
  const message = data.message;
  const messageType = data.message_type;

  return (
    <PageLayout username={username} role={role} activePage="complaints">
      <h2 style={{ marginBottom: '1.5rem' }}>Complaints</h2>

      {message && (
        <div className={messageType === 'success' ? 'info' : 'error'} style={{ marginBottom: '1rem' }}>
          {message}
        </div>
      )}

      {/* ── STUDENT: file a complaint against anyone ── */}
      {role === 'student' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>File a Complaint</h3>
          <p className="muted" style={{ marginBottom: '1rem' }}>
            You can file a complaint against any student or instructor.
            You cannot file a complaint against yourself.
          </p>
          <form method="POST" action="/complaints/file/student">
            <label>Who are you complaining about?</label>
            <select name="filed_against" required>
              <option value="">— Select a user —</option>
              {allUsers.map((u: any) => (
                <option key={u.id} value={u.id}>{u.username} ({u.role})</option>
              ))}
            </select>
            <label>Description of the issue</label>
            <textarea name="description" rows={4} placeholder="Describe the issue clearly..." required />
            <button type="submit" className="block">Submit Complaint</button>
          </form>
        </div>
      )}

      {/* ── INSTRUCTOR: file complaint against own student ── */}
      {role === 'instructor' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>File a Complaint Against a Student</h3>
          <p className="muted" style={{ marginBottom: '1rem' }}>
            You can only file complaints against students enrolled in your courses.
            You must specify a requested action.
          </p>
          {myStudents.length > 0 ? (
            <form method="POST" action="/complaints/file/instructor">
              <label>Student</label>
              <select name="student_id" required>
                <option value="">— Select a student —</option>
                {myStudents.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.username}</option>
                ))}
              </select>
              <label>Description of the issue</label>
              <textarea name="description" rows={4} placeholder="Describe the conduct issue clearly..." required />
              <label>Requested Action</label>
              <select name="requested_action" required>
                <option value="">— Choose an action —</option>
                <option value="warning">Issue a Warning</option>
                <option value="deregister">De-register Student from My Courses</option>
              </select>
              <button type="submit" className="block">Submit Complaint</button>
            </form>
          ) : (
            <p className="muted">You have no students enrolled in your courses to file a complaint against.</p>
          )}
        </div>
      )}

      {/* ── REGISTRAR: view and resolve all pending complaints ── */}
      {role === 'registrar' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Pending Complaints</h3>

          {complaints.length > 0 ? complaints.map((c: any) => (
            <div
              key={c.id}
              style={{
                borderLeft: '4px solid #f59e0b',
                padding: '1rem 1.25rem',
                marginBottom: '1.5rem',
                background: '#fffaf5',
                borderRadius: 6
              }}
            >
              {/* Complaint details */}
              <p style={{ marginBottom: 4 }}>
                <strong>Filed by:</strong> {c.filed_by_name}
                <span className="muted" style={{ marginLeft: 6 }}>({c.filed_by_role})</span>
              </p>
              <p style={{ marginBottom: 4 }}>
                <strong>Against:</strong> {c.filed_against_name}
                <span className="muted" style={{ marginLeft: 6 }}>({c.filed_against_role})</span>
              </p>
              <p style={{ marginBottom: 4 }}><strong>Description:</strong> {c.description}</p>
              {c.requested_action && (
                <p style={{ marginBottom: 4 }}>
                  <strong>Requested action:</strong>{' '}
                  <span style={{
                    background: c.requested_action === 'deregister' ? '#fee2e2' : '#fef9c3',
                    color: c.requested_action === 'deregister' ? '#991b1b' : '#854d0e',
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 13
                  }}>
                    {c.requested_action === 'deregister' ? 'De-register Student' : 'Issue Warning'}
                  </span>
                </p>
              )}
              <p className="muted" style={{ marginBottom: '1rem' }}>
                Type: {c.complaint_type} &nbsp;·&nbsp; Filed: {c.created_at}
              </p>

              {/* ── Instructor complaint: accept or reject ── */}
              {c.complaint_type === 'instructor' ? (
                <>
                  <form method="POST" action={`/complaints/resolve/instructor/${c.id}`}>
                    <label>Resolution Notes (required)</label>
                    <input type="text" name="resolution_text" placeholder="Explain your decision..." required />
                    <p className="muted" style={{ margin: '6px 0 10px' }}>
                      <strong>Accept</strong> → student gets warned
                      {c.requested_action === 'deregister' ? " and de-registered from this instructor's courses" : ''}.&nbsp;
                      <strong>Reject</strong> → instructor gets warned for filing.
                    </p>
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                      <button
                        type="submit"
                        name="decision"
                        value="accept"
                        style={{ background: '#16a34a', color: 'white', border: 'none', padding: '8px 18px', borderRadius: 5, cursor: 'pointer' }}
                      >
                        ✅ Accept — Warn Student{c.requested_action === 'deregister' ? ' + De-register' : ''}
                      </button>
                      <button
                        type="submit"
                        name="decision"
                        value="reject"
                        style={{ background: '#dc2626', color: 'white', border: 'none', padding: '8px 18px', borderRadius: 5, cursor: 'pointer' }}
                      >
                        ❌ Reject — Warn Instructor
                      </button>
                    </div>
                  </form>

                  {/* Dismiss — its own separate form, NOT inside the resolve form above */}
                  <form method="POST" action={`/complaints/dismiss/${c.id}`} style={{ marginTop: '0.75rem' }}>
                    <button
                      type="submit"
                      style={{ background: '#6b7280', color: 'white', border: 'none', padding: '7px 16px', borderRadius: 5, cursor: 'pointer', fontSize: 13 }}
                      onClick={(e) => { if (!window.confirm('Dismiss this complaint with no action taken?')) e.preventDefault(); }}
                    >
                      🗑 Dismiss — No Action
                    </button>
                  </form>
                </>
              ) : (
                /* ── Student complaint: choose who gets the warning ── */
                <>
                  <form method="POST" action={`/complaints/resolve/student/${c.id}`}>
                    <label>Who should receive the warning?</label>
                    <select name="warn_user_id" required>
                      <option value="">— Select —</option>
                      <option value={c.filed_by}>{c.filed_by_name} (filed the complaint)</option>
                      <option value={c.filed_against}>{c.filed_against_name} (was reported)</option>
                    </select>
                    <label>Resolution Notes (required)</label>
                    <input type="text" name="resolution_text" placeholder="Explain your decision..." required />
                    <button type="submit" style={{ marginTop: '0.5rem' }}>
                      Resolve &amp; Issue Warning
                    </button>
                  </form>

                  {/* Dismiss — its own separate form, NOT inside the resolve form above */}
                  <form method="POST" action={`/complaints/dismiss/${c.id}`} style={{ marginTop: '0.75rem' }}>
                    <button
                      type="submit"
                      style={{ background: '#6b7280', color: 'white', border: 'none', padding: '7px 16px', borderRadius: 5, cursor: 'pointer', fontSize: 13 }}
                      onClick={(e) => { if (!window.confirm('Dismiss this complaint with no action taken?')) e.preventDefault(); }}
                    >
                      🗑 Dismiss — No Action
                    </button>
                  </form>
                </>
              )}
            </div>
          )) : (
            <p className="muted">✅ No pending complaints at this time.</p>
          )}
        </div>
      )}
    </PageLayout>
  );
}