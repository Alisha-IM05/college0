export type Role = 'student' | 'instructor' | 'registrar' | null;

export interface Semester {
  id: number;
  name: string;
  current_period: string;
}

export interface StudentSummary {
  id: number;
  username: string;
  email: string;
  semester_gpa: number | null;
  cumulative_gpa: number | null;
  credits_earned: number | null;
  honor_roll: number | null;
  status: string | null;
}

export interface GradeRow {
  letter_grade: string;
  numeric_value: number;
  course_name: string;
  semester_name: string;
}

export interface ApplicationRow {
  id: number;
  name: string;
  email: string;
  role_applied: 'student' | 'instructor';
  status: 'pending' | 'approved' | 'rejected';
  submitted_at: string;
  reviewed_at: string | null;
  user_id?: number | null;
  issued_username?: string | null;
  must_change_password?: number | null;
  issued_temp_password?: string | null;
}

export interface UserRow {
  id: number;
  username: string;
  email: string;
  role: string;
  status: 'active' | 'suspended' | 'terminated';
  created_at: string;
}

export interface IssuedCredentials {
  user_id?: number;
  username?: string;
  temp_password?: string;
  role?: string;
  email?: string;
  error?: string;
  rejected?: boolean;
  message?: string;
  /** Set when registrar approves an applicant who already received credentials at submit. */
  account_activated?: boolean;
}

export interface PageData {
  page: string;
  username?: string;
  role?: Role;
  error?: string;
  message?: string;

  // login
  first_name?: string;
  last_name?: string;
  email?: string;
  role_applied?: 'student' | 'instructor' | '';

  // dashboard
  semester?: Semester | null;
  student_data?: StudentSummary | null;
  grades?: GradeRow[];

  // apply / status
  mail_configured?: boolean;
  applications?: ApplicationRow[];
  token?: string;
  missing_token?: boolean;
  logged_in?: boolean;
  reason?: string;

  // registrar
  pending?: ApplicationRow[];
  reviewed?: ApplicationRow[];
  issued?: IssuedCredentials | null;
  mail_configured?: boolean;
  users?: UserRow[];

  // change password
  must_change?: boolean;
}

let cached: PageData | null = null;

export function getPageData(): PageData {
  if (cached) return cached;
  const el = document.getElementById('__data');
  if (!el || !el.textContent) {
    cached = { page: '' };
    return cached;
  }
  try {
    cached = JSON.parse(el.textContent) as PageData;
  } catch {
    cached = { page: '' };
  }
  return cached;
}

export function getPageId(): string {
  const root = document.getElementById('root');
  return root?.getAttribute('data-page') ?? '';
}
