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
          // Handle structured error response: {error, message, stage} or simple {detail}
          if (typeof errorData.detail === 'object' && errorData.detail?.message) {
            errorDetail = errorData.detail.message
          } else if (typeof errorData.detail === 'string') {
            errorDetail = errorData.detail
          } else {
            errorDetail = errorData.error || errorData.message || errorDetail
          }
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
    
    // Extract error message properly - handle Error objects, strings, and plain objects
    let errorMessage = 'Unknown error'
    if (error instanceof Error) {
      errorMessage = error.message
    } else if (typeof error === 'string') {
      errorMessage = error
    } else if (error?.message) {
      errorMessage = error.message
    } else if (error?.detail) {
      // Handle structured error: {detail: {message: "..."}} or {detail: "..."}
      if (typeof error.detail === 'object' && error.detail?.message) {
        errorMessage = error.detail.message
      } else if (typeof error.detail === 'string') {
        errorMessage = error.detail
      } else {
        errorMessage = JSON.stringify(error.detail)
      }
    } else if (error && typeof error === 'object') {
      // Last resort: try to stringify the error object meaningfully
      try {
        errorMessage = JSON.stringify(error)
      } catch {
        errorMessage = 'Network or connection error'
      }
    }
    
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
  // Pipeline status fields
  discovery_status?: string
  approval_status?: string
  scrape_status?: string
  verification_status?: string
  draft_status?: string
  send_status?: string
  stage?: string  // Canonical pipeline stage: DISCOVERED, SCRAPED, LEAD, VERIFIED, DRAFTED, SENT
  discovery_category?: string
  discovery_location?: string
  discovery_keywords?: string
  scrape_source_url?: string
  verification_confidence?: number
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
  const url = `${API_BASE}/pipeline/discover?_t=${timestamp}`
  
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
    console.log(`🔍 Enriching prospect ${prospectId}...`)
    const res = await authenticatedFetch(`${API_BASE}/prospects/enrich/${prospectId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to enrich email' }))
      console.error(`❌ Enrichment failed (${res.status}):`, error)
      throw new Error(error.detail || error.error || `Failed to enrich email: ${res.status} ${res.statusText}`)
    }
    
    const data = await res.json()
    console.log(`✅ Enrichment response:`, data)
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
    const res = await authenticatedFetch(`${API_BASE}/jobs/cancel/${jobId}`, {
      method: 'POST',
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
    
    // Handle new response format: { data: Job[], total: number, skip: number, limit: number }
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      if (data.data && Array.isArray(data.data)) {
        return data.data
      }
      // Try other possible keys
      const jobs = data.jobs || data.items || []
        if (Array.isArray(jobs)) {
          return jobs
      }
      console.warn('⚠️ listJobs: Response is not an array. Got:', typeof data, data)
      return []
    }
    
    // If it's already an array, return it
    if (Array.isArray(data)) {
    return data
    }
    
    return []
  } catch (error: any) {
    console.error('❌ Error in listJobs:', error)
    // Return empty array to prevent app crash
    return []
  }
}

// Prospects API
export async function listLeads(
  skip = 0,
  limit = 50
): Promise<ProspectListResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  params.append('_t', Date.now().toString())
  
  try {
    const res = await authenticatedFetch(`${API_BASE}/prospects/leads?${params}`)
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to list leads' }))
      throw new Error(error.detail || `Failed to list leads: ${res.status} ${res.statusText}`)
    }
    const result: any = await res.json()
    
    // Normalize to PaginatedResponse<Prospect>
    let prospectsData: Prospect[] = []
    let total = 0
    
    if (result.data && Array.isArray(result.data)) {
      prospectsData = result.data
      total = result.total ?? prospectsData.length
    } else if (Array.isArray(result)) {
      prospectsData = result
      total = prospectsData.length
    }
    
    console.log(`📊 listLeads: Found ${prospectsData.length} leads (total: ${total})`)
    
    return {
      data: prospectsData,
      total: total,
      skip,
      limit,
    }
  } catch (error: any) {
    console.error('listLeads API error:', error)
    throw new Error(error.message || 'Failed to list leads. Check if backend is running.')
  }
}

export async function listScrapedEmails(
  skip = 0,
  limit = 50
): Promise<ProspectListResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  params.append('_t', Date.now().toString())
  
  try {
    const res = await authenticatedFetch(`${API_BASE}/prospects/scraped-emails?${params}`)
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to list scraped emails' }))
      throw new Error(error.detail || `Failed to list scraped emails: ${res.status} ${res.statusText}`)
    }
    const result: any = await res.json()
    
    // Normalize to PaginatedResponse<Prospect>
    let prospectsData: Prospect[] = []
    let total = 0
    
    if (result.data && Array.isArray(result.data)) {
      prospectsData = result.data
      total = result.total ?? prospectsData.length
    } else if (Array.isArray(result)) {
      prospectsData = result
      total = prospectsData.length
    }
    
    console.log(`📊 listScrapedEmails: Found ${prospectsData.length} scraped emails (total: ${total})`)
    
    return {
      data: prospectsData,
      total: total,
      skip,
      limit,
    }
  } catch (error: any) {
    console.error('listScrapedEmails API error:', error)
    throw new Error(error.message || 'Failed to list scraped emails. Check if backend is running.')
  }
}

export async function promoteToLead(prospectId: string): Promise<{ success: boolean; message: string; stage: string }> {
  const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}/promote`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to promote prospect' }))
    throw new Error(error.detail || 'Failed to promote prospect')
  }
  return res.json()
}

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
  
  try {
  const res = await authenticatedFetch(`${API_BASE}/prospects?${params}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list prospects' }))
      throw new Error(error.detail || `Failed to list prospects: ${res.status} ${res.statusText}`)
  }
  const result: any = await res.json()
  
  // Normalize to PaginatedResponse<Prospect>
    // Backend returns: {success: true, data: {data: [...], prospects: [...], total: ...}}
    // Handle nested structure
    let prospectsData: Prospect[] = []
    let total = 0
    
    // Check for nested structure first (backend format)
    if (result.success && result.data) {
      if (Array.isArray(result.data.data)) {
        prospectsData = result.data.data
        total = result.data.total ?? prospectsData.length
      } else if (Array.isArray(result.data.prospects)) {
        prospectsData = result.data.prospects
        total = result.data.total ?? prospectsData.length
      }
    }
    // Fallback to direct array or flat structure
    else if (result.prospects && Array.isArray(result.prospects)) {
      prospectsData = result.prospects
      total = result.total ?? prospectsData.length
    } else if (result.data && Array.isArray(result.data)) {
      prospectsData = result.data
      total = result.total ?? prospectsData.length
    } else if (Array.isArray(result)) {
      prospectsData = result
      total = prospectsData.length
    }
    
    console.log(`📊 listProspects: Found ${prospectsData.length} prospects (total: ${total})`)
    
  return {
      data: prospectsData,
      total: total,
    skip,
    limit,
    }
  } catch (error: any) {
    console.error('listProspects API error:', error)
    // Re-throw with more context
    throw new Error(error.message || 'Failed to list prospects. Check if backend is running.')
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
  prospectId: string
): Promise<{
  prospect_id: string
  email_log_id: string
  sent_at: string
  success: boolean
  message_id?: string
}> {
  // Manual send endpoint - sends existing draft (no body content in request)
  // Email content comes ONLY from database (draft_subject, draft_body)
  const res = await authenticatedFetch(`${API_BASE}/prospects/${prospectId}/send`, {
    method: 'POST',
    // No body - endpoint uses draft from database
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to send email' }))
    const status = res.status
    // Map HTTP status codes to specific error messages
    if (status === 400) {
      throw new Error(error.detail || 'Prospect is not ready for sending. Ensure draft exists and email is verified.')
    } else if (status === 409) {
      throw new Error(error.detail || 'Email already sent for this prospect.')
    } else if (status === 500) {
      throw new Error(error.detail || 'Failed to send email. Please try again.')
    }
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
    // Handle both normalized response and raw backend response
    let allProspectsList: Prospect[] = []
    if (allProspects) {
      if (Array.isArray(allProspects)) {
        allProspectsList = allProspects
      } else if (allProspects.data && Array.isArray(allProspects.data)) {
        allProspectsList = allProspects.data
      } else {
        // Handle raw backend response that might have 'prospects' property
        const rawResponse = allProspects as any
        if (rawResponse.prospects && Array.isArray(rawResponse.prospects)) {
          allProspectsList = rawResponse.prospects
        }
      }
    }
    
    let prospectsWithEmailList: Prospect[] = []
    if (prospectsWithEmail) {
      if (Array.isArray(prospectsWithEmail)) {
        prospectsWithEmailList = prospectsWithEmail
      } else if (prospectsWithEmail.data && Array.isArray(prospectsWithEmail.data)) {
        prospectsWithEmailList = prospectsWithEmail.data
      } else {
        // Handle raw backend response that might have 'prospects' property
        const rawResponse = prospectsWithEmail as any
        if (rawResponse.prospects && Array.isArray(rawResponse.prospects)) {
          prospectsWithEmailList = rawResponse.prospects
        }
      }
    }
    
    // Extract totals from PaginatedResponse<Prospect> format
    const allProspectsTotal = (allProspects && typeof allProspects === 'object' && 'total' in allProspects) 
      ? (allProspects.total ?? 0) 
      : allProspectsList.length
    const prospectsWithEmailTotal = (prospectsWithEmail && typeof prospectsWithEmail === 'object' && 'total' in prospectsWithEmail)
      ? (prospectsWithEmail.total ?? 0)
      : prospectsWithEmailList.length
    
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

// ============================================
// PIPELINE API - Strict Step-by-Step Pipeline
// ============================================

export interface PipelineDiscoveryRequest {
  categories: string[]
  locations: string[]
  keywords?: string
  max_results?: number
}

export interface PipelineDiscoveryResponse {
  success: boolean
  job_id: string
  message: string
  prospects_count: number
}

export async function pipelineDiscover(request: PipelineDiscoveryRequest): Promise<PipelineDiscoveryResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/discover`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to start discovery' }))
    throw new Error(error.detail || 'Failed to start discovery')
  }
  return res.json()
}

