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
 * ALWAYS throws meaningful errors with stack traces
 */
async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const startTime = Date.now()
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  try {
    console.log(`📤 [FETCH] ${options.method || 'GET'} ${url}`)
    console.log(`📥 [FETCH] Input - headers: ${JSON.stringify(Object.keys(headers))}, hasBody: ${!!options.body}`)
    
    // Attempt fetch with error handling
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'omit',
    })
    
    const fetchTime = Date.now() - startTime
    console.log(`⏱️  [FETCH] Response received in ${fetchTime}ms - status: ${response.status}`)
    
    // If unauthorized, redirect to login (only if auth was actually required)
    if (response.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token')
        if (token) {
          window.location.href = '/login'
        }
      }
      const error = new Error(`Unauthorized: ${url}`)
      console.error(`❌ [FETCH] Unauthorized: ${url}`)
      throw error
    }
    
    if (!response.ok) {
      // Try to get error details from response
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`
      try {
        const errorData = await response.clone().json().catch(() => null)
        if (errorData) {
          errorDetail = errorData.error || errorData.detail || errorData.message || errorDetail
        }
      } catch {
        // If JSON parsing fails, use status text
      }
      
      const error = new Error(`Fetch failed: ${errorDetail}`)
      console.error(`❌ [FETCH] Request failed: ${url}`, {
        status: response.status,
        statusText: response.statusText,
        error: errorDetail,
        stack: new Error().stack
      })
      throw error
    }
    
    console.log(`✅ [FETCH] Success: ${url}`)
    return response
  } catch (error: any) {
    const fetchTime = Date.now() - startTime
    const errorMessage = error?.message || String(error)
    const errorStack = error?.stack || new Error().stack
    
    // Create meaningful error with full context
    const enhancedError = new Error(`Fetch error for ${url}: ${errorMessage}`)
    enhancedError.stack = errorStack
    
    // Log with full context
    if (errorMessage.includes('Failed to fetch') || 
        errorMessage.includes('NetworkError') ||
        errorMessage.includes('ERR_CONNECTION_REFUSED') ||
        errorMessage.includes('ERR_SSL')) {
      console.error(`❌ [FETCH] Network/SSL Error after ${fetchTime}ms:`, {
        url,
        method: options.method || 'GET',
        error: errorMessage,
        stack: errorStack,
        message: 'Backend may be unreachable or SSL certificate issue.'
      })
    } else {
      console.error(`❌ [FETCH] Error after ${fetchTime}ms:`, {
        url,
        method: options.method || 'GET',
        error: errorMessage,
        stack: errorStack
      })
    }
    
    // Re-throw enhanced error with stack trace
    throw enhancedError
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

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  skip: number
  limit: number
}

export type ProspectListResponse = PaginatedResponse<Prospect>

// Jobs API
/**
 * Create a discovery job with robust error handling and authentication
 * 
 * @param keywords - Search keywords (optional if categories provided)
 * @param locations - Array of location codes/names (required)
 * @param maxResults - Maximum number of results (default: 100)
 * @param categories - Array of category names (optional if keywords provided)
 * @returns Promise resolving to job object or throws error
 * 
 * REQUIRES AUTHENTICATION: Valid JWT token must be present in localStorage
 */
export async function createDiscoveryJob(
  keywords: string,
  locations?: string[],
  maxResults?: number,
  categories?: string[]
): Promise<Job> {
  // Check for authentication token before making request
  const token = getAuthToken()
  if (!token) {
    const errorMsg = 'Authentication required. Please log in first.'
    console.error('❌ createDiscoveryJob: No auth token found:', errorMsg)
    throw new Error(errorMsg)
  }
  
  // Validate required parameters
  if (!locations || !Array.isArray(locations) || locations.length === 0) {
    const errorMsg = 'At least one location is required'
    console.error('❌ createDiscoveryJob: Missing locations:', errorMsg)
    throw new Error(errorMsg)
  }
  
  if (!keywords?.trim() && (!categories || !Array.isArray(categories) || categories.length === 0)) {
    const errorMsg = 'Either keywords or at least one category is required'
    console.error('❌ createDiscoveryJob: Missing search criteria:', errorMsg)
    throw new Error(errorMsg)
  }
  
  // Add cache-busting timestamp to ensure fresh requests
  const timestamp = Date.now()
  const url = `${API_BASE}/jobs/discover?_t=${timestamp}`
  
  // Prepare request payload
  const payload = {
    keywords: keywords?.trim() || '',
    locations: Array.isArray(locations) ? locations : [],
    max_results: maxResults && maxResults > 0 ? maxResults : 100,
    categories: Array.isArray(categories) ? categories : [],
  }
  
  try {
    console.log('📤 Creating discovery job:', { 
      keywords: payload.keywords || '(none)', 
      locations: payload.locations.length, 
      categories: payload.categories.length,
      maxResults: payload.max_results 
    })
    
    const res = await authenticatedFetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(payload),
    })
    
    // Parse response - handle both success and error cases
    let responseData: any
    try {
      responseData = await res.json()
    } catch (parseError) {
      console.error('❌ createDiscoveryJob: Failed to parse JSON response:', parseError)
      throw new Error(`Invalid response from server (HTTP ${res.status}): ${res.statusText}`)
    }
    
    // Handle structured error responses from backend
    if (!res.ok || (responseData && responseData.success === false)) {
      const errorDetail = responseData?.error || responseData?.detail || responseData?.message || `HTTP ${res.status}: ${res.statusText}`
      const statusCode = responseData?.status_code || res.status
      
      console.error('❌ createDiscoveryJob: Request failed:', {
        status: statusCode,
        error: errorDetail,
        response: responseData
      })
      
      throw new Error(errorDetail)
    }
    
    // Handle success response - extract job from structured response
    if (responseData && responseData.success === true) {
      // Backend returns structured response: { success: true, job_id, job, ... }
      const job = responseData.job || {
        id: responseData.job_id,
        job_type: 'discover',
        status: responseData.status || 'pending',
        params: payload,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      
      console.log('✅ Discovery job created successfully:', {
        job_id: job.id || responseData.job_id,
        status: job.status || responseData.status
      })
      
      return job
    }
    
    // Fallback: if response doesn't have success field, assume it's the job object directly
    if (responseData && responseData.id) {
      console.log('✅ Discovery job created (legacy format):', responseData.id)
      return responseData
    }
    
    // If we get here, response format is unexpected
    console.warn('⚠️ createDiscoveryJob: Unexpected response format:', responseData)
    throw new Error('Unexpected response format from server')
    
  } catch (error: any) {
    // Enhanced error logging with context
    const errorMessage = error?.message || String(error)
    
    // Check for specific error types
    if (errorMessage.includes('Authentication required') || errorMessage.includes('Unauthorized')) {
      console.error('❌ createDiscoveryJob: Authentication error - redirecting to login')
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token')
        window.location.href = '/login'
      }
    } else if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      console.error('❌ createDiscoveryJob: Network error - backend may be unreachable')
    } else {
      console.error('❌ createDiscoveryJob: Error details:', {
        message: errorMessage,
        error: error,
        stack: error?.stack
      })
    }
    
    // Re-throw with clear message
    throw new Error(errorMessage)
  }
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

export type EnrichmentResult = {
  email?: string
  domain?: string
  [key: string]: any
}

export async function enrichEmail(domain: string, name?: string): Promise<EnrichmentResult> {
  const token = getAuthToken()
  if (!token) {
    throw new Error('Authentication required. Please log in first.')
  }
  
  try {
    const res = await authenticatedFetch(`${API_BASE}/prospects/enrich/direct?domain=${encodeURIComponent(domain)}${name ? `&name=${encodeURIComponent(name)}` : ''}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to enrich email' }))
      throw new Error(error.detail || error.error || 'Failed to enrich email')
    }
    
    const data = await res.json()
    return data
  } catch (error: any) {
    console.error('❌ Error enriching email:', error)
    throw new Error(`Enrichment failed: ${error.message}`)
  }
}

