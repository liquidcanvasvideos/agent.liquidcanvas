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

/**
 * Authenticated fetch wrapper with robust error handling and SSL support
 * Handles network errors, SSL issues, and undefined responses gracefully
 */
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
  
  try {
    // Attempt fetch with error handling
    const response = await fetch(url, {
      ...options,
      headers,
      // Add credentials for CORS if needed (but don't require SSL verification in browser)
      credentials: 'omit', // Browser handles SSL automatically, but we don't send cookies
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
  } catch (error: any) {
    // Handle network errors, SSL errors, and other fetch failures
    const errorMessage = error?.message || String(error)
    
    // Log clear error message for debugging
    if (errorMessage.includes('Failed to fetch') || 
        errorMessage.includes('NetworkError') ||
        errorMessage.includes('ERR_CONNECTION_REFUSED') ||
        errorMessage.includes('ERR_SSL')) {
      console.error('❌ Network/SSL Error:', {
        url,
        error: errorMessage,
        message: 'Backend may be unreachable or SSL certificate issue. App will continue running.',
      })
    } else {
      console.error('❌ Fetch Error:', {
        url,
        error: errorMessage,
      })
    }
    
    // Re-throw to allow caller to handle, but app won't crash
    throw error
  }
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
  try {
    const res = await authenticatedFetch(`${API_BASE}/jobs?skip=${skip}&limit=${limit}`)
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to list jobs' }))
      throw new Error(error.detail || 'Failed to list jobs')
    }
    const data = await res.json()
    
    // Validate response is an array
    if (!Array.isArray(data)) {
      console.warn('⚠️ listJobs: Response is not an array. Got:', typeof data, data)
      // Try to extract array from response
      if (data && typeof data === 'object') {
        const jobs = data.jobs || data.data || data.items || []
        if (Array.isArray(jobs)) {
          return jobs
        }
      }
      return [] // Return empty array instead of crashing
    }
    
    return data
  } catch (error: any) {
    console.error('❌ Error in listJobs:', error)
    // Return empty array to prevent app crash
    return []
  }
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
  const response = await res.json()
  
  // Handle new response format: {success: bool, data: {prospects, total, skip, limit}, error: null | string}
  if (response.success && response.data) {
    return response.data
  }
  
  // Fallback for old format or error case
  if (response.error) {
    throw new Error(response.error)
  }
  
  // If response doesn't match expected format, return empty structure
  console.warn('Unexpected response format from /api/prospects:', response)
  return { prospects: [], total: 0, skip: 0, limit: 0 }
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
    // Fetch all data in parallel with defensive error handling
    const [allProspects, jobs, prospectsWithEmail] = await Promise.all([
      listProspects(0, 1000).catch(() => ({ prospects: [], total: 0, skip: 0, limit: 0 })),
      listJobs(0, 100).catch(() => []),
      listProspects(0, 1000, undefined, undefined, true).catch(() => ({ prospects: [], total: 0, skip: 0, limit: 0 })),
    ])
    
    // Log actual API responses for debugging (only in development)
    if (process.env.NODE_ENV !== 'production') {
      console.log('🔍 getStats - allProspects response:', allProspects)
      console.log('🔍 getStats - prospectsWithEmail response:', prospectsWithEmail)
      console.log('🔍 getStats - jobs response:', jobs)
    }
    
    // Defensive guard: Ensure all inputs are defined before processing
    if (!allProspects && !prospectsWithEmail && !jobs) {
      console.warn('⚠️ getStats: All API responses are undefined/null')
      return null
    }
    
    // Safely extract prospects array with multiple fallbacks
    let allProspectsList: any[] = []
    if (allProspects) {
      if (Array.isArray(allProspects.prospects)) {
        allProspectsList = allProspects.prospects
      } else if (allProspects.data && Array.isArray(allProspects.data.prospects)) {
        allProspectsList = allProspects.data.prospects
      } else if (Array.isArray(allProspects)) {
        allProspectsList = allProspects
      }
    }
    
    let prospectsWithEmailList: any[] = []
    if (prospectsWithEmail) {
      if (Array.isArray(prospectsWithEmail.prospects)) {
        prospectsWithEmailList = prospectsWithEmail.prospects
      } else if (prospectsWithEmail.data && Array.isArray(prospectsWithEmail.data.prospects)) {
        prospectsWithEmailList = prospectsWithEmail.data.prospects
      } else if (Array.isArray(prospectsWithEmail)) {
        prospectsWithEmailList = prospectsWithEmail
      }
    }
    
    // Safely extract totals with defensive checks
    const allProspectsTotal = (allProspects?.total ?? allProspects?.data?.total ?? 0) || 0
    const prospectsWithEmailTotal = (prospectsWithEmail?.total ?? prospectsWithEmail?.data?.total ?? 0) || 0
    
    // Count prospects by status - defensive forEach guard
    let prospects_pending = 0
    let prospects_sent = 0
    let prospects_replied = 0
    
    // Critical defensive guard: Never call forEach on undefined/null
    // Use safe array check and try-catch for maximum safety
    if (Array.isArray(allProspectsList) && allProspectsList.length > 0) {
      try {
        allProspectsList.forEach((p: any) => {
          // Additional safety check for each item
          if (p && typeof p === 'object' && p.outreach_status) {
            if (p.outreach_status === 'pending') prospects_pending++
            if (p.outreach_status === 'sent') prospects_sent++
            if (p.outreach_status === 'replied') prospects_replied++
          }
        })
      } catch (forEachError) {
        console.error('⚠️ Error in forEach loop (likely from devtools hook or invalid data):', forEachError)
        // Continue with zero counts rather than failing - app stays running
      }
    } else if (allProspectsList !== null && allProspectsList !== undefined) {
      // Log warning if we expected an array but got something else
      console.warn('⚠️ getStats: allProspectsList is not a valid array:', typeof allProspectsList, allProspectsList)
    }
    
    // Safely handle jobs array - defensive guard
    let jobsArray: any[] = []
    if (jobs) {
      if (Array.isArray(jobs)) {
        jobsArray = jobs
      } else if (jobs.data && Array.isArray(jobs.data)) {
        jobsArray = jobs.data
      }
    }
    
    // Defensive filter operations with safe array checks
    let jobs_running = 0
    let jobs_completed = 0
    let jobs_failed = 0
    
    if (Array.isArray(jobsArray) && jobsArray.length > 0) {
      try {
        jobs_running = jobsArray.filter((j: any) => j && typeof j === 'object' && j.status === 'running').length
        jobs_completed = jobsArray.filter((j: any) => j && typeof j === 'object' && j.status === 'completed').length
        jobs_failed = jobsArray.filter((j: any) => j && typeof j === 'object' && j.status === 'failed').length
      } catch (filterError) {
        console.error('⚠️ Error in filter operations:', filterError)
        // Continue with zero counts - app stays running
      }
    }
    
    const stats: Stats = {
      total_prospects: allProspectsTotal,
      prospects_with_email: prospectsWithEmailTotal,
      prospects_pending,
      prospects_sent,
      prospects_replied,
      total_jobs: jobsArray.length || 0,
      jobs_running,
      jobs_completed,
      jobs_failed,
    }
    
    return stats
  } catch (error) {
    console.error('Failed to get stats:', error)
    // Return null instead of throwing to prevent crashes from devtools hooks
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