export interface PipelineApprovalRequest {
  prospect_ids: string[]
  action: 'approve' | 'reject' | 'delete'
}

export interface PipelineApprovalResponse {
  success: boolean
  approved_count: number
  rejected_count: number
  deleted_count: number
  message: string
}

export async function pipelineApprove(request: PipelineApprovalRequest): Promise<PipelineApprovalResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/approve`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to approve prospects' }))
    throw new Error(error.detail || 'Failed to approve prospects')
  }
  return res.json()
}

export async function pipelineApproveAll(): Promise<PipelineApprovalResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/approve_all`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to approve all prospects' }))
    throw new Error(error.detail || 'Failed to approve all prospects')
  }
  return res.json()
}

export interface PipelineScrapeRequest {
  prospect_ids?: string[]
}

export interface PipelineScrapeResponse {
  success: boolean
  job_id: string
  message: string
  prospects_count: number
}

export async function pipelineScrape(request?: PipelineScrapeRequest): Promise<PipelineScrapeResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/scrape`, {
    method: 'POST',
    body: JSON.stringify(request || {}),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to start scraping' }))
    throw new Error(error.detail || 'Failed to start scraping')
  }
  return res.json()
}

export interface PipelineVerifyRequest {
  prospect_ids?: string[]
}

export interface PipelineVerifyResponse {
  success: boolean
  job_id: string
  message: string
  prospects_count: number
}

export async function pipelineVerify(request?: PipelineVerifyRequest): Promise<PipelineVerifyResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/verify`, {
    method: 'POST',
    body: JSON.stringify(request || {}),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to start verification' }))
    throw new Error(error.detail || 'Failed to start verification')
  }
  return res.json()
}