export async function enrichProspectById(prospectId: string): Promise<EnrichmentResult> {
  const token = getAuthToken()
  if (!token) {
    throw new Error('Authentication required. Please log in first.')
  }
  
  try {
    const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}/enrich`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to enrich email' }))
      throw new Error(error.detail || error.error || 'Failed to enrich email')
    }
    
    const data = await res.json()
    return data
  } catch (error: any) {
    console.error('❌ Error enriching email:', error)
    throw new Error(`Enrichment failed: ${error.message}`)
  }
}

export async function cancelJob(jobId: string): Promise<{ success: boolean; message?: string; error?: string }> {
  const token = getAuthToken()
  if (!token) {
    throw new Error('Authentication required. Please log in first.')
  }
  
  try {
    const res = await authenticatedFetch(`${API_BASE}/jobs/${jobId}/cancel`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to cancel job' }))
      throw new Error(error.detail || error.error || 'Failed to cancel job')
    }
    
    const data = await res.json()
    return data
  } catch (error: any) {
    console.error('❌ Error cancelling job:', error)
    throw error
  }
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
  const result: any = await res.json()
  
  // Normalize to PaginatedResponse<Prospect>
  return {
    data: (result.prospects || result.data || []) as Prospect[],
    total: (result.total ?? 0) as number,
    skip,
    limit,
  }
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
      listProspects(0, 1000).catch(() => ({ data: [], total: 0, skip: 0, limit: 0 })),
      listJobs(0, 100).catch(() => []),
      listProspects(0, 1000, undefined, undefined, true).catch(() => ({ data: [], total: 0, skip: 0, limit: 0 })),
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
    
    // Extract prospects array from PaginatedResponse<Prospect> format
    const allProspectsList: Prospect[] = allProspects?.data || []
    const prospectsWithEmailList: Prospect[] = prospectsWithEmail?.data || []
    
    // Extract totals from PaginatedResponse<Prospect> format
    const allProspectsTotal = allProspects?.total ?? 0
    const prospectsWithEmailTotal = prospectsWithEmail?.total ?? 0
    
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
      } else if (jobs && typeof jobs === 'object' && 'data' in jobs && Array.isArray((jobs as any).data)) {
        jobsArray = (jobs as any).data
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
