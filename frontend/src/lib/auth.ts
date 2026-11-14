import 'server-only';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { COOKIE_NAME, validateConfig, verifySession } from './security';

export function getConfig() {
  return validateConfig(process.env);
}
export async function hasAccess(): Promise<boolean> {
  try {
    return verifySession((await cookies()).get(COOKIE_NAME)?.value, getConfig().secret);
  } catch {
    return false;
  }
}
export async function requireAccess() {
  if (!(await hasAccess())) redirect('/bql/login');
}
