import React, { useState } from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

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
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Complaints</h2>

        {message && (
          <div className={messageType === 'success' ? 'info' : 'error'}>{message}</div>
        )}

        {/* Student: file a complaint */}
        {role === 'student' && (
          <div className="card">
            <h3>File a Complaint</h3>
            <form method="POST" action="/complaints/file/student">
              <label>User to complain about</label>
              <select name="filed_against" required>
                <option value="">— Select user —</option>
                {allUsers.map((u: any) => (
                  <option key={u.id} value={u.id}>{u.username} ({u.role})</option>
                ))}
              </select>
              <label>Description</label>
              <textarea name="description" rows={4} placeholder="Describe the issue..." style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '5px', fontSize: '14px', fontFamily: 'inherit' }} required />
              <button type="submit" className="block">Submit Complaint</button>
            </form>
          </div>
        )}

        {/* Instructor: file complaint against student */}
        {role === 'instructor' && (
          <div className="card">
            <h3>File a Complaint Against a Student</h3>
            <form method="POST" action="/complaints/file/instructor">
              <label>Student</label>
              <select name="student_id" required>
                <option value="">— Select student —</option>
                {myStudents.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.username}</option>
                ))}
              </select>
              <label>Description</label>
              <textarea name="description" rows={4} placeholder="Describe the issue..." style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '5px', fontSize: '14px', fontFamily: 'inherit' }} required />
              <label>Requested Action</label>
              <select name="requested_action">
                <option value="warning">Issue Warning</option>
                <option value="suspension">Suspend Student</option>
              </select>
              <button type="submit" className="block">Submit Complaint</button>
            </form>
          </div>
        )}

        {/* Registrar: resolve complaints */}
        {role === 'registrar' && (
          <div className="card">
            <h3>Pending Complaints</h3>
            {complaints.length > 0 ? complaints.map((c: any) => (
              <div key={c.id} style={{ borderLeft: '4px solid #f59e0b', padding: '1rem', marginBottom: '1rem', background: '#fffaf5', borderRadius: '6px' }}>
                <p><strong>Type:</strong> {c.complaint_type || 'Student'}</p>
                <p><strong>Filed by:</strong> {c.filed_by_name}</p>
                <p><strong>Against:</strong> {c.filed_against_name}</p>
                <p><strong>Description:</strong> {c.description}</p>
                <p className="muted">Filed on: {c.created_at}</p>

                {c.complaint_type === 'instructor' ? (
                  <form method="POST" action={`/complaints/resolve/instructor/${c.id}`} style={{ marginTop: '.75rem' }}>
                    <label>Decision</label>
                    <select name="decision" required>
                      <option value="warn">Warn Student</option>
                      <option value="reject">Reject Complaint</option>
                    </select>
                    <label>Resolution Notes</label>
                    <input type="text" name="resolution_text" placeholder="Resolution notes" required />
                    <button type="submit" className="block">Resolve</button>
                  </form>
                ) : (
                  <form method="POST" action={`/complaints/resolve/student/${c.id}`} style={{ marginTop: '.75rem' }}>
                    <label>User ID to warn</label>
                    <input type="number" name="warn_user_id" placeholder="User ID" required />
                    <label>Resolution Notes</label>
                    <input type="text" name="resolution_text" placeholder="Resolution notes" required />
                    <button type="submit" className="block">Resolve &amp; Issue Warning</button>
                  </form>
                )}
              </div>
            )) : (
              <p className="muted">No pending complaints.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}