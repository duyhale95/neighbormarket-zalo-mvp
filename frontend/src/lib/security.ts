import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

export const COOKIE_NAME = 'nm_bql_demo';
export const SESSION_SECONDS = 8 * 3600;
export function cookieSettings(origin: string) {
  return {
    httpOnly: true,
    sameSite: 'strict' as const,
    secure: origin.startsWith('https:'),
    path: '/',
    maxAge: SESSION_SECONDS,
  };
}
export type ServerConfig = {
  backend: string;
  adminKey: string;
  password: string;
  secret: string;
  origin: string;
  community: string;
};

export function validateConfig(env: Record<string, string | undefined>): ServerConfig {
  const { BACKEND_URL, ADMIN_API_KEY, BQL_DEMO_PASSWORD, BQL_SESSION_SECRET, APP_ORIGIN } = env;
  if (
    !BACKEND_URL ||
    !ADMIN_API_KEY?.trim() ||
    !BQL_DEMO_PASSWORD ||
    BQL_DEMO_PASSWORD.trim().length < 12 ||
    BQL_DEMO_PASSWORD.length > 256 ||
    !BQL_SESSION_SECRET ||
    BQL_SESSION_SECRET.length < 32 ||
    !APP_ORIGIN
  ) {
    throw new Error(
      'Cấu hình frontend/.env.local: BACKEND_URL, ADMIN_API_KEY, BQL_DEMO_PASSWORD (12+ ký tự), BQL_SESSION_SECRET (32+ ký tự), APP_ORIGIN.',
    );
  }
  const backend = new URL(BACKEND_URL);
  const origin = new URL(APP_ORIGIN);
  for (const url of [backend, origin]) {
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      url.pathname !== '/'
    ) {
      throw new Error(
        'Cấu hình URL phải là origin HTTP(S), không chứa đường dẫn hoặc thông tin đăng nhập.',
      );
    }
    if (url.protocol === 'http:' && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
      throw new Error('Cấu hình HTTPS cho máy chủ ngoài localhost.');
    }
  }
  const community = env.BQL_COMMUNITY_ID || 'demo';
  if (community.length > 100 || !community.trim())
    throw new Error('Cấu hình BQL_COMMUNITY_ID không hợp lệ.');
  return {
    backend: backend.origin,
    adminKey: ADMIN_API_KEY,
    password: BQL_DEMO_PASSWORD,
    secret: BQL_SESSION_SECRET,
    origin: origin.origin,
    community,
  };
}

export function passwordMatches(input: string, expected: string): boolean {
  const hash = (value: string) => createHash('sha256').update(value).digest();
  return timingSafeEqual(hash(input), hash(expected));
}

export function issueSession(secret: string, now = Math.floor(Date.now() / 1000)): string {
  const body = Buffer.from(
    JSON.stringify({ exp: now + SESSION_SECONDS, nonce: randomBytes(16).toString('hex') }),
  ).toString('base64url');
  return `${body}.${createHmac('sha256', secret).update(body).digest('base64url')}`;
}

export function verifySession(
  value: string | undefined,
  secret: string,
  now = Math.floor(Date.now() / 1000),
): boolean {
  if (!value || value.length > 512) return false;
  const [body, signature, extra] = value.split('.');
  if (!body || !signature || extra) return false;
  const expected = createHmac('sha256', secret).update(body).digest('base64url');
  if (!passwordMatches(signature, expected)) return false;
  try {
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
    return (
      Number.isInteger(payload.exp) &&
      payload.exp > now &&
      payload.exp <= now + SESSION_SECONDS &&
      typeof payload.nonce === 'string'
    );
  } catch {
    return false;
  }
}

export function sameOrigin(origin: string | null, configured: string): boolean {
  return origin === configured;
}
