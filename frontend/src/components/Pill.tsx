import React from 'react';

interface PillProps {
  status: string;
  variant?: 'p' | 's';
}

export function Pill({ status, variant = 'p' }: PillProps): React.ReactElement {
  return <span className={`pill ${variant}-${status}`}>{status.toUpperCase()}</span>;
}
