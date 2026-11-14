import { NextRequest, NextResponse } from 'next/server';
import { getConfig } from '@/lib/auth';
import { COOKIE_NAME, sameOrigin, cookieSettings } from '@/lib/security';
export async function POST(request: NextRequest) {
  let config;
  try {
    config = getConfig();
  } catch {
    return NextResponse.json({ error: 'Thiếu cấu hình.' }, { status: 503 });
  }
  if (!sameOrigin(request.headers.get('origin'), config.origin))
    return NextResponse.json({ error: 'Yêu cầu bị từ chối.' }, { status: 403 });
  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE_NAME, '', {
    ...cookieSettings(config.origin),
    maxAge: 0,
  });
  response.headers.set('Cache-Control', 'no-store');
  return response;
}
