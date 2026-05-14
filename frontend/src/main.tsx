import React from 'react';
import { createRoot } from 'react-dom/client';

import { getPageData, getPageId } from './lib/data';
import './styles/global.css';

import { Login } from './pages/Login';
import { Apply } from './pages/Apply';
import { ApplyStatus } from './pages/ApplyStatus';
import { AccountBlocked } from './pages/AccountBlocked';
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
import { MyReviews } from './pages/MyReviews';
import { Home } from './pages/Home';
import { Profile } from './pages/Profile';
import { AIAssistant } from './pages/AIAssistant';
import { Suspended } from './pages/Suspended';

function renderPage(pageId: string): React.ReactElement {
  switch (pageId) {
    case 'login':
      return <Login />;
    case 'apply':
      return <Apply />;
    case 'apply_status':
      return <ApplyStatus />;
    case 'account_blocked':
      return <AccountBlocked />;
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
    case 'my_reviews':
      return <MyReviews />;
    case 'home':
      return <Home />;
    case 'profile':
      return <Profile />;
    case 'ai_assistant':
      return <AIAssistant />;
    case 'suspended':
      return <Suspended />;
  }
}

function App(): React.ReactElement {
  const pageId = getPageId();
  return renderPage(pageId);
}

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(<App />);
}