'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Lock, Loader2, Search, Scissors, Shield, Eye, FileText, Send, RefreshCw, ArrowRight } from 'lucide-react'
import { 
  pipelineDiscover, 
  pipelineApprove, 
  pipelineApproveAll,
  pipelineScrape, 
  pipelineVerify, 
  pipelineDraft, 
  pipelineSend,
  pipelineStatus,
  listJobs,
  normalizePipelineStatus,
  type Job,
  type NormalizedPipelineStatus
} from '@/lib/api'

interface StepCard {
  id: number
  name: string
  description: string
  icon: any
  status: 'pending' | 'active' | 'completed' | 'locked'
  count: number
  ctaText: string
  ctaAction: () => void
  jobStatus?: string
}

export default function Pipeline() {
  const [status, setStatus] = useState<NormalizedPipelineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [discoveryJobs, setDiscoveryJobs] = useState<Job[]>([])

  const loadStatus = async () => {
    try {
      const rawStatus = await pipelineStatus()
      const normalizedStatus = normalizePipelineStatus(rawStatus)
      setStatus(normalizedStatus)
    } catch (error) {
      console.error('Failed to load pipeline status:', error)
      // Set default normalized status on error
      setStatus(normalizePipelineStatus(null))
    } finally {
      setLoading(false)
    }
  }

  const loadDiscoveryJobs = async () => {
    try {
      const jobs = await listJobs(0, 50)
      const discoveryJobsList = jobs.filter((j: Job) => j.job_type === 'discover')
      setDiscoveryJobs(discoveryJobsList)
    } catch (err) {
      console.error('Failed to load discovery jobs:', err)
    }
  }

  useEffect(() => {
    let abortController = new AbortController()
    let debounceTimeout: NodeJS.Timeout | null = null
    
    const loadStatusDebounced = () => {
      // Cancel previous request if still in flight
      abortController.abort()
      abortController = new AbortController()
      
      // Clear existing debounce timeout
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      
      // Debounce: wait 300ms before making request
      debounceTimeout = setTimeout(() => {
        loadStatus()
        loadDiscoveryJobs()
      }, 300)
    }
    
    // Initial load
    loadStatusDebounced()
    
    // Debounced refresh every 10 seconds
    const interval = setInterval(() => {
      loadStatusDebounced()
    }, 10000)
    
    // Listen for manual refresh requests (e.g., after composing email from Leads page)
    const handleRefreshPipelineStatus = () => {
      console.log('🔄 Pipeline status refresh requested...')
      loadStatusDebounced()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('refreshPipelineStatus', handleRefreshPipelineStatus)
    }
    
    return () => {
      abortController.abort()
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('refreshPipelineStatus', handleRefreshPipelineStatus)
      }
    }
  }, [])

  const handleDiscover = async () => {
    // Discovery form is handled in Step1Discovery component
    // This is just a placeholder - actual discovery happens in the step card
  }

  const handleScrape = async () => {
    try {
      await pipelineScrape()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start scraping')
    }
  }

  const handleApproveAll = async () => {
    try {
      const res = await pipelineApproveAll()
      alert(res.message || `Approved ${res.approved_count} websites`)
      await loadStatus()
      // Optionally, navigate user to Websites tab to review approved websites
      const event = new CustomEvent('change-tab', { detail: 'websites' })
      window.dispatchEvent(event)
    } catch (err: any) {
      alert(err.message || 'Failed to approve all websites')
    }
  }

  const handleVerify = async () => {
    try {
      await pipelineVerify()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start verification')
    }
  }

  const handleDraft = async () => {
    try {
      await pipelineDraft()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start drafting')
    }
  }

  const handleSend = async () => {
    try {
      await pipelineSend()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start sending')
    }
  }

  if (loading) {
    return (
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
        <div className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-olive-600" />
          <p className="text-gray-500 mt-2">Loading pipeline status...</p>
        </div>
      </div>
    )
  }

  // Normalized status is guaranteed to have all fields as numbers
  // If status is null, use normalized empty status
  const normalizedStatus: NormalizedPipelineStatus = status || normalizePipelineStatus(null)

  const latestDiscoveryJob = discoveryJobs.length > 0
    ? discoveryJobs.sort((a: Job, b: Job) => {
        const dateA = new Date(a.created_at || 0).getTime()
        const dateB = new Date(b.created_at || 0).getTime()
        return dateB - dateA
      })[0]
    : null

  const steps: StepCard[] = [
    {
      id: 1,
      name: 'Website Discovery',
      description: 'Find websites using DataForSEO',
      icon: Search,
      status: normalizedStatus.discovered > 0 ? 'completed' : 'active',
      count: normalizedStatus.discovered,
      ctaText: normalizedStatus.discovered > 0 ? 'View Websites' : 'Start Discovery',
      ctaAction: () => {
        // Navigate to Websites tab or show discovery form
        if (normalizedStatus.discovered > 0) {
          // Trigger tab change via custom event
          const event = new CustomEvent('change-tab', { detail: 'websites' })
          window.dispatchEvent(event)
        } else {
          // Show discovery form modal
          const event = new CustomEvent('show-discovery-form')
          window.dispatchEvent(event)
        }
      },
      jobStatus: latestDiscoveryJob?.status
    },
    {
      id: 2,
      name: 'Scraping',
      description: 'Extract emails from approved websites',
      icon: Scissors,
      // UNLOCK as soon as we have at least one scrape-ready website from the backend
      status: normalizedStatus.scrape_ready_count === 0 ? 'locked' :
              normalizedStatus.scraped > 0 ? 'completed' : 'active',
      count: normalizedStatus.scraped,
      ctaText: normalizedStatus.scrape_ready_count === 0
        ? 'Discover Websites First'
        : normalizedStatus.scraped > 0
        ? 'View Prospects'
        : 'Start Scraping',
      ctaAction: () => {
        // If nothing is scrape-ready yet, guide user back to discovery
        if (normalizedStatus.scrape_ready_count === 0) {
          const event = new CustomEvent('show-discovery-form')
          window.dispatchEvent(event)
          return
        }

        // If scraping already ran, take user to leads
        if (normalizedStatus.scraped > 0) {
          const event = new CustomEvent('change-tab', { detail: 'leads' })
          window.dispatchEvent(event)
          return
        }

        // Otherwise start scraping approved websites
        handleScrape()
      }
    },
    {
      id: 3,
      name: 'Verification',
      description: 'Verify emails with Snov.io',
      icon: Shield,
      status: normalizedStatus.leads === 0 ? 'locked' :
              normalizedStatus.emails_verified > 0 ? 'completed' : 'active',
      count: normalizedStatus.emails_verified,
      ctaText: normalizedStatus.leads === 0 ? 'Scrape Websites First' :
               normalizedStatus.emails_verified > 0 ? 'View Verified' : 'Start Verification',
      ctaAction: () => {
        if (normalizedStatus.leads === 0) {
          alert('Please scrape websites first to create leads')
          return
        }
        handleVerify()
      }
    },
    {
      id: 4,
      name: 'Drafting',
      description: 'Generate outreach emails with Gemini',
      icon: FileText,
      status: normalizedStatus.drafting_ready === 0 ? 'locked' :
              normalizedStatus.drafted > 0 ? 'completed' : 'active',
      count: normalizedStatus.drafted,
      ctaText: normalizedStatus.drafting_ready === 0 ? 'Verify Leads First' :
               normalizedStatus.drafted > 0 ? 'View Drafts' : 'Start Drafting',
      ctaAction: () => {
        if (normalizedStatus.drafting_ready === 0) {
          alert('Please verify leads first. Leads must be promoted, have emails, and be verified.')
          return
        }
        handleDraft()
      }
    },
    {
      id: 5,
      name: 'Sending',
      description: 'Send emails via Gmail API',
      icon: Send,
      status: normalizedStatus.drafted === 0 ? 'locked' :
              normalizedStatus.sent > 0 ? 'completed' : 'active',
      count: normalizedStatus.sent,
      ctaText: normalizedStatus.drafted === 0 ? 'Draft Emails First' :
               normalizedStatus.sent > 0 ? 'View Sent' : 'Start Sending',
      ctaAction: () => {
        if (normalizedStatus.drafted === 0) {
          alert('Please draft emails first')
          return
        }
        handleSend()
      }
    }
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">Lead Acquisition Pipeline</h2>
          <button
            onClick={loadStatus}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
        <p className="text-gray-600 text-sm">
          Orchestrate your lead acquisition process step by step. Each stage must be completed before the next can begin.
        </p>
      </div>

      {/* Step Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {steps.map((step, index) => {
          const Icon = step.icon
          const isCompleted = step.status === 'completed'
          const isLocked = step.status === 'locked'
          const isActive = step.status === 'active'
          
          return (
            <div
              key={step.id}
              className={`bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 p-6 ${
                isCompleted
                  ? 'border-green-500'
                  : isLocked
                  ? 'border-gray-300 opacity-60'
                  : 'border-olive-600'
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-full ${
                  isCompleted
                    ? 'bg-green-500 text-white'
                    : isLocked
                    ? 'bg-gray-300 text-gray-500'
                    : 'bg-olive-600 text-white'
                }`}>
                  <Icon className="w-6 h-6" />
                </div>
                {isCompleted && (
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                )}
                {isLocked && (
                  <Lock className="w-6 h-6 text-gray-400" />
                )}
              </div>

              <h3 className="text-lg font-bold text-gray-900 mb-2">{step.name}</h3>
              <p className="text-sm text-gray-600 mb-4">{step.description}</p>

              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{step.count}</p>
                  <p className="text-xs text-gray-500">
                    {step.id === 1 && `${normalizedStatus.discovered} discovered`}
                    {step.id === 2 && `${normalizedStatus.scraped} scraped • ${normalizedStatus.email_found || 0} with emails`}
                    {step.id === 3 && `${normalizedStatus.leads} leads • ${normalizedStatus.emails_verified} verified`}
                    {step.id === 4 && `${normalizedStatus.drafting_ready || 0} ready • ${normalizedStatus.drafted} drafted`}
                    {step.id === 5 && `${normalizedStatus.sent} sent`}
                    {!step.id && `${step.count} ${step.count === 1 ? 'item' : 'items'} ${isCompleted ? 'completed' : 'ready'}`}
                  </p>
                  {step.id === 2 && (
                    <div className="mt-1 space-y-1">
                      <p className="text-xs text-gray-500">
                        Discovered: {normalizedStatus.discovered} • Scrape-ready: {normalizedStatus.scrape_ready_count}
                      </p>
                      {normalizedStatus.scrape_ready_count === 0 && (
                        <p className="text-xs text-red-500">
                          Blocked: No discovered websites yet. Run discovery first.
                        </p>
                      )}
                    </div>
                  )}
                  {step.id === 3 && (
                    <div className="mt-1 space-y-1">
                      <p className="text-xs text-gray-500">
                        Email found: {normalizedStatus.email_found || 0} • Promoted to lead: {normalizedStatus.leads}
                      </p>
                      {normalizedStatus.leads === 0 && normalizedStatus.email_found > 0 && (
                        <p className="text-xs text-yellow-600">
                          {normalizedStatus.email_found} prospects with emails need promotion to lead
                        </p>
                      )}
                    </div>
                  )}
                </div>
                {step.jobStatus && (
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    step.jobStatus === 'completed' ? 'bg-green-100 text-green-800' :
                    step.jobStatus === 'running' ? 'bg-yellow-100 text-yellow-800' :
                    step.jobStatus === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {step.jobStatus}
                  </span>
                )}
              </div>

              <button
                onClick={step.ctaAction}
                disabled={isLocked}
                className={`w-full px-4 py-2 rounded-md font-medium flex items-center justify-center space-x-2 ${
                  isLocked
                    ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                    : isCompleted
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : 'bg-olive-600 text-white hover:bg-olive-700'
                }`}
              >
                <span>{step.ctaText}</span>
                {!isLocked && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          )
        })}
      </div>

      {/* Discovery Form (shown when triggered) */}
      <Step1Discovery onComplete={loadStatus} />
    </div>
  )
}