export interface PipelineReviewProspect {
  id: string
  domain: string
  contact_email: string
  scrape_source_url?: string
  verification_status?: string
  verification_confidence?: number
  email_type?: string
}

export interface PipelineReviewResponse {
  data: PipelineReviewProspect[]
  total: number
  skip: number
  limit: number
}

export async function pipelineReview(): Promise<PipelineReviewResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/review`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get review prospects' }))
    throw new Error(error.detail || 'Failed to get review prospects')
  }
  return res.json()
}

export interface PipelineDraftRequest {
  prospect_ids?: string[]
  outreach_intent?: string
}

export interface PipelineDraftResponse {
  success: boolean
  job_id: string
  message: string
  prospects_count: number
}

export async function pipelineDraft(request?: PipelineDraftRequest): Promise<PipelineDraftResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/draft`, {
    method: 'POST',
    body: JSON.stringify(request || {}),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to start drafting' }))
    throw new Error(error.detail || 'Failed to start drafting')
  }
  return res.json()
}

export interface PipelineSendRequest {
  prospect_ids?: string[]
}

export interface PipelineSendResponse {
  success: boolean
  job_id: string
  message: string
  prospects_count: number
}

export async function pipelineSend(request?: PipelineSendRequest): Promise<PipelineSendResponse> {
  // If no prospect_ids provided, send empty object to trigger automatic selection of all send-ready prospects
  const payload = request?.prospect_ids && request.prospect_ids.length > 0 
    ? request 
    : { prospect_ids: null }  // Send null to trigger automatic query
  const res = await authenticatedFetch(`${API_BASE}/pipeline/send`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to start sending' }))
    throw new Error(error.detail || 'Failed to start sending')
  }
  return res.json()
}

