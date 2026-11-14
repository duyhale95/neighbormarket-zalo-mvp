import { test } from 'node:test';
import assert from 'node:assert/strict';
import { listingSchema, deliverySchema } from '../src/lib/contracts';

const oldListing = {
  id: 'NM-OLD',
  title: 'Ghế',
  price_vnd: 800000,
  condition: 'cũ',
  status: 'pending',
  seller_id: 'seller',
  community_id: 'demo',
  created_at: '2026-11-14 00:00:00',
  moderation_flags: '[]',
};
test('old listing responses remain valid; optional report and source survive BFF validation', () => {
  assert.equal(listingSchema.parse(oldListing).id, 'NM-OLD');
  const moderation = {
    risk_score: null,
    risk_level: 'attention',
    categories: ['suspicious'],
    reason: 'Có yêu cầu đặt cọc trước; cần BQL kiểm tra',
    policy_version: 'nm-human-review-v1',
    model_version: 'rules-only',
    requires_review: true,
    ai_status: 'not_requested',
    score_calibrated: false,
  };
  const current = listingSchema.parse({ ...oldListing, source_channel: 'deplao', moderation });
  assert.equal(current.source_channel, 'deplao');
  assert.equal(current.moderation?.requires_review, true);
  assert.equal(current.moderation?.risk_score, null);
});
test('delivery evidence is optional for legacy responses and distinguishes mock receipts', () => {
  const old = {
    id: 'id',
    listing_id: 'NM-OLD',
    community_id: 'demo',
    target_group_id: 'group',
    status: 'sent',
    attempts: 1,
    last_error: null,
    sent_message_id: 'mock-1',
    created_at: 'now',
    updated_at: 'now',
  };
  assert.equal(deliverySchema.parse(old).transport_mode, undefined);
  assert.equal(deliverySchema.parse({ ...old, transport_mode: 'mock' }).transport_mode, 'mock');
});
