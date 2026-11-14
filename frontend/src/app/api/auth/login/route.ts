import { NextRequest, NextResponse } from 'next/server';
import { getConfig } from '@/lib/auth';
import {
  COOKIE_NAME,
  issueSession,
  passwordMatches,
  sameOrigin,
  cookieSettings,
} from '@/lib/security';

// Demo-only, process-local throttle. Production requires a shared rate limiter and individual accounts.
let failures = 0;
let blockedUntil = 0;
export async function POST(request: NextRequest) {
  let config;
  try {
    config = getConfig();
  } catch {
    return NextResponse.json(
      { error: 'Chưa cấu hình đăng nhập. Kiểm tra frontend/.env.local theo README.' },
      { status: 503 },
    );
  }
  if (
    !sameOrigin(request.headers.get('origin'), config.origin) ||
    request.headers.get('sec-fetch-site') === 'cross-site'
  ) {
    return NextResponse.json({ error: 'Yêu cầu khác nguồn bị từ chối.' }, { status: 403 });
  }
  if (!request.headers.get('content-type')?.startsWith('application/json'))
    return NextResponse.json({ error: 'Yêu cầu JSON.' }, { status: 415 });
  if (Date.now() < blockedUntil)
    return NextResponse.json(
      { error: 'Đã thử quá nhiều lần. Thử lại sau 5 phút.' },
      { status: 429 },
    );
  try {
    if (Number(request.headers.get('content-length')) > 2048) throw new Error();
    const body = await request.json();
    if (
      typeof body.password !== 'string' ||
      body.password.length > 256 ||
      !passwordMatches(body.password, config.password)
    ) {
      failures += 1;
      if (failures >= 5) {
        blockedUntil = Date.now() + 300000;
        failures = 0;
      }
      return NextResponse.json({ error: 'Mật khẩu chưa đúng.' }, { status: 401 });
    }
    failures = 0;
    const response = NextResponse.json({ ok: true }, { headers: { 'Cache-Control': 'no-store' } });
    response.cookies.set(COOKIE_NAME, issueSession(config.secret), cookieSettings(config.origin));
    return response;
  } catch {
    return NextResponse.json({ error: 'Thông tin đăng nhập không hợp lệ.' }, { status: 400 });
  }
}
