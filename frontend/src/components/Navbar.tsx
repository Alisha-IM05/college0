import React from 'react';

interface NavbarProps {
  username?: string;
  extras?: React.ReactNode;
}

export function Navbar({ username, extras }: NavbarProps): React.ReactElement {
  return (
    <div className="navbar">
      <h1><a href="/dashboard" style={{ color: 'white', textDecoration: 'none' }}>College0</a></h1>
      <div>
        {extras}
        <a href="/dashboard">Dashboard</a>
        {username && <span style={{ marginLeft: 20 }}>Welcome, {username}</span>}
        <a href="/logout">Logout</a>
      </div>
    </div>
  );
}