// Raw API response - fields may be missing
export interface PipelineStatus {
  discovered?: number
  approved?: number
  scraped?: number
  email_found?: number  // Prospects with emails found (stage=EMAIL_FOUND)
  emails_found?: number  // All prospects with emails (contact_email IS NOT NULL)
  leads?: number  // Explicitly promoted leads (stage=LEAD) - ONLY these are shown in Leads page
  verified?: number  // Backwards-compatible: verification_status=verified AND email IS NOT NULL
  verified_email_count?: number  // Backwards-compatible alias
  verified_count?: number  // Data-driven: contact_email IS NOT NULL AND verification_status = 'verified'
  emails_verified?: number  // Data-driven: verification_status=verified AND contact_email IS NOT NULL (matches Leads page)
  verified_stage?: number  // stage = VERIFIED
  reviewed?: number  // Same as emails_verified for review step
  drafted?: number  // Data-driven: draft_subject IS NOT NULL AND draft_body IS NOT NULL
  drafted_count?: number  // Explicit count of drafted prospects
  sent?: number  // Optional - may not be in response
  send_ready?: number  // Data-driven: verified + drafted + not sent
  send_ready_count?: number  // Explicit count of send-ready prospects
  discovered_for_scraping?: number  // Legacy field - aliased to scrape_ready_count
  scrape_ready_count?: number       // New canonical field for scraping unlock
  drafting_ready?: number  // Data-driven: stage=LEAD, email IS NOT NULL, verification_status=verified
  drafting_ready_count?: number  // Backwards-compatible alias
}

// Normalized pipeline status - ALL fields are guaranteed to be numbers
export interface NormalizedPipelineStatus {
  discovered: number
  approved: number
  scraped: number
  email_found: number  // Prospects with emails found (stage=EMAIL_FOUND)
  emails_found: number  // All prospects with emails (contact_email IS NOT NULL)
  leads: number  // Explicitly promoted leads (stage=LEAD) - ONLY these are shown in Leads page
  verified: number  // Backwards-compatible: verification_status=verified AND email IS NOT NULL
  verified_email_count: number  // Backwards-compatible alias
  verified_count: number  // Data-driven: contact_email IS NOT NULL AND verification_status = 'verified'
  emails_verified: number  // Data-driven: verification_status=verified AND contact_email IS NOT NULL (matches Leads page)
  verified_stage: number  // stage = VERIFIED
  reviewed: number
  drafted: number  // Data-driven: draft_subject IS NOT NULL AND draft_body IS NOT NULL
  drafted_count: number  // Explicit count of drafted prospects
  sent: number
  send_ready: number  // Data-driven: verified + drafted + not sent
  send_ready_count: number  // Explicit count of send-ready prospects
  discovered_for_scraping: number
  scrape_ready_count: number
  drafting_ready: number  // Data-driven: stage=LEAD, email IS NOT NULL, verification_status=verified
  drafting_ready_count: number  // Backwards-compatible alias
}

/**
 * Normalizes a partial pipeline status from the API into a complete status object.
 * All missing fields default to 0, ensuring type safety throughout the application.
 * 
 * @param rawStatus - Partial status object from API (may have missing fields)
 * @returns Complete normalized status with all fields as numbers
 */
