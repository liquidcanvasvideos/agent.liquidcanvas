/**
 * API client for new backend architecture
 */
// Remove /v1 if present - new backend uses /api directly
const envBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api'
const API_BASE = envBase.replace('/api/v1', '/api').replace('/v1', '')

// Get auth token from localStorage
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('auth_token')
}

// Authenticated fetch wrapper
async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // Note: No console warning if token is missing - auth is optional for some endpoints
  
  const response = await fetch(url, {
    ...options,
    headers,
  })
  
  // If unauthorized, redirect to login (only if auth was actually required)
  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token')
      // Only redirect if we actually sent a token (meaning auth was expected)
      if (token) {
        window.location.href = '/login'
      }
    }
    throw new Error('Unauthorized')
  }
  
  return response
}

// Types
export interface Prospect {
  id: string
  domain: string
  page_url?: string
  page_title?: string
  contact_email?: string
  contact_method?: string
  da_est?: number
  score?: number
  outreach_status: string
  last_sent?: string
  followups_sent: number
  draft_subject?: string
  draft_body?: string
  dataforseo_payload?: any
  hunter_payload?: any
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  job_type: string
  status: string
  params?: any
  result?: any
  error_message?: string
  created_at: string
  updated_at: string
}

export interface EmailLog {
  id: string
  prospect_id: string
  subject: string
  body: string
  response?: any
  sent_at: string
}

export interface ProspectListResponse {
  prospects: Prospect[]
  total: number
  skip: number
  limit: number
}

// Jobs API
export async function createDiscoveryJob(
  keywords: string,
  locations?: string[],
  maxResults?: number,
  categories?: string[]
): Promise<Job> {
  // Add cache-busting timestamp to ensure fresh requests
  const timestamp = Date.now()
  const url = `${API_BASE}/jobs/discover?_t=${timestamp}`
  
  const res = await authenticatedFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify({
      keywords: keywords || '',
      locations: locations || [],
      max_results: maxResults || 100,
      categories: categories || [],
    }),
  })
  
  if (!res.ok) {
    let errorDetail = 'Failed to create discovery job'
    try {
      const errorData = await res.json()
      errorDetail = errorData.detail || errorData.message || errorDetail
    } catch {
      // If JSON parsing fails, use status text
      errorDetail = res.statusText || errorDetail
    }
    throw new Error(errorDetail)
  }
  
  return res.json()
}

export async function createEnrichmentJob(
  prospectIds?: string[],
  maxProspects?: number
): Promise<{ job_id: string; status: string; message?: string }> {
  const params = new URLSearchParams()
  if (prospectIds) params.append('prospect_ids', prospectIds.join(','))
  if (maxProspects) params.append('max_prospects', maxProspects.toString())
  
  const res = await authenticatedFetch(`${API_BASE}/prospects/enrich?${params}`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create enrichment job' }))
    throw new Error(error.detail || 'Failed to create enrichment job')
  }
  return res.json()
}

export async function createScoringJob(
  prospectIds?: string[],
  maxProspects?: number
): Promise<Job> {
  const params = new URLSearchParams()
  if (prospectIds) params.append('prospect_ids', prospectIds.join(','))
  if (maxProspects) params.append('max_prospects', maxProspects.toString())
  
  const res = await authenticatedFetch(`${API_BASE}/jobs/score?${params}`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create scoring job' }))
    throw new Error(error.detail || 'Failed to create scoring job')
  }
  return res.json()
}

export async function createSendJob(
  prospectIds?: string[],
  maxProspects?: number,
  autoSend?: boolean
): Promise<Job> {
  const params = new URLSearchParams()
  if (prospectIds) params.append('prospect_ids', prospectIds.join(','))
  if (maxProspects) params.append('max_prospects', maxProspects.toString())
  if (autoSend !== undefined) params.append('auto_send', autoSend.toString())
  
  const res = await authenticatedFetch(`${API_BASE}/jobs/send?${params}`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create send job' }))
    throw new Error(error.detail || 'Failed to create send job')
  }
  return res.json()
}

export async function createFollowupJob(
  daysSinceSent?: number,
  maxFollowups?: number,
  maxProspects?: number
): Promise<Job> {
  const params = new URLSearchParams()
  if (daysSinceSent) params.append('days_since_sent', daysSinceSent.toString())
  if (maxFollowups) params.append('max_followups', maxFollowups.toString())
  if (maxProspects) params.append('max_prospects', maxProspects.toString())
  
  const res = await authenticatedFetch(`${API_BASE}/jobs/followup?${params}`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create follow-up job' }))
    throw new Error(error.detail || 'Failed to create follow-up job')
  }
  return res.json()
}

export async function getJobStatus(jobId: string): Promise<Job> {
  const res = await authenticatedFetch(`${API_BASE}/jobs/${jobId}/status`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get job status' }))
    throw new Error(error.detail || 'Failed to get job status')
  }
  return res.json()
}

