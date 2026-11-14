'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Eye, EyeOff, LockKeyhole } from 'lucide-react';
import { Notice } from './shared';
export function LoginForm({ setupError }: { setupError: string }) {
  const router = useRouter();
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const form = new FormData(e.currentTarget);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: form.get('password') }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      router.replace('/bql');
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể đăng nhập. Thử lại sau.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="login-form">
      {setupError && <Notice message={setupError} />}
      <label htmlFor="password">Mật khẩu BQL Demo</label>
      <div className="password-field">
        <LockKeyhole size={18} />
        <input
          id="password"
          name="password"
          type={show ? 'text' : 'password'}
          required
          maxLength={256}
          autoComplete="current-password"
          disabled={!!setupError}
          aria-describedby="login-help"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <p id="login-help" className="field-help">
        Dùng mật khẩu do người vận hành cấu hình cho phiên demo.
      </p>
      {error && <Notice message={error} />}
      <button className="button button-navy" type="submit" disabled={busy || !!setupError}>
        {busy ? 'Đang xác thực…' : 'Vào không gian BQL'}
        <ArrowRight size={18} />
      </button>
      <p className="login-security">
        <LockKeyhole size={13} /> Phiên đăng nhập được bảo vệ · Hết hạn sau 8 giờ
      </p>
    </form>
  );
}
