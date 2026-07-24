'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Lock, Loader2, Search, Scissors, Shield, Eye, FileText, Send, RefreshCw, ArrowRight, AlertCircle } from 'lucide-react'
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
  isMasterSwitchEnabled,
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
  viewText?: string  // Optional "View" button text (e.g., "View Prospects", "View Sent")
  viewAction?: () => void  // Optional "View" button action (navigates to tab)
  jobStatus?: string
}

export default function Pipeline() {
  const [status, setStatus] = useState<NormalizedPipelineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [discoveryJobs, setDiscoveryJobs] = useState<Job[]>([])
  const [masterSwitchEnabled, setMasterSwitchEnabled] = useState(false)
  const [latestDiscoveryJobId, setLatestDiscoveryJobId] = useState<string | null>(null)
  // Track the last discovery job ID that we've already processed/reset for
  const [lastProcessedDiscoveryJobId, setLastProcessedDiscoveryJobId] = useState<string | null>(null)

  // Check master switch status
  useEffect(() => {
    const checkMasterSwitch = () => {
      const enabled = isMasterSwitchEnabled()
      setMasterSwitchEnabled(enabled)
    }
    
    // Check on mount
    checkMasterSwitch()
    
    // Listen for changes
    const handleMasterSwitchChange = (e: CustomEvent) => {
      setMasterSwitchEnabled(e.detail.enabled)
    }
    
    window.addEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
    
    return () => {
      window.removeEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
    }
  }, [])

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

  const loadDiscoveryJobs = async (checkForNewJob: boolean = true) => {
    try {
      const jobs = await listJobs(0, 50)
      const discoveryJobsList = jobs.filter((j: Job) => j.job_type === 'discover')
      setDiscoveryJobs(discoveryJobsList)
      
      // Only check for new jobs if explicitly requested (not on network refreshes)
      if (!checkForNewJob) {
        return
      }
      
      // Track latest discovery job to detect new discovery runs
      if (discoveryJobsList.length > 0) {
        const latestJob = discoveryJobsList.sort((a: Job, b: Job) => {
          const dateA = new Date(a.created_at || 0).getTime()
          const dateB = new Date(b.created_at || 0).getTime()
          return dateB - dateA
        })[0]
        
        // Only reset if this is a truly NEW job that we haven't processed yet
        // Compare against lastProcessedDiscoveryJobId, not latestDiscoveryJobId
        if (latestJob.id && latestJob.id !== lastProcessedDiscoveryJobId) {
          // Update both tracking states immediately to prevent repeated resets
          setLatestDiscoveryJobId(latestJob.id)
          setLastProcessedDiscoveryJobId(latestJob.id)
          // Reset pipeline state by reloading status
          // This ensures buttons are re-enabled based on current data
          console.log('🔄 New discovery detected, resetting pipeline state', latestJob.id)
          loadStatus()
        }
      }
    } catch (err) {
      console.error('Failed to load discovery jobs:', err)
    }
  }

  useEffect(() => {
    let abortController = new AbortController()
    
    // Initial load only - no polling
    loadStatus()
    // On initial load, check for new jobs
    loadDiscoveryJobs(true)
    
    // Listen for manual refresh requests (e.g., after composing email from Leads page)
    // Do NOT check for new jobs on refresh - only refresh status
    const handleRefreshPipelineStatus = () => {
      console.log('🔄 Pipeline status refresh requested...')
      loadStatus()
      // Load jobs list but don't check for new jobs (prevents false resets)
      loadDiscoveryJobs(false)
    }
    
    // Listen for discovery completion to reset pipeline state
    // Only reset if we have a confirmed new job ID
    const handleDiscoveryCompleted = () => {
      console.log('🔄 Discovery completed event received...')
      // Load discovery jobs to check for new job ID
      // Pass true to check for new jobs
      loadDiscoveryJobs(true).then(() => {
        // Status will be reloaded by loadDiscoveryJobs if new job detected
      }).catch(err => {
        console.error('Failed to load discovery jobs after discovery completed:', err)
        // Don't reset state on error - treat as false positive
      })
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('refreshPipelineStatus', handleRefreshPipelineStatus)
      window.addEventListener('discoveryCompleted', handleDiscoveryCompleted)
    }
    
    return () => {
      abortController.abort()
      if (typeof window !== 'undefined') {
        window.removeEventListener('refreshPipelineStatus', handleRefreshPipelineStatus)
        window.removeEventListener('discoveryCompleted', handleDiscoveryCompleted)
      }
    }
  }, [])

  const handleDiscover = async () => {
    // Discovery form is handled in Step1Discovery component
    // This is just a placeholder - actual discovery happens in the step card
  }

  const handleScrape = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      await pipelineScrape()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start scraping')
    }
  }

  const handleApproveAll = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
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
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      await pipelineVerify()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start verification')
    }
  }

  const handleDraft = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    
    try {
      // Call pipelineDraft without prospect_ids to automatically draft for ALL verified prospects
      // This includes leads and scraped emails (any prospect with verification_status='verified' and contact_email IS NOT NULL)
      const result = await pipelineDraft()
      
      if (!result.job_id) {
        throw new Error('No job ID returned from drafting request')
      }
      
      // Check if component is still mounted (for Next.js client component)
      if (typeof window === 'undefined') {
        return
      }
      
      // Show success message
      console.log('✅ Drafting job started:', result.job_id)
      
      // Start polling for job status (same as LeadsTable) - continue until completion
      const { getDraftJobStatus } = await import('@/lib/api')
      const pollInterval = setInterval(async () => {
        try {
          const status = await getDraftJobStatus(result.job_id)
          
          if (status.status === 'failed') {
            clearInterval(pollInterval)
            console.error('❌ Drafting failed:', status.error_message)
            return
          }
          
          if (status.status === 'completed') {
            clearInterval(pollInterval)
            console.log(`✅ Drafting completed! ${status.drafts_created} drafts created.`)
            
            // Trigger pipeline status refresh
            await loadStatus()
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
              window.dispatchEvent(new CustomEvent('jobsCompleted'))
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }
            return
          }
          
          // Update progress
          if (status.status === 'running') {
            console.log(`⏳ Drafting in progress... ${status.drafts_created}${status.total_targets ? ` / ${status.total_targets}` : ''} drafts created`)
            
            // Refresh drafts list periodically while drafting
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }
          }
        } catch (pollErr: any) {
          console.error('Error polling draft job status:', pollErr)
          // Keep polling on error - job might still be running
        }
      }, 3000) // Poll every 3 seconds
      
      // Trigger pipeline status refresh immediately
      await loadStatus()
      
      // Trigger refresh events
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
        window.dispatchEvent(new CustomEvent('refreshDrafts'))
      }
      
      // Navigate to Drafts tab after a short delay
      setTimeout(() => {
        if (typeof window !== 'undefined') {
          const event = new CustomEvent('change-tab', { detail: 'drafts' })
          window.dispatchEvent(event)
        }
      }, 1500)
    } catch (err: any) {
      // Show error message - 422 is a valid business rule, not a crash
      const errorMessage = err?.message || 'Failed to start drafting'
      console.error('❌', errorMessage)
      alert(errorMessage)
      
      // Do NOT update state here - let the error be handled by the alert
      // This prevents React invariant violations
    }
  }

  const handleSend = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      await pipelineSend()
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to start sending')
    }
  }

  if (loading) {
    return (
      <div className="glass rounded-xl shadow-lg p-4 animate-fade-in">
        <div className="text-center py-4">
          <div className="relative inline-block">
            <div className="w-8 h-8 rounded-full border-2 border-olive-200"></div>
            <div className="absolute top-0 left-0 w-8 h-8 rounded-full border-2 border-t-olive-600 border-r-olive-500 animate-spin"></div>
          </div>
          <p className="text-gray-600 mt-2 text-sm font-medium">Loading pipeline...</p>
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
        if (!masterSwitchEnabled) {
          alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
          return
        }
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
        : 'Start Scraping',
      ctaAction: () => {
        // If nothing is scrape-ready yet, guide user back to discovery
        if (normalizedStatus.scrape_ready_count === 0) {
          const event = new CustomEvent('show-discovery-form')
          window.dispatchEvent(event)
          return
        }
        // Start scraping approved websites
        handleScrape()
      },
      viewText: normalizedStatus.scraped > 0 ? 'View Prospects' : undefined,
      viewAction: normalizedStatus.scraped > 0 ? () => {
        const event = new CustomEvent('change-tab', { detail: 'leads' })
        window.dispatchEvent(event)
      } : undefined
    },
    {
      id: 3,
      name: 'Verification',
      description: 'Verify emails with Snov.io',
      icon: Shield,
      status: normalizedStatus.leads === 0 ? 'locked' :
              normalizedStatus.emails_verified > 0 ? 'completed' : 'active',
      count: normalizedStatus.emails_verified,
      ctaText: normalizedStatus.leads === 0 ? 'Scrape Websites First' : 'Start Verification',
      ctaAction: () => {
        if (normalizedStatus.leads === 0) {
          alert('Please scrape websites first to create leads')
          return
        }
        handleVerify()
      },
      viewText: normalizedStatus.emails_verified > 0 ? 'View Verified' : undefined,
      viewAction: normalizedStatus.emails_verified > 0 ? () => {
        const event = new CustomEvent('change-tab', { detail: 'leads' })
        window.dispatchEvent(event)
      } : undefined
    },
    {
      id: 4,
      name: 'Drafting',
      description: 'Generate outreach emails with Gemini',
      icon: FileText,
      // UNLOCK when drafts exist OR when verified prospects exist (drafting_ready > 0)
      // This allows composing even if not all prospects are verified yet
      status: (normalizedStatus.drafted > 0 || normalizedStatus.drafting_ready > 0) 
        ? (normalizedStatus.drafted > 0 ? 'completed' : 'active')
        : 'locked',
      count: normalizedStatus.drafted,
      ctaText: normalizedStatus.drafting_ready === 0 && normalizedStatus.drafted === 0 
        ? 'Verify Leads First' 
        : 'Start Drafting',
      ctaAction: () => {
        if (normalizedStatus.drafting_ready === 0 && normalizedStatus.drafted === 0) {
          alert('Please verify leads first. Leads must be promoted, have emails, and be verified.')
          return
        }
        handleDraft()
      },
      viewText: normalizedStatus.drafted > 0 ? 'View Drafts' : undefined,
      viewAction: normalizedStatus.drafted > 0 ? () => {
        const event = new CustomEvent('change-tab', { detail: 'drafts' })
        window.dispatchEvent(event)
      } : undefined
    },
    {
      id: 5,
      name: 'Sending',
      description: 'Send emails via Gmail API',
      icon: Send,
      // UNLOCK when drafts exist (drafted > 0) OR when send-ready exists (send_ready_count > 0)
      // Backend will filter to only send verified + drafted + not sent prospects
      status: (normalizedStatus.drafted > 0 || normalizedStatus.send_ready_count > 0)
        ? (normalizedStatus.sent > 0 ? 'completed' : 'active')
        : 'locked',
      count: normalizedStatus.sent,
      ctaText: (normalizedStatus.drafted > 0 || normalizedStatus.send_ready_count > 0)
        ? 'Start Sending'
        : 'No Emails Ready',
      ctaAction: () => {
        if (normalizedStatus.send_ready_count === 0 && normalizedStatus.drafted === 0) {
          alert('No emails ready for sending. Ensure prospects have verified email, draft subject, and draft body.')
          return
        }
        handleSend()
      },
      viewText: normalizedStatus.sent > 0 ? 'View Sent' : undefined,
      viewAction: normalizedStatus.sent > 0 ? () => {
        const event = new CustomEvent('change-tab', { detail: 'emails' })
        window.dispatchEvent(event)
      } : undefined
    }
  ]

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="glass rounded-xl shadow-lg p-3 border border-olive-200">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-sm font-bold text-olive-700 mb-1">Outreach Pipeline</h2>
            <p className="text-gray-600 text-xs">
              Transform prospects into connections with Liquid Canvas
            </p>
          </div>
          <button
            onClick={loadStatus}
            className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg transition-all duration-200 text-xs font-medium hover:bg-olive-700 hover:shadow-md"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>
        {!masterSwitchEnabled && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <p className="text-xs text-red-700">
                <span className="font-semibold">Master switch is OFF</span> — Enable it in Automation Control to use pipeline activities.
              </p>
            </div>
          </div>
        )}
        {masterSwitchEnabled && (
          <div className="mt-2 p-2 bg-gradient-to-r from-olive-50 to-olive-50 rounded-lg border border-olive-200">
            <p className="text-xs text-gray-700">
              <span className="font-semibold">Orchestrate your creative outreach</span> — Each stage builds on the previous, creating meaningful connections through art and creativity.
            </p>
          </div>
        )}
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
              className={`glass rounded-xl shadow-lg p-3 border transition-all duration-300 hover:shadow-xl hover:scale-102 animate-slide-up ${
                isCompleted
                  ? 'border-olive-300 bg-gradient-to-br from-olive-50/80 to-olive-50/50'
                  : isLocked
                  ? 'border-gray-200 opacity-60'
                  : 'border-olive-300 bg-gradient-to-br from-olive-50/80 to-olive-50/50'
              }`}
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className={`p-2 rounded-lg shadow-md transition-all duration-300 ${
                  isCompleted
                    ? 'bg-olive-600 text-white'
                    : isLocked
                    ? 'bg-gray-300 text-gray-500'
                    : 'bg-olive-600 text-white hover-glow'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                {isCompleted && (
                  <CheckCircle2 className="w-4 h-4 text-olive-600 animate-scale-in" />
                )}
                {isLocked && (
                  <Lock className="w-4 h-4 text-gray-400" />
                )}
              </div>

              <h3 className="text-sm font-bold text-gray-900 mb-1">{step.name}</h3>
              <p className="text-xs text-gray-600 mb-2">{step.description}</p>

              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-lg font-bold text-olive-700">{step.count}</p>
                  <p className="text-xs text-gray-500">
                    {step.id === 1 && `${normalizedStatus.discovered} discovered`}
                    {step.id === 2 && `${normalizedStatus.scraped} scraped • ${normalizedStatus.email_found || 0} with emails`}
                    {step.id === 3 && `${normalizedStatus.leads} leads • ${normalizedStatus.emails_verified} verified`}
                    {step.id === 4 && `${normalizedStatus.drafting_ready || 0} ready • ${normalizedStatus.drafted} drafted`}
                    {step.id === 5 && `${normalizedStatus.sent} sent`}
                    {!step.id && `${step.count} ${step.count === 1 ? 'item' : 'items'} ${isCompleted ? 'completed' : 'ready'}`}
                  </p>
                  {step.id === 2 && (
                    <div className="mt-1 space-y-0.5">
                      <p className="text-xs text-gray-500">
                        Discovered: {normalizedStatus.discovered} • Scrape-ready: {normalizedStatus.scrape_ready_count}
                      </p>
                      {normalizedStatus.scrape_ready_count === 0 && (
                        <p className="text-xs text-olive-600">
                          Blocked: No discovered websites yet. Run discovery first.
                        </p>
                      )}
                    </div>
                  )}
                  {step.id === 3 && (
                    <div className="mt-1 space-y-0.5">
                      <p className="text-xs text-gray-500">
                        Email found: {normalizedStatus.email_found || 0} • Promoted to lead: {normalizedStatus.leads}
                      </p>
                      {normalizedStatus.leads === 0 && normalizedStatus.email_found > 0 && (
                        <p className="text-xs text-olive-600">
                          {normalizedStatus.email_found} prospects with emails need promotion to lead
                        </p>
                      )}
                    </div>
                  )}
                </div>
                {step.jobStatus && (
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                    step.jobStatus === 'completed' ? 'bg-olive-100 text-olive-800' :
                    step.jobStatus === 'running' ? 'bg-olive-100 text-olive-800' :
                    step.jobStatus === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {step.jobStatus}
                  </span>
                )}
              </div>

              <div className={`flex gap-2 ${step.viewText && step.viewAction ? 'flex-col' : ''}`}>
                {step.viewText && step.viewAction && (
                  <button
                    onClick={step.viewAction}
                    className="w-full px-2 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1 transition-all duration-200 bg-gray-100 text-gray-700 hover:bg-gray-200 hover:shadow-md"
                  >
                    <span>{step.viewText}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                )}
                <button
                  onClick={step.ctaAction}
                  disabled={isLocked || !masterSwitchEnabled}
                  className={`w-full px-2 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1 transition-all duration-200 ${
                    isLocked || !masterSwitchEnabled
                      ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                      : isCompleted
                      ? 'bg-olive-600 text-white hover:bg-olive-700 hover:shadow-md hover:scale-102'
                      : 'bg-olive-600 text-white hover:bg-olive-700 hover:shadow-md hover:scale-102'
                  }`}
                  title={!masterSwitchEnabled ? 'Master switch must be enabled' : undefined}
                >
                  <span>{step.ctaText}</span>
                  {!isLocked && masterSwitchEnabled && <ArrowRight className="w-3 h-3" />}
                </button>
              </div>
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
    'Art Lovers', 'Interior Design', 'Pet Lovers', 'Dogs and Cat Owners - Fur Parent', 'Childhood Development', 
    'Holidays', 'Famous Quotes', 'Home Decor', 
    'Audio Visual', 'Interior Decor', 'Holiday Decor', 'Home Tech', 
    'Parenting (Mom Site)', 'NFTs', 'Museum'
  ]

  const normalizeCategoryForBackend = (category: string) => {
    if (category === 'Parenting (Mom Site)') return 'Parenting'
    return category
  }

  const availableLocations = [
    'USA', 'Canada', 'UK / London', 'Germany', 'France', 'Europe'
  ]

  const handleDiscover = async () => {
    // Check master switch
    if (!isMasterSwitchEnabled()) {
      setError('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    
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
      // Debug: make it obvious what we are actually submitting (helps verify "selected all" runs)
      // Note: This is UI-only; backend already supports arrays.
      if (process.env.NODE_ENV !== 'production') {
        console.log('🔍 [WEBSITE DISCOVERY] Submitting discovery request:', {
          categories_count: categories.length,
          locations_count: locations.length,
          categories,
          locations,
          keywords: keywords.trim() || '(none)',
          max_results: 100,
        })
      }
      await pipelineDiscover({
        categories: categories.map(normalizeCategoryForBackend),
        locations,
        keywords: keywords.trim() || undefined,
        max_results: 100
      })
      setSuccess(true)
      setShowForm(false)
      
      // Trigger discovery completion event to reset pipeline state
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('discoveryCompleted'))
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
      }
      
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
    <div className="glass rounded-xl shadow-lg border border-liquid-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold liquid-gradient-text">Step 1: Website Discovery</h3>
        <button
          onClick={() => setShowForm(false)}
          className="text-gray-500 hover:text-liquid-600 text-lg"
        >
          ×
        </button>
      </div>

      <div className="mb-3 flex items-center justify-between text-xs">
        <div className="text-gray-600">
          Selected: <span className="font-semibold text-gray-800">{categories.length}</span> categories,
          <span className="ml-1 font-semibold text-gray-800">{locations.length}</span> locations
        </div>
        <button
          type="button"
          onClick={() => {
            setCategories(availableCategories)
            setLocations(availableLocations)
            setError(null)
          }}
          className="px-2 py-1 rounded-md border border-olive-200 bg-white hover:bg-olive-50 text-olive-700 font-semibold"
        >
          Select all
        </button>
      </div>
      
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Categories (Required) *
          </label>
          <div className="flex items-center justify-end gap-2 mb-1.5">
            <button
              type="button"
              onClick={() => {
                setCategories(availableCategories)
                setError(null)
              }}
              className="text-[11px] font-semibold text-olive-700 hover:text-olive-800"
            >
              Select all
            </button>
            <span className="text-gray-300">|</span>
            <button
              type="button"
              onClick={() => {
                setCategories([])
                setError(null)
              }}
              className="text-[11px] font-semibold text-gray-600 hover:text-gray-800"
            >
              Clear
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5">
            {availableCategories.map(cat => (
              <label key={cat} className="flex items-center space-x-1.5 p-1.5 border border-olive-200 rounded hover:bg-olive-50 cursor-pointer">
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
                  className="accent-olive-600"
                />
                <span className="text-xs">{cat}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Locations (Required) *
          </label>
          <div className="flex items-center justify-end gap-2 mb-1.5">
            <button
              type="button"
              onClick={() => {
                setLocations(availableLocations)
                setError(null)
              }}
              className="text-[11px] font-semibold text-olive-700 hover:text-olive-800"
            >
              Select all
            </button>
            <span className="text-gray-300">|</span>
            <button
              type="button"
              onClick={() => {
                setLocations([])
                setError(null)
              }}
              className="text-[11px] font-semibold text-gray-600 hover:text-gray-800"
            >
              Clear
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-1.5">
            {availableLocations.map(loc => (
              <label key={loc} className="flex items-center space-x-1.5 p-1.5 border border-olive-200 rounded hover:bg-olive-50 cursor-pointer">
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
                  className="accent-olive-600"
                />
                <span className="text-xs">{loc}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Keywords (Optional)
          </label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., contemporary art, abstract painting"
            className="w-full px-2 py-1.5 text-xs border border-olive-200 rounded-lg focus:ring-olive-500 focus:border-olive-500"
          />
        </div>

        {error && (
          <div className="p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
            {error}
          </div>
        )}

        {success && (
          <div className="p-2 bg-olive-50 border border-olive-200 rounded text-olive-700 text-xs">
            ✅ Discovery job started! Check the Websites tab to see results.
          </div>
        )}

        <button
          onClick={handleDiscover}
          disabled={loading || categories.length === 0 || locations.length === 0}
          className="w-full px-3 py-2 bg-olive-600 text-white rounded-lg hover:bg-olive-700 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 text-xs font-semibold"
        >
          {loading ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Starting Discovery...</span>
            </>
          ) : (
            <>
              <Search className="w-3 h-3" />
              <span>Find Websites</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}