export function normalizePipelineStatus(rawStatus: Partial<PipelineStatus> | null | undefined): NormalizedPipelineStatus {
  const discoveredForScraping =
    typeof rawStatus?.scrape_ready_count === 'number'
      ? rawStatus.scrape_ready_count
      : typeof rawStatus?.discovered_for_scraping === 'number'
      ? rawStatus.discovered_for_scraping
      : 0

  return {
    discovered: typeof rawStatus?.discovered === 'number' ? rawStatus.discovered : 0,
    approved: typeof rawStatus?.approved === 'number' ? rawStatus.approved : 0,
    scraped: typeof rawStatus?.scraped === 'number' ? rawStatus.scraped : 0,
    email_found: typeof rawStatus?.email_found === 'number' ? rawStatus.email_found : 0,  // Prospects with emails found (stage=EMAIL_FOUND)
    emails_found: typeof rawStatus?.emails_found === 'number' ? rawStatus.emails_found : 0,  // All prospects with emails (contact_email IS NOT NULL)
    leads: typeof rawStatus?.leads === 'number' ? rawStatus.leads : 0,  // Explicitly promoted leads (stage=LEAD)
    verified: typeof rawStatus?.emails_verified === 'number' ? rawStatus.emails_verified : (typeof rawStatus?.verified_email_count === 'number' ? rawStatus.verified_email_count : (typeof rawStatus?.verified === 'number' ? rawStatus.verified : 0)),  // Use emails_verified if available, fallback to verified_email_count or verified
    verified_email_count: typeof rawStatus?.emails_verified === 'number' ? rawStatus.emails_verified : (typeof rawStatus?.verified_email_count === 'number' ? rawStatus.verified_email_count : (typeof rawStatus?.verified === 'number' ? rawStatus.verified : 0)),  // Backwards-compatible alias
    verified_count: typeof rawStatus?.verified_count === 'number' ? rawStatus.verified_count : (typeof rawStatus?.emails_verified === 'number' ? rawStatus.emails_verified : (typeof rawStatus?.verified_email_count === 'number' ? rawStatus.verified_email_count : (typeof rawStatus?.verified === 'number' ? rawStatus.verified : 0))),  // Data-driven: contact_email IS NOT NULL AND verification_status = 'verified'
    emails_verified: typeof rawStatus?.emails_verified === 'number' ? rawStatus.emails_verified : (typeof rawStatus?.verified_email_count === 'number' ? rawStatus.verified_email_count : (typeof rawStatus?.verified === 'number' ? rawStatus.verified : 0)),  // Data-driven: verification_status=verified AND contact_email IS NOT NULL (matches Leads page)
    verified_stage: typeof rawStatus?.verified_stage === 'number' ? rawStatus.verified_stage : 0,  // stage = VERIFIED
    reviewed: typeof rawStatus?.emails_verified === 'number' ? rawStatus.emails_verified : (typeof rawStatus?.reviewed === 'number' ? rawStatus.reviewed : 0),  // Same as emails_verified
    drafted: typeof rawStatus?.drafted === 'number' ? rawStatus.drafted : (typeof rawStatus?.drafted_count === 'number' ? rawStatus.drafted_count : 0),  // Data-driven: draft_subject IS NOT NULL AND draft_body IS NOT NULL
    drafted_count: typeof rawStatus?.drafted_count === 'number' ? rawStatus.drafted_count : (typeof rawStatus?.drafted === 'number' ? rawStatus.drafted : 0),  // Explicit count of drafted prospects
    sent: typeof rawStatus?.sent === 'number' ? rawStatus.sent : 0,
    send_ready: typeof rawStatus?.send_ready === 'number' ? rawStatus.send_ready : (typeof rawStatus?.send_ready_count === 'number' ? rawStatus.send_ready_count : 0),  // Data-driven: verified + drafted + not sent
    send_ready_count: typeof rawStatus?.send_ready_count === 'number' ? rawStatus.send_ready_count : (typeof rawStatus?.send_ready === 'number' ? rawStatus.send_ready : 0),  // Explicit count of send-ready prospects
    discovered_for_scraping: discoveredForScraping,
    scrape_ready_count: discoveredForScraping,
    drafting_ready: typeof rawStatus?.drafting_ready === 'number' ? rawStatus.drafting_ready : (typeof rawStatus?.drafting_ready_count === 'number' ? rawStatus.drafting_ready_count : 0),  // Data-driven: stage=LEAD, email IS NOT NULL, verification_status=verified
    drafting_ready_count: typeof rawStatus?.drafting_ready === 'number' ? rawStatus.drafting_ready : (typeof rawStatus?.drafting_ready_count === 'number' ? rawStatus.drafting_ready_count : 0),  // Backwards-compatible alias
  }
}

export async function listWebsites(skip: number = 0, limit: number = 50): Promise<{
  data: Array<{
    id: string
    domain: string
    url: string
    title: string
    category: string
    location: string
    discovery_job_id: string | null
    discovered_at: string | null
    scrape_status: string
    approval_status: string
  }>
  total: number
  skip: number
  limit: number
}> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/websites?skip=${skip}&limit=${limit}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to fetch websites' }))
    throw new Error(error.detail || 'Failed to fetch websites')
  }
  return res.json()
}

