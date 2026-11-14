import { NextRequest, NextResponse } from 'next/server';
import { getConfig, hasAccess } from '@/lib/auth';
import { sameOrigin } from '@/lib/security';
import {
  statsSchema,
  listingSchema,
  deliverySchema,
  reviewSchema,
  reconcileSchema,
  uploadSchema,
} from '@/lib/contracts';
import { z } from 'zod';
type Context = { params: Promise<{ path: string[] }> };
const reply = (body: unknown, status = 200) =>
  NextResponse.json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });

async function handle(request: NextRequest, context: Context) {
  let config;
  try {
    config = getConfig();
  } catch {
    return reply({ error: 'Thiếu cấu hình máy chủ. Xem frontend/.env.example.' }, 503);
  }
  if (!(await hasAccess())) return reply({ error: 'Phiên đăng nhập đã hết hạn.' }, 401);
  const path = (await context.params).path;
  let endpoint: string;
  let body: unknown;
  const imageId = path.length >= 2 && path[0] === 'images' && /^[a-f0-9]{32}$/.test(path[1]);
  const preview = request.method === 'GET' && imageId && path.length === 2;
  if (
    request.method === 'GET' &&
    path.length === 1 &&
    ['stats', 'listings', 'deliveries', 'health'].includes(path[0])
  ) {
    endpoint =
      path[0] === 'health'
        ? '/health'
        : `/${path[0]}?community_id=${encodeURIComponent(config.community)}`;
  } else if (preview) {
    endpoint = `/images/${path[1]}?community_id=${encodeURIComponent(config.community)}`;
  } else if (request.method === 'POST') {
    if (
      !sameOrigin(request.headers.get('origin'), config.origin) ||
      request.headers.get('sec-fetch-site') === 'cross-site'
    )
      return reply({ error: 'Yêu cầu khác nguồn bị từ chối.' }, 403);
    if (!request.headers.get('content-type')?.startsWith('application/json'))
      return reply({ error: 'Yêu cầu JSON.' }, 415);
    if (path.length !== 3 || !/^[A-Za-z0-9-]{1,80}$/.test(path[1]))
      return reply({ error: 'Không có thao tác này.' }, 404);
    try {
      const isUpload = path[0] === 'listings' && path[2] === 'images';
      const limit = isUpload ? 6 * 1024 * 1024 : 8192;
      if (Number(request.headers.get('content-length')) > limit)
        return reply({ error: 'Yêu cầu quá lớn.' }, 413);
      // Bound chunked bodies as well; do not trust Content-Length alone.
      const reader = request.body?.getReader();
      let size = 0;
      const chunks: Uint8Array[] = [];
      if (!reader) return reply({ error: 'Thiếu nội dung yêu cầu.' }, 422);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > limit) {
          await reader.cancel();
          return reply({ error: 'Yêu cầu quá lớn.' }, 413);
        }
        chunks.push(value);
      }
      const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if (path[0] === 'listings' && path[2] === 'review')
        body = { ...reviewSchema.parse(input), community_id: config.community };
      else if (path[0] === 'deliveries' && path[2] === 'reconcile')
        body = reconcileSchema.parse(input);
      else if (isUpload) body = { ...uploadSchema.parse(input), community_id: config.community };
      else if (imageId && path[2] === 'recheck') {
        z.object({}).strict().parse(input);
        body = {};
      } else return reply({ error: 'Không có thao tác này.' }, 404);
      endpoint = `/${path.map(encodeURIComponent).join('/')}`;
      if (imageId) endpoint += `?community_id=${encodeURIComponent(config.community)}`;
      // Reconciliation API has no community parameter: enforce scope before forwarding.
      if (path[0] === 'deliveries') {
        const scope = await fetch(
          `${config.backend}/deliveries?community_id=${encodeURIComponent(config.community)}`,
          {
            headers: { 'X-API-Key': config.adminKey },
            cache: 'no-store',
            signal: AbortSignal.timeout(8000),
          },
        );
        if (!scope.ok)
          return reply({ error: 'Không xác minh được delivery. Chưa thực hiện thay đổi.' }, 502);
        const deliveries = z.array(deliverySchema).parse(await scope.json());
        if (!deliveries.some((row) => row.id === path[1] && row.status === 'unknown'))
          return reply({ error: 'Delivery không thuộc phạm vi hoặc không cần đối soát.' }, 409);
      }
    } catch {
      return reply(
        {
          error:
            'Thông tin không hợp lệ hoặc không xác minh được phạm vi. Kiểm tra lý do và kết nối.',
        },
        422,
      );
    }
  } else return reply({ error: 'Không có API này.' }, 404);
  try {
    const response = await fetch(config.backend + endpoint, {
      method: request.method,
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
      headers: { 'X-API-Key': config.adminKey, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const errors: Record<number, string> = {
        401: 'Backend từ chối khóa quản trị. Kiểm tra cấu hình máy chủ.',
        404: 'Không tìm thấy dữ liệu.',
        409: 'Trạng thái đã thay đổi. Làm mới danh sách trước khi tiếp tục.',
        422: 'Backend từ chối nội dung. Kiểm tra thông tin nhạy cảm, trạng thái và lý do.',
      };
      return reply(
        { error: errors[response.status] || 'Backend không xử lý được yêu cầu.' },
        // Only this BFF's session gate emits 401. Upstream auth is a server setup error.
        response.status === 401 || response.status >= 500 ? 502 : response.status,
      );
    }
    if (preview) {
      if (response.headers.get('content-type') !== 'image/jpeg')
        return reply({ error: 'Ảnh không đúng định dạng.' }, 502);
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength > 4 * 1024 * 1024) return reply({ error: 'Ảnh vượt giới hạn.' }, 502);
      return new NextResponse(bytes, {
        headers: {
          'Content-Type': 'image/jpeg',
          'Cache-Control': 'private, no-store',
          'X-Content-Type-Options': 'nosniff',
          'Content-Security-Policy': "default-src 'none'; sandbox",
        },
      });
    }
    const data = await response.json();
    if (request.method === 'GET') {
      if (path[0] === 'stats') return reply(statsSchema.parse(data));
      if (path[0] === 'listings') return reply(z.array(listingSchema).parse(data));
      if (path[0] === 'deliveries') return reply(z.array(deliverySchema).parse(data));
      return reply({
        status: data.status === 'ok' ? 'ok' : 'unavailable',
        community: config.community,
      });
    }
    return reply(
      path[0] === 'images' || path[2] === 'images'
        ? z.object({ image_id: z.string(), status: z.string() }).parse(data)
        : path[0] === 'listings'
          ? z
              .object({ listing_id: z.string(), status: z.string(), delivery_status: z.string() })
              .parse(data)
          : z.object({ delivery_id: z.string(), status: z.string() }).parse(data),
    );
  } catch {
    return reply(
      {
        error:
          request.method === 'POST'
            ? 'Chưa xác định kết quả. Làm mới và kiểm tra trạng thái trước khi thử lại.'
            : 'Không kết nối được backend hoặc dữ liệu không đúng hợp đồng. Kiểm tra FastAPI.',
      },
      502,
    );
  }
}
export const GET = handle;
export const POST = handle;