export async function listJobs(skip = 0, limit = 50): Promise<Job[]> {
  const res = await authenticatedFetch(`${API_BASE}/jobs?skip=${skip}&limit=${limit}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list jobs' }))
    throw new Error(error.detail || 'Failed to list jobs')
  }
  return res.json()
}

// Prospects API
export async function listProspects(
  skip = 0,
  limit = 50,
  status?: string,
  minScore?: number,
  hasEmail?: boolean
): Promise<ProspectListResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  if (status) params.append('status', status)
  if (minScore !== undefined) params.append('min_score', minScore.toString())
  if (hasEmail !== undefined) params.append('has_email', hasEmail.toString())
  // Cache busting
  params.append('_t', Date.now().toString())
  
  const res = await authenticatedFetch(`${API_BASE}/prospects?${params}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list prospects' }))
    throw new Error(error.detail || 'Failed to list prospects')
  }
  return res.json()
}

export async function getProspect(prospectId: string): Promise<Prospect> {
  const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get prospect' }))
    throw new Error(error.detail || 'Failed to get prospect')
  }
  return res.json()
}

export async function composeEmail(prospectId: string): Promise<{
  prospect_id: string
  subject: string
  body: string
  draft_saved: boolean
}> {
  const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}/compose`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to compose email' }))
    throw new Error(error.detail || 'Failed to compose email')
  }
  return res.json()
}

export async function sendEmail(
  prospectId: string,
  subject?: string,
  body?: string
): Promise<{
  prospect_id: string
  email_log_id: string
  sent_at: string
  success: boolean
  message_id?: string
}> {
  const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}/send`, {
    method: 'POST',
    body: JSON.stringify({
      subject,
      body,
    }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to send email' }))
    throw new Error(error.detail || 'Failed to send email')
  }
  return res.json()
}

// Stats API (will need to be added to backend)
export interface Stats {
  total_prospects: number
  prospects_with_email: number
  prospects_pending: number
  prospects_sent: number
  prospects_replied: number
  total_jobs: number
  jobs_running: number
  jobs_completed: number
  jobs_failed: number
}

export async function getStats(): Promise<Stats | null> {
  try {
    // Fetch all data in parallel
    const [allProspects, jobs, prospectsWithEmail] = await Promise.all([
      listProspects(0, 1000).catch(() => ({ prospects: [], total: 0, skip: 0, limit: 0 })),
      listJobs(0, 100).catch(() => []),
      listProspects(0, 1000, undefined, undefined, true).catch(() => ({ prospects: [], total: 0, skip: 0, limit: 0 })),
    ])
    
    // Count prospects by status
    let prospects_pending = 0
    let prospects_sent = 0
    let prospects_replied = 0
    
    allProspects.prospects.forEach(p => {
      if (p.outreach_status === 'pending') prospects_pending++
      if (p.outreach_status === 'sent') prospects_sent++
      if (p.outreach_status === 'replied') prospects_replied++
    })
    
    const stats: Stats = {
      total_prospects: allProspects.total,
      prospects_with_email: prospectsWithEmail.total,
      prospects_pending,
      prospects_sent,
      prospects_replied,
      total_jobs: jobs.length,
      jobs_running: jobs.filter(j => j.status === 'running').length,
      jobs_completed: jobs.filter(j => j.status === 'completed').length,
      jobs_failed: jobs.filter(j => j.status === 'failed').length,
    }
    
    return stats
  } catch (error) {
    console.error('Failed to get stats:', error)
    return null
  }
}

// Auth API
export async function login(username: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Login failed' }))
    throw new Error(error.detail || 'Login failed')
  }
  return res.json()
}

// Settings API
export interface ServiceStatus {
  name: string
  enabled: boolean
  configured: boolean
  status: 'connected' | 'disconnected' | 'error' | 'not_configured' | 'unknown'
  message?: string
  last_tested?: string
}

export interface SettingsResponse {
  services: Record<string, ServiceStatus>
  api_keys: Record<string, boolean>
}

export async function getSettings(): Promise<SettingsResponse> {
  const res = await authenticatedFetch(`${API_BASE}/settings/services/status`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get settings' }))
    throw new Error(error.detail || 'Failed to get settings')
  }
  return res.json()
}

export async function testService(serviceName: string): Promise<{
  success: boolean
  status: string
  message: string
  test_result?: any
}> {
  const res = await authenticatedFetch(`${API_BASE}/settings/services/${encodeURIComponent(serviceName)}/test`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Test failed' }))
    throw new Error(error.detail || 'Test failed')
  }
  return res.json()
}

export async function getAPIKeysStatus(): Promise<Record<string, boolean>> {
  const res = await authenticatedFetch(`${API_BASE}/settings/api-keys`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get API keys status' }))
    throw new Error(error.detail || 'Failed to get API keys status')
  }
  return res.json()
}