export async function pipelineStatus(): Promise<PipelineStatus> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/status`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get pipeline status' }))
    throw new Error(error.detail || 'Failed to get pipeline status')
  }
  return res.json()
}

// ============================================
// MANUAL INPUT ENDPOINTS
// ============================================

export interface ManualScrapeRequest {
  website_url: string
}

export interface ManualScrapeResponse {
  success: boolean
  prospect_id: string
  message: string
  is_followup: boolean
}

export async function manualScrape(request: ManualScrapeRequest): Promise<ManualScrapeResponse> {
  const res = await authenticatedFetch(`${API_BASE}/manual/scrape`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to scrape website' }))
    throw new Error(error.detail || 'Failed to scrape website')
  }
  return res.json()
}

export interface ManualVerifyRequest {
  email: string
}

export interface ManualVerifyResponse {
  success: boolean
  prospect_id: string
  message: string
  verification_status: string
  is_followup: boolean
}

export async function manualVerify(request: ManualVerifyRequest): Promise<ManualVerifyResponse> {
  const res = await authenticatedFetch(`${API_BASE}/manual/verify`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to verify email' }))
    throw new Error(error.detail || 'Failed to verify email')
  }
  return res.json()
}

// ============================================
// CATEGORY MANAGEMENT
// ============================================

export interface UpdateCategoryRequest {
  prospect_ids: string[]
  category: string
}

export interface UpdateCategoryResponse {
  success: boolean
  updated_count: number
  message: string
}

export async function updateProspectCategory(request: UpdateCategoryRequest): Promise<UpdateCategoryResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/update_category`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to update category' }))
    throw new Error(error.detail || 'Failed to update category')
  }
  return res.json()
}

export interface AutoCategorizeResponse {
  success: boolean
  categorized_count: number
  message: string
}

export async function autoCategorizeAll(): Promise<AutoCategorizeResponse> {
  const res = await authenticatedFetch(`${API_BASE}/pipeline/auto_categorize`, {
    method: 'POST',
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to auto-categorize' }))
    throw new Error(error.detail || 'Failed to auto-categorize')
  }
  return res.json()
}

// ============================================
// MASTER SWITCH & AUTOMATION CONTROL
// ============================================

export interface MasterSwitchResponse {
  enabled: boolean
  message: string
}

export async function getMasterSwitch(): Promise<MasterSwitchResponse> {
  const res = await authenticatedFetch(`${API_BASE}/scraper/master`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get master switch status' }))
    throw new Error(error.detail || 'Failed to get master switch status')
  }
  return res.json()
}

export async function setMasterSwitch(enabled: boolean): Promise<MasterSwitchResponse> {
  const res = await authenticatedFetch(`${API_BASE}/scraper/master`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to set master switch' }))
    throw new Error(error.detail || 'Failed to set master switch')
  }
  const result = await res.json()
  // Store in localStorage for Pipeline to check
  if (typeof window !== 'undefined') {
    localStorage.setItem('master_switch_enabled', String(enabled))
    // Dispatch event so Pipeline can react
    window.dispatchEvent(new CustomEvent('masterSwitchChanged', { detail: { enabled } }))
  }
  return result
}

export interface AutomationSettings {
  enabled: boolean
}

export async function getAutomationSettings(): Promise<AutomationSettings> {
  const res = await authenticatedFetch(`${API_BASE}/settings/automation`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get automation settings' }))
    throw new Error(error.detail || 'Failed to get automation settings')
  }
  return res.json()
}

export async function updateAutomationSettings(settings: AutomationSettings): Promise<AutomationSettings> {
  const res = await authenticatedFetch(`${API_BASE}/settings/automation`, {
    method: 'POST',
    body: JSON.stringify(settings),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to update automation settings' }))
    throw new Error(error.detail || 'Failed to update automation settings')
  }
  const result = await res.json()
  // Store in localStorage for Pipeline to check
  if (typeof window !== 'undefined') {
    localStorage.setItem('automation_enabled', String(settings.enabled))
    // Dispatch event so Pipeline can react
    window.dispatchEvent(new CustomEvent('automationSettingsChanged', { detail: settings }))
  }
  return result
}

// Helper function to check if master switch is enabled (for Pipeline)
export function isMasterSwitchEnabled(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem('master_switch_enabled')
  return stored === 'true'
}

// ============================================
// SOCIAL OUTREACH API (Separate from Website Outreach)
// ============================================

export interface SocialDiscoveryRequest {
  platform: 'linkedin' | 'instagram' | 'tiktok'
  filters: {
    keywords?: string[]
    location?: string
    hashtags?: string[]
  }
  max_results?: number
}

export interface SocialDiscoveryResponse {
  success: boolean
  job_id: string
  message: string
  profiles_count: number
}

export interface SocialProfile {
  id: string
  platform: string
  username: string
  full_name?: string
  profile_url: string
  bio?: string
  followers_count: number
  location?: string
  category?: string
  engagement_score: number
  discovery_status: string
  outreach_status: string
  created_at: string
  draft_subject?: string
  draft_body?: string
  last_sent?: string
  followups_sent?: number
  updated_at?: string
}

export interface SocialProfileListResponse {
  data: SocialProfile[]
  total: number
  skip: number
  limit: number
}

export async function discoverSocialProfiles(request: SocialDiscoveryRequest): Promise<SocialDiscoveryResponse> {
  const res = await authenticatedFetch(`${API_BASE}/social/discover`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to discover social profiles' }))
    throw new Error(error.detail || 'Failed to discover social profiles')
  }
  return await res.json()
}

export async function listSocialProfiles(
  skip: number = 0,
  limit: number = 50,
  platform?: string,
  qualification_status?: string
): Promise<SocialProfileListResponse> {
  const params = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
  if (platform) params.append('platform', platform)
  if (qualification_status) params.append('qualification_status', qualification_status)
  
  const res = await authenticatedFetch(`${API_BASE}/social/profiles?${params.toString()}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list social profiles' }))
    throw new Error(error.detail || 'Failed to list social profiles')
  }
  return await res.json()
}

export async function createSocialDrafts(request: { profile_ids: string[]; is_followup?: boolean }): Promise<{ success: boolean; drafts_created: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/drafts`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create social drafts' }))
    throw new Error(error.detail || 'Failed to create social drafts')
  }
  return await res.json()
}

export async function sendSocialMessages(request: { profile_ids: string[] }): Promise<{ success: boolean; messages_sent: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/send`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to send social messages' }))
    throw new Error(error.detail || 'Failed to send social messages')
  }
  return await res.json()
}

export async function createSocialFollowups(request: { profile_ids: string[] }): Promise<{ success: boolean; drafts_created: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/followup`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create social followups' }))
    throw new Error(error.detail || 'Failed to create social followups')
  }
  return await res.json()
}

// SOCIAL STATS API
export interface SocialStats {
  total_profiles: number
  discovered: number
  drafted: number
  sent: number
  pending: number
  jobs_running: number
  linkedin_total: number
  linkedin_discovered: number
  linkedin_drafted: number
  linkedin_sent: number
  instagram_total: number
  instagram_discovered: number
  instagram_drafted: number
  instagram_sent: number
  facebook_total: number
  facebook_discovered: number
  facebook_drafted: number
  facebook_sent: number
  tiktok_total: number
  tiktok_discovered: number
  tiktok_drafted: number
  tiktok_sent: number
}

export async function getSocialStats(): Promise<SocialStats | null> {
  try {
    const res = await authenticatedFetch(`${API_BASE}/social/stats`)
    if (!res.ok) {
      return null
    }
    return res.json()
  } catch (error) {
    console.error('Failed to get social stats:', error)
    return null
  }
}

// SOCIAL PIPELINE API (New pipeline endpoints)
export interface SocialPipelineStatus {
  discovered: number
  reviewed: number
  qualified: number
  drafted: number
  sent: number
  followup_ready: number
  status?: 'active' | 'inactive'
  reason?: string
}

export async function getSocialPipelineStatus(platform?: 'linkedin' | 'instagram' | 'facebook' | 'tiktok'): Promise<SocialPipelineStatus> {
  const url = platform 
    ? `${API_BASE}/social/pipeline/status?platform=${platform}`
    : `${API_BASE}/social/pipeline/status`
  const res = await authenticatedFetch(url)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to get social pipeline status' }))
    throw new Error(error.detail || 'Failed to get social pipeline status')
  }
  return res.json()
}

