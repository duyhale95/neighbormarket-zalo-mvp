import { z } from 'zod';
export const statsSchema = z.object({
  total: z.number(),
  pending: z.number(),
  approved: z.number(),
  rejected: z.number(),
  sold: z.number(),
  sent: z.number(),
});
export const listingSchema = z.object({
  id: z.string(),
  title: z.string(),
  price_vnd: z.number(),
  condition: z.string(),
  status: z.string(),
  seller_id: z.string(),
  community_id: z.string(),
  created_at: z.string(),
  moderation_flags: z.string(),
});
export const deliverySchema = z.object({
  id: z.string(),
  listing_id: z.string(),
  community_id: z.string(),
  target_group_id: z.string(),
  status: z.string(),
  attempts: z.number(),
  last_error: z.string().nullable(),
  sent_message_id: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Stats = z.infer<typeof statsSchema>;
export type Listing = z.infer<typeof listingSchema>;
export type Delivery = z.infer<typeof deliverySchema>;
export const reviewSchema = z
  .object({ action: z.enum(['approve', 'reject']), reason: z.string().trim().min(1).max(1000) })
  .strict();
export const reconcileSchema = z
  .object({
    decision: z.enum(['sent', 'not_sent']),
    reason: z.string().trim().min(1).max(1000),
    sent_message_id: z.string().trim().min(1).max(200).optional(),
  })
  .strict();
export function flagsOf(value: string): string[] {
  try {
    const result = JSON.parse(value);
    return Array.isArray(result)
      ? result.filter((x): x is string => typeof x === 'string')
      : ['unknown'];
  } catch {
    return ['unknown'];
  }
}
