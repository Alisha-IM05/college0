import React from 'react';

interface NavbarProps {
  username?: string;
  extras?: React.ReactNode;
}

export function Navbar({ username, extras }: NavbarProps): React.ReactElement {
  return (
    <div className="navbar">
      <h1>College0</h1>
      <div>
        {extras}
        {username && <span style={{ marginLeft: 20 }}>Welcome, {username}</span>}
        <a href="/logout">Logout</a>
      </div>
    </div>
  );
}
