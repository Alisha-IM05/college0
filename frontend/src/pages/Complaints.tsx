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

      {message && <div className={messageType === 'success' ? 'info' : 'error'} style={{ marginBottom: '1rem' }}>{message}</div>}

      {role === 'student' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>File a Complaint</h3>
          <form method="POST" action="/complaints/file/student">
            <label>User to complain about</label>
            <select name="filed_against" required>
              <option value="">— Select user —</option>
              {allUsers.map((u: any) => <option key={u.id} value={u.id}>{u.username} ({u.role})</option>)}
            </select>
            <label>Description</label>
            <textarea name="description" rows={4} placeholder="Describe the issue..." required />
            <button type="submit" className="block">Submit Complaint</button>
          </form>
        </div>
      )}

      {role === 'instructor' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>File a Complaint Against a Student</h3>
          <form method="POST" action="/complaints/file/instructor">
            <label>Student</label>
            <select name="student_id" required>
              <option value="">— Select student —</option>
              {myStudents.map((s: any) => <option key={s.id} value={s.id}>{s.username}</option>)}
            </select>
            <label>Description</label>
            <textarea name="description" rows={4} placeholder="Describe the issue..." required />
            <label>Requested Action</label>
            <select name="requested_action">
              <option value="warning">Issue Warning</option>
              <option value="suspension">Suspend Student</option>
            </select>
            <button type="submit" className="block">Submit Complaint</button>
          </form>
        </div>
      )}

      {role === 'registrar' && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Pending Complaints</h3>
          {complaints.length > 0 ? complaints.map((c: any) => (
            <div key={c.id} style={{ borderLeft: '4px solid #f59e0b', padding: '1rem 1.25rem', marginBottom: '1rem', background: '#fffaf5', borderRadius: 6 }}>
              <p style={{ marginBottom: 4 }}><strong>Filed by:</strong> {c.filed_by_name}</p>
              <p style={{ marginBottom: 4 }}><strong>Against:</strong> {c.filed_against_name}</p>
              <p style={{ marginBottom: 4 }}><strong>Description:</strong> {c.description}</p>
              <p className="muted" style={{ marginBottom: '1rem' }}>Filed on: {c.created_at}</p>
              <form method="POST" action={`/complaints/resolve/student/${c.id}`}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '.75rem', marginBottom: '.75rem' }}>
                  <div><label>User ID to warn</label><input type="number" name="warn_user_id" placeholder="User ID" required /></div>
                  <div><label>Resolution notes</label><input type="text" name="resolution_text" placeholder="Resolution notes" required /></div>
                </div>
                <button type="submit">Resolve &amp; Issue Warning</button>
              </form>
            </div>
          )) : <p className="muted">No pending complaints.</p>}
        </div>
      )}
    </PageLayout>
  );
}