import React from 'react';

interface BannerProps {
  kind: 'error' | 'info' | 'note' | 'warn';
  children: React.ReactNode;
}

const CLASS_MAP: Record<BannerProps['kind'], string> = {
  error: 'banner-error',
  info: 'banner-info',
  note: 'note',
  warn: 'warn-note',
};

export function Banner({ kind, children }: BannerProps): React.ReactElement {
  return <div className={CLASS_MAP[kind]}>{children}</div>;
}
