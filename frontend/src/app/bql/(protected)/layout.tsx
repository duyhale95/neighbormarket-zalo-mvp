import { requireAccess, getConfig } from '@/lib/auth';
import { ConsoleShell } from '@/components/bql/shell';
export const dynamic = 'force-dynamic';
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  await requireAccess();
  return <ConsoleShell community={getConfig().community}>{children}</ConsoleShell>;
}
