import React from 'react';

import { getPageData } from '../lib/data';

export function AccountBlocked(): React.ReactElement {
  const data = getPageData();
  const reason = (data.reason as string) || '';

  const title =
    reason === 'terminated' ? 'Account terminated' : reason === 'suspended' ? 'Account suspended' : 'Account inactive';

  const body =
    reason === 'terminated'
      ? 'Your account has been terminated. You cannot access the college system. Please contact the registrar if you have questions.'
      : reason === 'suspended'
        ? 'Your account is suspended. You cannot access the college system until it is reinstated. Please contact the registrar.'
        : 'This account cannot be used to sign in right now. Please contact the registrar.';

  return (
    <div className="login-shell">
      <div className="login-box">
        <h1>{title}</h1>
        <p className="subtitle">{body}</p>
        <a className="cta" href="/login">
          Back to login
        </a>
      </div>
    </div>
  );
}
