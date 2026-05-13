import React from 'react';
import { createRoot } from 'react-dom/client';
import { ClerkProvider } from '@clerk/clerk-react';

import { getPageData, getPageId } from './lib/data';
import './styles/global.css';

import { Login } from './pages/Login';
import { Apply } from './pages/Apply';
import { ApplyStatus } from './pages/ApplyStatus';
import { ChangePassword } from './pages/ChangePassword';
import { Dashboard } from './pages/Dashboard';
import { RegistrarApplications } from './pages/RegistrarApplications';
import { RegistrarUsers } from './pages/RegistrarUsers';
import { Warnings } from './pages/Warnings';
import { Complaints } from './pages/Complaints';
import { Reviews } from './pages/Reviews';
import { Taboo } from './pages/Taboo';
import { Manage } from './pages/Manage';
import { Graduation } from './pages/Graduation';
import { Register } from './pages/Register';
import { InstructorCourses } from './pages/InstructorCourses';
import { ClassDetail } from './pages/ClassDetail';
import { Create } from './pages/Create';

const CLERK_PAGES = new Set(['login', 'apply', 'apply_status']);

function renderPage(pageId: string): React.ReactElement {
  switch (pageId) {
    case 'login':
      return <Login />;
    case 'apply':
      return <Apply />;
    case 'apply_status':
      return <ApplyStatus />;
    case 'change_password':
      return <ChangePassword />;
    case 'dashboard':
      return <Dashboard />;
    case 'registrar_applications':
      return <RegistrarApplications />;
    case 'registrar_users':
      return <RegistrarUsers />;
    default:
      return <div className="container"><p>Unknown page: {pageId}</p></div>;
    case 'warnings':
      return <Warnings />;
    case 'complaints':
      return <Complaints />;
    case 'reviews':
      return <Reviews />;
    case 'taboo':
      return <Taboo />;
    case 'manage':
      return <Manage />;
    case 'graduation':
      return <Graduation />;
    case 'register':
      return <Register />;
    case 'instructor_courses':
      return <InstructorCourses />;
    case 'class_detail':
      return <ClassDetail />;
    case 'create':
      return <Create />;
  }
}

function App(): React.ReactElement {
  const pageId = getPageId();
  const data = getPageData();
  const page = renderPage(pageId);

  if (CLERK_PAGES.has(pageId)) {
    const key = data.clerk_publishable_key || '';
    if (!key) {
      return (
        <div className="wrap">
          <div className="card card-narrow">
            <h1>Clerk not configured</h1>
            <p className="muted">
              Set <code>CLERK_PUBLISHABLE_KEY</code> in your <code>.env</code> file
              and restart the server.
            </p>
          </div>
        </div>
      );
    }
    return <ClerkProvider publishableKey={key}>{page}</ClerkProvider>;
  }
  return page;
}

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(<App />);
}
