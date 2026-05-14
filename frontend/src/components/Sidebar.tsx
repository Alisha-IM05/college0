import React from 'react';

interface SidebarProps {
  username: string;
  role: string;
  activePage?: string;
}

function SidebarLink({ href, icon, label, active }: { href: string; icon: string; label: string; active?: boolean }) {
  return (
    <a href={href} style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '9px 12px',
      borderRadius: 8,
      marginBottom: 2,
      textDecoration: 'none',
      fontSize: 13.5,
      fontWeight: active ? 600 : 500,
      color: active ? 'white' : 'rgba(255,255,255,.55)',
      background: active ? 'rgba(255,255,255,.12)' : 'transparent',
      transition: 'background .15s, color .15s',
    }}
    onMouseOver={e => { if (!active) { e.currentTarget.style.background = 'rgba(255,255,255,.07)'; e.currentTarget.style.color = 'rgba(255,255,255,.85)'; }}}
    onMouseOut={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(255,255,255,.55)'; }}}
    >
      <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>{icon}</span>
      {label}
    </a>
  );
}

export function Sidebar({ username, role, activePage }: SidebarProps): React.ReactElement {
  return (
    <div style={{
      width: 220,
      background: '#0f1923',
      color: 'white',
      display: 'flex',
      flexDirection: 'column',
      padding: '20px 0',
      position: 'fixed',
      top: 0,
      left: 0,
      height: '100vh',
      zIndex: 100,
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      {/* Logo */}
      <div style={{ padding: '0 16px 20px', borderBottom: '1px solid rgba(255,255,255,.07)' }}>
        <a href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 34, height: 34, background: '#2E4A7A', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>🎓</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'white' }}>College0</div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,.35)', textTransform: 'uppercase', letterSpacing: 1 }}>
              {role === 'student' ? 'Student Portal' : role === 'instructor' ? 'Instructor Portal' : 'Registrar Portal'}
            </div>
          </div>
        </a>
      </div>

      {/* Nav */}
      <nav style={{ padding: '12px 8px', flex: 1, overflowY: 'auto' }}>
        <SidebarLink href="/dashboard" icon="🏠" label="Dashboard" active={activePage === 'dashboard'} />
        <SidebarLink href="/ai/assistant" icon="🤖" label="AI Assistant" active={activePage === 'ai_assistant'} />

        {role === 'student' && <>
          <SidebarLink href="/courses/register" icon="📋" label="Registration" active={activePage === 'register'} />
          <SidebarLink href="/reviews" icon="📝" label="Course Reviews" active={activePage === 'reviews'} />
          <SidebarLink href="/warnings" icon="⚠️" label="Warnings" active={activePage === 'warnings'} />
          <SidebarLink href="/complaints" icon="📢" label="Complaints" active={activePage === 'complaints'} />
          <SidebarLink href="/profile" icon="👤" label="My Profile" active={activePage === 'profile'} />
        </>}

        {role === 'instructor' && <>
          <SidebarLink href="/instructor/courses" icon="📚" label="My Courses" active={activePage === 'instructor_courses'} />
          <SidebarLink href="/warnings" icon="⚠️" label="Warnings" active={activePage === 'warnings'} />
          <SidebarLink href="/complaints" icon="📢" label="Complaints" active={activePage === 'complaints'} />
        </>}

        {role === 'registrar' && <>
          <SidebarLink href="/semester" icon="📅" label="Semester" active={activePage === 'manage'} />
          <SidebarLink href="/courses/create" icon="➕" label="Courses" active={activePage === 'create'} />
          <SidebarLink href="/graduation/resolve" icon="🎓" label="Graduation" active={activePage === 'graduation'} />
          <SidebarLink href="/registrar/applications" icon="📝" label="Applications" active={activePage === 'registrar_applications'} />
          <SidebarLink href="/registrar/users" icon="👥" label="Users" active={activePage === 'registrar_users'} />
          <SidebarLink href="/complaints" icon="📢" label="Complaints" active={activePage === 'complaints'} />
          <SidebarLink href="/taboo" icon="🚫" label="Taboo Words" active={activePage === 'taboo'} />
        </>}
      </nav>
      {/* Quick login buttons */}
<div style={{ padding: '12px 8px', borderTop: '1px solid rgba(255,255,255,.07)', marginTop: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,.3)', letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>Quick Switch</div>
        {[
          { label: 'Registrar', username: 'registrar1', color: '#c0392b' },
          { label: 'Prof Smith', username: 'prof_smith', color: '#27ae60' },
          { label: 'Prof Jones', username: 'prof_jones', color: '#16a34a' },
          { label: 'Student 1', username: 'demo_student1', color: '#2980b9' },
          { label: 'Student 2', username: 'demo_student2', color: '#8e44ad' },
          ].map(q => (
    <form key={q.username} method="POST" action="/login" style={{ marginBottom: 4 }}>
      <input type="hidden" name="username" value={q.username} />
      <input type="hidden" name="password" value="password123" />
      <button type="submit" style={{ width: '100%', background: q.color, color: 'white', border: 'none', borderRadius: 6, padding: '6px 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer', textAlign: 'left', fontFamily: 'Inter, sans-serif' }}>
        {q.label}
      </button>
    </form>
  ))}
</div>

      {/* User footer */}
      <div style={{ padding: '16px', borderTop: '1px solid rgba(255,255,255,.07)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 30, height: 30, background: '#2E4A7A', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 12, flexShrink: 0 }}>
          {username.charAt(0).toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 12, color: 'white', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{username}</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,.4)', textTransform: 'capitalize' }}>{role}</div>
        </div>
        <a href="/logout" title="Logout" style={{ color: 'rgba(255,255,255,.35)', fontSize: 16, textDecoration: 'none', flexShrink: 0 }}>⏻</a>
      </div>
    </div>
  );
}

// Wrapper that adds the sidebar + main content layout
export function PageLayout({ username, role, activePage, children }: {
  username: string;
  role: string;
  activePage?: string;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f0f4f8', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <Sidebar username={username} role={role} activePage={activePage} />
      <div style={{ marginLeft: 220, flex: 1, padding: '2rem' }}>
        {children}
      </div>
    </div>
  );
}