export interface SocialDiscoveryPipelineRequest {
  platform: 'linkedin' | 'instagram' | 'tiktok' | 'facebook'
  categories: string[]
  locations: string[]
  keywords?: string[]
  parameters?: Record<string, any>
  max_results?: number
}

export async function discoverSocialProfilesPipeline(request: SocialDiscoveryPipelineRequest): Promise<{ success: boolean; job_id: string; message: string; profiles_count: number }> {
  const res = await authenticatedFetch(`${API_BASE}/social/pipeline/discover`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to discover social profiles' }))
    throw new Error(error.detail || 'Failed to discover social profiles')
  }
  return res.json()
}

export async function reviewSocialProfiles(profile_ids: string[], action: 'qualify' | 'reject'): Promise<{ success: boolean; updated: number; action: string; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/pipeline/review`, {
    method: 'POST',
    body: JSON.stringify({ profile_ids, action }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to review profiles' }))
    throw new Error(error.detail || 'Failed to review profiles')
  }
  return res.json()
}

export async function draftSocialProfiles(profile_ids: string[], is_followup: boolean = false): Promise<{ success: boolean; drafts_created: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/pipeline/draft`, {
    method: 'POST',
    body: JSON.stringify({ profile_ids, is_followup }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create drafts' }))
    throw new Error(error.detail || 'Failed to create drafts')
  }
  return res.json()
}

export async function sendSocialProfiles(profile_ids: string[]): Promise<{ success: boolean; messages_sent: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/pipeline/send`, {
    method: 'POST',
    body: JSON.stringify({ profile_ids }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to send messages' }))
    throw new Error(error.detail || 'Failed to send messages')
  }
  return res.json()
}

export async function createSocialFollowupsPipeline(profile_ids: string[]): Promise<{ success: boolean; drafts_created: number; message: string }> {
  const res = await authenticatedFetch(`${API_BASE}/social/pipeline/followup`, {
    method: 'POST',
    body: JSON.stringify({ profile_ids }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to create followups' }))
    throw new Error(error.detail || 'Failed to create followups')
  }
  return res.json()
}

// List drafted social profiles
export async function listSocialDrafts(
  skip: number = 0,
  limit: number = 50,
  platform?: string
): Promise<SocialProfileListResponse> {
  const params = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
  if (platform) params.append('platform', platform)
  
  const res = await authenticatedFetch(`${API_BASE}/social/drafts?${params.toString()}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list social drafts' }))
    throw new Error(error.detail || 'Failed to list social drafts')
  }
  return await res.json()
}

