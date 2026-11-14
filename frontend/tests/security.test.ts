import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  issueSession,
  verifySession,
  sameOrigin,
  passwordMatches,
  validateConfig,
  cookieSettings,
} from '../src/lib/security';
const secret = 'test-signing-secret-at-least-32-characters';

test('cookies are HttpOnly, SameSite strict and Secure on HTTPS', () => {
  assert.deepEqual(cookieSettings('https://demo.example'), {
    httpOnly: true,
    sameSite: 'strict',
    secure: true,
    path: '/',
    maxAge: 8 * 3600,
  });
  assert.equal(cookieSettings('http://127.0.0.1:3000').secure, false);
});
test('signed sessions reject tampering, wrong secret and expiry', () => {
  const token = issueSession(secret, 1000);
  assert.equal(verifySession(token, secret, 1001), true);
  assert.equal(verifySession(token + 'x', secret, 1001), false);
  assert.equal(verifySession(token, secret + 'x', 1001), false);
  assert.equal(verifySession(token, secret, 1000 + 8 * 3600), false);
  assert.equal(verifySession(undefined, secret), false);
});
test('origin protection fails closed and passwords are compared safely', () => {
  assert.equal(sameOrigin('https://evil.example', 'http://127.0.0.1:3000'), false);
  assert.equal(sameOrigin(null, 'http://127.0.0.1:3000'), false);
  assert.equal(sameOrigin('http://127.0.0.1:3000', 'http://127.0.0.1:3000'), true);
  assert.equal(passwordMatches('correct password', 'correct password'), true);
  assert.equal(passwordMatches('wrong', 'correct password'), false);
});
test('missing credentials and unsafe server configuration fail closed', () => {
  assert.throws(() => validateConfig({}), /Cấu hình/);
  const env = {
    ADMIN_API_KEY: 'test-admin',
    BQL_DEMO_PASSWORD: 'test-long-password',
    BQL_SESSION_SECRET: secret,
    BACKEND_URL: 'http://127.0.0.1:8000',
    APP_ORIGIN: 'http://127.0.0.1:3000',
  };
  assert.equal(validateConfig(env).community, 'demo');
  assert.throws(() => validateConfig({ ...env, BACKEND_URL: 'https://user:pass@example.com' }));
  assert.throws(() => validateConfig({ ...env, APP_ORIGIN: 'http://example.com' }));
});
