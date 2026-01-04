# Social Outreach Feature Completion Plan

## Current State Analysis

### ✅ What Works
- Discovery (backend + frontend)
- Profile listing (SocialProfilesTable)
- Pipeline status (backend + frontend)
- Backend draft/send endpoints exist (`/api/social/pipeline/draft`, `/api/social/pipeline/send`)

### ❌ What's Broken/Missing

1. **Draft & Sent Tabs** - Show "Coming Soon" placeholders
   - Need: Components to list drafted and sent social profiles
   - Backend: Need endpoints to filter by `source_type='social'` AND `draft_status='drafted'` / `send_status='sent'`
   - Frontend: Need `SocialDraftsTable` and `SocialSentTable` components

2. **Pipeline Reactivation** - Buttons don't respond after discovery
   - Need: Event listeners to refresh pipeline status after discovery completes
   - Need: Reset UI state, re-enable buttons

3. **CSV Export** - Missing from all tables
   - Need: Backend endpoint `/api/prospects/export?source_type=social&status=drafted`
   - Need: Frontend download buttons on all list views

4. **Activity Log** - Missing from social discovery
   - Need: Reuse `ActivityFeed` component from website outreach
   - Need: Filter jobs by `job_type='social_discover'`

5. **Gemini Content Generation** - Doesn't read context
   - Need: Update `app/services/drafting.py` to read website content first
   - Need: Build positioning summary before generating

6. **Gemini Side Chat** - Doesn't exist
   - Need: New component `GeminiChatPanel`
   - Need: Chat API endpoint

## Implementation Order

1. Draft & Sent tabs (highest priority - visible placeholders)
2. Pipeline reactivation (blocks user workflow)
3. CSV export (quick win)
4. Activity log (reuse existing)
5. Gemini context reading (critical for quality)
6. Gemini side chat (enhancement)

