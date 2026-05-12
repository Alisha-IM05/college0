import React, { useState } from 'react';

import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

export function ChangePassword(): React.ReactElement {
  const data = getPageData();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(data.error ?? null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.');
      return;
    }
    setError(null);
    setSubmitting(true);
    const resp = await postForm('/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    setSubmitting(false);
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
    } else {
      setError(resp.error || 'Could not update password.');
    }
  }

  return (
    <div className="login-shell">
      <div className="login-box">
        <h1>Change Password</h1>
        <p className="subtitle">Signed in as {data.username || '—'}</p>

        {data.must_change && (
          <div className="warn-note">
            You're using a temporary password. Please choose a new one to continue.
          </div>
        )}

        {error && <div className="error">{error}</div>}

        <form onSubmit={onSubmit}>
          <label htmlFor="old_password">Current password</label>
          <input
            id="old_password"
            type="password"
            required
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
          />

          <label htmlFor="new_password">New password</label>
          <input
            id="new_password"
            type="password"
            minLength={6}
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />

          <label htmlFor="confirm_password">Confirm new password</label>
          <input
            id="confirm_password"
            type="password"
            minLength={6}
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />

          <button type="submit" className="block" disabled={submitting}>
            {submitting ? 'Updating…' : 'Update password'}
          </button>
        </form>

        {!data.must_change && (
          <div className="apply-links">
            <a href="/dashboard">Back to dashboard</a>
          </div>
        )}
      </div>
    </div>
  );
}
