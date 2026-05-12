import React, { useEffect, useState } from 'react';
import {
  SignedIn,
  SignedOut,
  SignUp,
  useAuth,
  useUser,
} from '@clerk/clerk-react';

import { getPageData } from '../lib/data';
import { postForm, navigate } from '../lib/api';

export function Apply(): React.ReactElement {
  const initial = getPageData();
  return (
    <div className="wrap">
      <div className="card card-narrow">
        <h1>Apply to College0</h1>
        <p className="subtitle">Submit your application as a student or instructor.</p>

        <SignedOut>
          <p className="muted">
            Step 1 — sign up or sign in with Clerk so we can keep track of your application:
          </p>
          <div style={{ marginTop: 12, marginBottom: 12 }}>
            <SignUp
              routing="hash"
              signInUrl="/apply"
              forceRedirectUrl="/apply"
            />
          </div>
        </SignedOut>

        <SignedIn>
          <ApplyForm initialError={initial.error} initialValues={initial} />
        </SignedIn>
      </div>

      <div className="links">
        <a href="/apply/status">Check application status</a> | <a href="/">Already have an account? Log in</a>
      </div>
    </div>
  );
}

interface FormProps {
  initialError?: string;
  initialValues: ReturnType<typeof getPageData>;
}

function ApplyForm({ initialError, initialValues }: FormProps): React.ReactElement {
  const { user } = useUser();
  const { getToken, signOut } = useAuth();

  const [firstName, setFirstName] = useState(initialValues.first_name || '');
  const [lastName, setLastName] = useState(initialValues.last_name || '');
  const [email, setEmail] = useState(initialValues.email || '');
  const [roleApplied, setRoleApplied] = useState(initialValues.role_applied || '');
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      if (!firstName && user.firstName) setFirstName(user.firstName);
      if (!lastName && user.lastName) setLastName(user.lastName);
      if (!email && user.primaryEmailAddress?.emailAddress) {
        setEmail(user.primaryEmailAddress.emailAddress);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const token = await getToken();
    const resp = await postForm(
      '/apply',
      {
        first_name: firstName,
        last_name: lastName,
        email,
        role_applied: roleApplied,
      },
      { bearerToken: token },
    );
    setSubmitting(false);
    if (resp.ok && resp.redirect) {
      navigate(resp.redirect);
    } else {
      setError(resp.error || 'Submission failed.');
    }
  }

  return (
    <>
      <p className="muted">
        Signed in via Clerk
        {' '}·{' '}
        <a
          href="#"
          onClick={async (e) => {
            e.preventDefault();
            await signOut();
            window.location.reload();
          }}
        >
          Sign out
        </a>
      </p>
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <p className="muted">Step 2 — tell us who you are and what you'd like to apply for:</p>
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

        <label htmlFor="email">Email (from your Clerk account)</label>
        <input id="email" type="email" readOnly value={email} />

        <label htmlFor="role_applied">
          I'm applying as a <span className="req" aria-hidden="true">*</span>
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
          The registrar will review your application. Once it's approved you'll be issued
          a username and a temporary password — <a href="/apply/status">check your status here</a>.
        </div>
      </form>
    </>
  );
}
