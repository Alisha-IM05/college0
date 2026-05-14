import React, { useState } from 'react';

import { getPageData, UserRow } from '../lib/data';
import { postForm } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { Pill } from '../components/Pill';

type Action = 'suspend' | 'terminate' | 'reactivate' | 'approve_fine';

export function RegistrarUsers(): React.ReactElement {
  const data = getPageData();
  const [users, setUsers] = useState<UserRow[]>(data.users || []);
  const [message, setMessage] = useState<string | null>(data.message ?? null);
  const [busy, setBusy] = useState<number | null>(null);
  const [pendingFineIds, setPendingFineIds] = useState<number[]>(data.pending_fine_user_ids || []);

  async function act(userId: number, action: Action) {
    setBusy(userId);
    const resp = await postForm(`/registrar/users/${userId}/${action}`, {});
    setBusy(null);
    if (resp.message) setMessage(resp.message);
    if (action === 'approve_fine') {
      setPendingFineIds(ids => ids.filter(id => id !== userId));
    }
    if (resp.data) {
      const d = resp.data as { users?: UserRow[] };
      if (d.users) setUsers(d.users);
    }
  }

  return (
    <>
      <Navbar
        username={data.username}
        extras={
          <>
            <a href="/dashboard">Dashboard</a>
            <a href="/registrar/applications">Applications</a>
          </>
        }
      />
      <div className="container">
        {message && <div className="banner-info">{message}</div>}

        <div className="card">
          <h2>Manage users</h2>
          <p className="muted">
            Suspend or terminate student / instructor accounts. Suspended users
            must pay their fine and receive registrar approval before being reactivated.
          </p>
          {users.length === 0 ? (
            <p className="muted">No users yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td>{u.username}</td>
                    <td>{u.email}</td>
                    <td>{capitalize(u.role)}</td>
                    <td>
                      <Pill variant="s" status={u.status} />
                      {pendingFineIds.includes(u.id) && (
                        <span style={{
                          marginLeft: 6,
                          fontSize: 11,
                          fontWeight: 700,
                          background: '#713f12',
                          color: '#fde68a',
                          padding: '2px 7px',
                          borderRadius: 20,
                        }}>
                          💰 Fine Paid — Awaiting Approval
                        </span>
                      )}
                    </td>
                    <td>{u.created_at}</td>
                    <td>
                      <UserActions
                        user={u}
                        busy={busy === u.id}
                        hasPendingFine={pendingFineIds.includes(u.id)}
                        onAction={(a) => void act(u.id, a)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}

interface ActionsProps {
  user: UserRow;
  busy: boolean;
  hasPendingFine: boolean;
  onAction: (a: Action) => void;
}

function UserActions({ user, busy, hasPendingFine, onAction }: ActionsProps): React.ReactElement {
  if (user.status === 'active') {
    return (
      <>
        <button className="btn btn-sm btn-suspend" disabled={busy}
                onClick={() => onAction('suspend')} style={{ marginRight: 4 }}>
          Suspend
        </button>
        <button className="btn btn-sm btn-terminate" disabled={busy}
                onClick={() => onAction('terminate')}>
          Terminate
        </button>
      </>
    );
  }
  return (
    <>
      {hasPendingFine ? (
        <button
          className="btn btn-sm btn-reactivate"
          disabled={busy}
          onClick={() => onAction('approve_fine')}
          style={{ marginRight: 4, background: '#b45309', borderColor: '#b45309' }}
        >
          ✅ Approve Payment & Reactivate
        </button>
      ) : (
        <button className="btn btn-sm btn-reactivate" disabled={busy}
                onClick={() => onAction('reactivate')} style={{ marginRight: 4 }}>
          Reactivate
        </button>
      )}
      {user.status === 'suspended' && (
        <button className="btn btn-sm btn-terminate" disabled={busy}
                onClick={() => onAction('terminate')}>
          Terminate
        </button>
      )}
    </>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}