// List sent social profiles
export async function listSocialSent(
  skip: number = 0,
  limit: number = 50,
  platform?: string
): Promise<SocialProfileListResponse> {
  const params = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
  if (platform) params.append('platform', platform)
  
  const res = await authenticatedFetch(`${API_BASE}/social/sent?${params.toString()}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to list sent social messages' }))
    throw new Error(error.detail || 'Failed to list sent social messages')
  }
  return await res.json()
}

// CSV Export functions
export async function exportProspectsCSV(status?: string, sourceType?: string): Promise<Blob> {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  if (sourceType) params.append('source_type', sourceType)
  
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/prospects/export/csv?${params.toString()}`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export CSV' }))
    throw new Error(error.detail || 'Failed to export CSV')
  }
  return await res.blob()
}

export async function exportLeadsCSV(): Promise<Blob> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/prospects/leads/export/csv`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export leads CSV' }))
    throw new Error(error.detail || 'Failed to export leads CSV')
  }
  return await res.blob()
}

export async function exportScrapedEmailsCSV(): Promise<Blob> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/prospects/scraped-emails/export/csv`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export scraped emails CSV' }))
    throw new Error(error.detail || 'Failed to export scraped emails CSV')
  }
  return await res.blob()
}

export async function exportSocialProfilesCSV(platform?: string): Promise<Blob> {
  const params = new URLSearchParams()
  if (platform) params.append('platform', platform)
  
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/social/profiles/export/csv?${params.toString()}`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export social profiles CSV' }))
    throw new Error(error.detail || 'Failed to export social profiles CSV')
  }
  return await res.blob()
}

export async function exportSocialDraftsCSV(platform?: string): Promise<Blob> {
  const params = new URLSearchParams()
  if (platform) params.append('platform', platform)
  
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/social/drafts/export/csv?${params.toString()}`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export social drafts CSV' }))
    throw new Error(error.detail || 'Failed to export social drafts CSV')
  }
  return await res.blob()
}

export async function exportSocialSentCSV(platform?: string): Promise<Blob> {
  const params = new URLSearchParams()
  if (platform) params.append('platform', platform)
  
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${token}`,
  }
  
  const res = await fetch(`${API_BASE}/social/sent/export/csv?${params.toString()}`, { headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to export sent social messages CSV' }))
    throw new Error(error.detail || 'Failed to export sent social messages CSV')
  }
  return await res.blob()
}

// Gemini Chat API
export interface GeminiChatRequest {
  prospect_id: string
  message: string
  current_subject?: string
  current_body?: string
}

export interface GeminiChatResponse {
  success: boolean
  response: string
  candidate_draft?: {
    subject: string
    body: string
  }
}

export async function geminiChat(request: GeminiChatRequest): Promise<GeminiChatResponse> {
  const res = await authenticatedFetch(`${API_BASE}/prospects/${request.prospect_id}/chat`, {
    method: 'POST',
    body: JSON.stringify({
      message: request.message,
      current_subject: request.current_subject,
      current_body: request.current_body
    }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to chat with Gemini' }))
    // Handle structured error response: {error, message, stage} or simple {detail}
    const errorMessage = typeof error.detail === 'object' && error.detail?.message
      ? error.detail.message
      : typeof error.detail === 'string'
      ? error.detail
      : error.message || 'Failed to chat with Gemini'
    throw new Error(errorMessage)
  }
  return await res.json()
}