// Step 1 Discovery Form Component
function Step1Discovery({ onComplete }: { onComplete: () => void }) {
  const [showForm, setShowForm] = useState(false)
  const [categories, setCategories] = useState<string[]>([])
  const [locations, setLocations] = useState<string[]>([])
  const [keywords, setKeywords] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const handleShowForm = () => setShowForm(true)
    window.addEventListener('show-discovery-form', handleShowForm)
    return () => window.removeEventListener('show-discovery-form', handleShowForm)
  }, [])

  const availableCategories = [
    'Art Gallery', 'Museum', 'Art Studio', 'Art School', 'Art Fair', 
    'Art Dealer', 'Art Consultant', 'Art Publisher', 'Art Magazine'
  ]

  const availableLocations = [
    'United States', 'United Kingdom', 'Canada', 'Australia', 'Germany',
    'France', 'Italy', 'Spain', 'Netherlands', 'Belgium'
  ]

  const handleDiscover = async () => {
    if (categories.length === 0) {
      setError('Please select at least one category')
      return
    }
    if (locations.length === 0) {
      setError('Please select at least one location')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(false)

    try {
      await pipelineDiscover({
        categories,
        locations,
        keywords: keywords.trim() || undefined,
        max_results: 100
      })
      setSuccess(true)
      setShowForm(false)
      setTimeout(() => {
        onComplete()
        setSuccess(false)
      }, 2000)
    } catch (err: any) {
      setError(err.message || 'Failed to start discovery')
    } finally {
      setLoading(false)
    }
  }

  if (!showForm) return null

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-900">Step 1: Website Discovery</h3>
        <button
          onClick={() => setShowForm(false)}
          className="text-gray-500 hover:text-gray-700"
        >
          ×
        </button>
      </div>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Categories (Required) *
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {availableCategories.map(cat => (
              <label key={cat} className="flex items-center space-x-2 p-2 border rounded hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={categories.includes(cat)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setCategories([...categories, cat])
                    } else {
                      setCategories(categories.filter(c => c !== cat))
                    }
                  }}
                />
                <span className="text-sm">{cat}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Locations (Required) *
          </label>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {availableLocations.map(loc => (
              <label key={loc} className="flex items-center space-x-2 p-2 border rounded hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={locations.includes(loc)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setLocations([...locations, loc])
                    } else {
                      setLocations(locations.filter(l => l !== loc))
                    }
                  }}
                />
                <span className="text-sm">{loc}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Keywords (Optional)
          </label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., contemporary art, abstract painting"
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-olive-500 focus:border-olive-500"
          />
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
            ✅ Discovery job started! Check the Websites tab to see results.
          </div>
        )}

        <button
          onClick={handleDiscover}
          disabled={loading || categories.length === 0 || locations.length === 0}
          className="w-full px-6 py-3 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Starting Discovery...</span>
            </>
          ) : (
            <>
              <Search className="w-5 h-5" />
              <span>Find Websites</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}
