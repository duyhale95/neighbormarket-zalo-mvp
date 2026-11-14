import { z } from 'zod';
export const statsSchema = z.object({
  total: z.number(),
  pending: z.number(),
  approved: z.number(),
  rejected: z.number(),
  sold: z.number(),
  sent: z.number(),
});
export const moderationSchema = z.object({
  risk_score: z.number().min(0).max(1).nullable(),
  risk_level: z.enum(['low', 'attention', 'high']),
  categories: z.array(z.string()),
  reason: z.string(),
  policy_version: z.string(),
  model_version: z.string(),
  requires_review: z.literal(true),
  ai_status: z.enum(['not_requested', 'unavailable', 'advisory']),
  score_calibrated: z.literal(false),
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
  source_channel: z.enum(['legacy', 'deplao', 'mock']).optional(),
  moderation: moderationSchema.nullable().optional(),
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
  transport_mode: z.enum(['mock', 'deplao', 'unverified', 'manual']).optional(),
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
