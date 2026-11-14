'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
export function useData<T>(resource: string) {
  const router = useRouter();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`/api/bql/${resource}`, {
          cache: 'no-store',
          signal: controller.signal,
        });
        if (response.status === 401) {
          router.replace('/bql/login');
          return;
        }
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || 'Không tải được dữ liệu.');
        setData(body);
        setError('');
      } catch (e) {
        if (!controller.signal.aborted) {
          setData(null);
          setError(e instanceof Error ? e.message : 'Không tải được dữ liệu.');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [resource, version, router]);
  const refresh = useCallback(() => {
    setLoading(true);
    setVersion((v) => v + 1);
  }, []);
  return { data, error, loading, refresh };
}
export async function mutate(path: string, body: unknown) {
  const response = await fetch(`/api/bql/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Thao tác chưa hoàn tất.');
  return result;
}
