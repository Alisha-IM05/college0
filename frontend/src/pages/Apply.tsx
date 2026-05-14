import React, { useState } from 'react';

import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

export function Apply(): React.ReactElement {
  const initial = getPageData();
  const [firstName, setFirstName] = useState(initial.first_name || '');
  const [lastName, setLastName] = useState(initial.last_name || '');
  const [email, setEmail] = useState(initial.email || '');
  const [roleApplied, setRoleApplied] = useState(initial.role_applied || '');
  const [error, setError] = useState<string | null>(initial.error ?? null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const resp = await postForm('/apply', {
      first_name: firstName,
      last_name: lastName,
      email,
      role_applied: roleApplied,
    });
    setSubmitting(false);
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
    } else {
      setError(resp.error || 'Submission failed.');
    }
  }

  return (
    <div className="wrap">
      <div className="card card-narrow">
        <h1>Apply to College0</h1>
        <p className="subtitle">Submit your application as a student or instructor.</p>

        {error && <div className="error">{error}</div>}
        <form onSubmit={onSubmit}>
          <p className="required-legend">
            Fields marked <span className="req">*</span> are required.
          </p>
          <div className="name-row">
            <div>
              <label htmlFor="first_name">
                First name <span className="req" aria-hidden="true">*</span>
              </label>
              <input
                id="first_name"
                type="text"
                required
                aria-required="true"
                placeholder="e.g. Jane"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="last_name">
                Last name <span className="req" aria-hidden="true">*</span>
              </label>
              <input
                id="last_name"
                type="text"
                required
                aria-required="true"
                placeholder="e.g. Doe"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
          </div>

          <label htmlFor="email">
            Email <span className="req" aria-hidden="true">*</span>
          </label>
          <input
            id="email"
            type="email"
            required
            aria-required="true"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="role_applied">
            I&apos;m applying as a <span className="req" aria-hidden="true">*</span>
          </label>
          <select
            id="role_applied"
            required
            aria-required="true"
            value={roleApplied}
            onChange={(e) => setRoleApplied(e.target.value)}
          >
            <option value="">Choose one…</option>
            <option value="student">Student</option>
            <option value="instructor">Instructor</option>
          </select>

          <button type="submit" className="block" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit application'}
          </button>
          <div className="note">
            After you submit, you will be taken to your <strong>application status</strong> page.
            Your username and temporary password are shown there — bookmark or save that page URL.
            Sign in to change your password and track your application. The registrar must still
            approve you before you can use courses and the rest of the portal.
          </div>
        </form>
      </div>

      <div className="links">
        <a href="/apply/status">Application status</a> | <a href="/login">Log in</a>
      </div>
    </div>
  );
}
