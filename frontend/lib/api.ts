/**
 * API client for FastAPI backend
 * Defaults to production URL, falls back to localhost for development
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 
  (typeof window !== 'undefined' && window.location.hostname !== 'localhost' 
    ? `https://${window.location.hostname}/api/v1`
    : 'http://localhost:8000/api/v1');

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('auth_token')
}

/**
 * Make authenticated API request
 */
async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken()
  const headers = {
    ...options.headers,
    'Content-Type': 'application/json',
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  })
  
  // If unauthorized, redirect to login
  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  
  return response
}

export interface Lead {
  id: number;
  email?: string;
  phone_number?: string;
  social_platform?: string;
  social_url?: string;
  name?: string;
  website_id: number;
  website_title?: string;
  website_url?: string;
  website_category?: string;
  created_at: string;
}

export interface LeadsResponse {
  leads: Lead[];
  total: number;
  skip: number;
  limit: number;
}

export interface Email {
  id: number;
  subject: string;
  recipient_email: string;
  status: string;
  website_id: number;
  contact_id?: number;
  website_title?: string;
  sent_at?: string;
  created_at: string;
}

export interface EmailsResponse {
  emails: Email[];
  total: number;
  skip: number;
  limit: number;
}

export interface Stats {
  leads_collected: number;
  emails_extracted: number;
  phones_extracted: number;
  social_links_extracted: number;
  outreach_sent: number;
  outreach_pending: number;
  outreach_failed: number;
  websites_scraped: number;
  websites_pending: number;
  websites_failed: number;
  jobs_completed: number;
  jobs_running: number;
  jobs_failed: number;
  recent_activity: {
    leads_last_24h: number;
    emails_sent_last_24h: number;
    websites_scraped_last_24h: number;
  };
}

export interface JobStatus {
  id: number;
  job_type: string;
  status: string;
  result?: any;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface LatestJobs {
  [key: string]: {
    status: string;
    result?: any;
    error_message?: string;
    started_at?: string;
    completed_at?: string;
    created_at?: string;
  };
}

export interface Website {
  id: number;
  url: string;
  domain?: string;
  title?: string;
  description?: string;
  category?: string;
  website_type?: string;
  status: string;
  is_art_related?: boolean;
  quality_score?: number;
  created_at: string;
}

export interface ScrapeResult {
  id: number;
  url: string;
  domain?: string;
  title?: string;
  description?: string;
  category?: string;
  website_type?: string;
  quality_score?: number;
  is_art_related?: boolean;
  status: string;
  created_at: string;
}

export interface DiscoveredWebsite {
  id: number;
  url: string;
  domain?: string;
  title?: string;
  snippet?: string;
  source: string;
  search_query?: string;
  category?: string;
  is_scraped: boolean;
  scraped_website_id?: number;
  created_at: string;
}

export interface DiscoveredWebsitesResponse {
  discovered: DiscoveredWebsite[];
  total: number;
  skip: number;
  limit: number;
  filters?: {
    is_scraped?: boolean;
    source?: string;
    category?: string;
  };
  contacts?: Array<{
    id: number;
    email?: string;
    phone_number?: string;
    social_platform?: string;
    social_url?: string;
    name?: string;
    role?: string;
  }>;
  extraction_stats?: {
    emails_found: number;
    phones_found: number;
    social_links_found: number;
    total_contacts: number;
  };
}

export interface Activity {
  id: number;
  activity_type: string;
  message: string;
  status: string;
  website_id?: number;
  job_id?: number;
  metadata?: any;
  created_at: string;
}

/**
 * Get leads with pagination and filtering
 */
export async function getLeads(
  skip = 0,
  limit = 50,
  category?: string,
  hasEmail?: boolean
): Promise<LeadsResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  if (category) params.append('category', category);
  if (hasEmail !== undefined) params.append('has_email', hasEmail.toString());

  const res = await authenticatedFetch(`${API_BASE}/leads?${params}`);
  if (!res.ok) throw new Error('Failed to fetch leads');
  return res.json();
}

/**
 * Get sent emails
 */
export async function getSentEmails(skip = 0, limit = 50): Promise<EmailsResponse> {
  const res = await authenticatedFetch(`${API_BASE}/emails/sent?skip=${skip}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch sent emails');
  return res.json();
}

/**
 * Get pending emails
 */
export async function getPendingEmails(skip = 0, limit = 50): Promise<EmailsResponse> {
  const res = await authenticatedFetch(`${API_BASE}/emails/pending?skip=${skip}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch pending emails');
  return res.json();
}

/**
 * Get statistics
 */
export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to fetch stats' }));
    throw new Error(error.detail || 'Failed to fetch stats');
  }
  return res.json();
}

/**
 * Get job status
 */
export async function getJobStatus(limit = 20, jobType?: string, status?: string): Promise<JobStatus[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (jobType) params.append('job_type', jobType);
  if (status) params.append('status', status);

  const res = await authenticatedFetch(`${API_BASE}/jobs/status?${params}`);
  if (!res.ok) throw new Error('Failed to fetch job status');
  return res.json();
}

/**
 * Get latest job executions
 */
export async function getLatestJobs(): Promise<LatestJobs> {
  const res = await fetch(`${API_BASE}/jobs/latest`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to fetch latest jobs' }));
    throw new Error(error.detail || 'Failed to fetch latest jobs');
  }
  return res.json();
}

/**
 * Scrape a URL
 */
export async function scrapeUrl(url: string, skipQualityCheck = false): Promise<ScrapeResult> {
  const params = new URLSearchParams({ url });
  if (skipQualityCheck) params.append('skip_quality_check', 'true');

  const res = await authenticatedFetch(`${API_BASE}/scrape-url?${params}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to scrape URL');
  }
  return res.json();
}

/**
 * Get activity logs
 */
export async function getActivity(
  limit = 50,
  activityType?: string,
  status?: string
): Promise<{ activities: Activity[]; total: number }> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (activityType) params.append('activity_type', activityType);
  if (status) params.append('status', status);

  const res = await authenticatedFetch(`${API_BASE}/activity?${params}`);
  if (!res.ok) throw new Error('Failed to fetch activity');
  return res.json();
}

/**
 * Get discovered websites
 */
export async function getDiscoveredWebsites(
  skip = 0,
  limit = 50,
  isScraped?: boolean,
  source?: string,
  category?: string
): Promise<DiscoveredWebsitesResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  if (isScraped !== undefined) params.append('is_scraped', isScraped.toString());
  if (source) params.append('source', source);
  if (category) params.append('category', category);

  const res = await authenticatedFetch(`${API_BASE}/discovered?${params}`);
  if (!res.ok) throw new Error('Failed to fetch discovered websites');
  return res.json();
}

/**
 * Get websites
 */
export async function getWebsites(): Promise<Website[]> {
  const res = await authenticatedFetch(`${API_BASE}/websites`);
  if (!res.ok) throw new Error('Failed to fetch websites');
  return res.json();
}

/**
 * Extract contacts for a website
 */
export async function extractContactsForWebsite(websiteId: number): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/websites/${websiteId}/extract-contacts`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to extract contacts');
}

