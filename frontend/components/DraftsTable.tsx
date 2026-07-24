'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { FileText, RefreshCw, Send, Edit, X, Loader2, Download, Mail, CheckCircle } from 'lucide-react'
import { listProspects, pipelineDraft, pipelineSend, updateProspectDraft, exportProspectsCSV, getDraftJobStatus, uploadProspectAttachment, type Prospect, type DraftJobStatusResponse } from '@/lib/api'
import RichEmailEditor from '@/components/RichEmailEditor'

export default function DraftsTable() {
  const [allDrafts, setAllDrafts] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  // Use a higher limit for drafts to ensure we get all drafts, not just first 50
  const limit = 1000
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)
  const [editingProspect, setEditingProspect] = useState<string | null>(null)
  const [editSubject, setEditSubject] = useState('')
  const [editBody, setEditBody] = useState('')
  const [editCc, setEditCc] = useState('')
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [locationQuery, setLocationQuery] = useState<string>('')

  const availableCategories = [
    'Art Lovers',
    'Interior Design',
    'Pet Lovers',
    'Dogs and Cat Owners - Fur Parent',
    'Childhood Development',
    'Holidays',
    'Famous Quotes',
    'Home Decor',
    'Audio Visual',
    'Interior Decor',
    'Holiday Decor',
    'Home Tech',
    'Parenting (Mom Site)',
    'NFTs',
    'Museum',
  ]

  const mapCategoryForDisplay = (category?: string | null) => {
    if (!category) return category
    if (category === 'Parenting') return 'Parenting (Mom Site)'
    return category
  }

  const [showGlobalAdd, setShowGlobalAdd] = useState(false)
  const [globalCc, setGlobalCc] = useState('')
  const [globalImageFile, setGlobalImageFile] = useState<File | null>(null)
  const [globalImageDataUrl, setGlobalImageDataUrl] = useState<string>('')
  const [globalImageSize, setGlobalImageSize] = useState<'sm' | 'md' | 'lg' | 'full'>('md')
  const [globalDocFile, setGlobalDocFile] = useState<File | null>(null)
  const [isApplyingGlobalAdd, setIsApplyingGlobalAdd] = useState(false)

  const getCcStorageKey = (prospectId: string) => `prospect_cc_${prospectId}`
  
  // Draft request state machine: single source of truth
  const [draftState, setDraftState] = useState<{
    status: 'idle' | 'loading' | 'success' | 'error'
    message: string | null
    jobId: string | null
    progress: {
      drafts_created: number
      total_targets: number | null
      status: 'pending' | 'running' | 'completed' | 'failed'
    } | null
  }>({ 
    status: 'idle', 
    message: null,
    jobId: null,
    progress: null
  })
  
  const [hasAutoDrafted, setHasAutoDrafted] = useState(false)
  const mountedRef = useRef(true)
  const abortControllerRef = useRef<AbortController | null>(null)
  // Ref for checking state without causing re-renders or closure issues
  const draftStateRef = useRef<'idle' | 'loading' | 'success' | 'error'>('idle')

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      // Cancel any in-flight requests
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
    }
  }, [])
  
  // Sync ref with state in useEffect to avoid render-time side effects
  useEffect(() => {
    draftStateRef.current = draftState.status
  }, [draftState.status])

  // Track if this is the initial load to determine error handling behavior
  const isInitialLoadRef = useRef(true)
  
  const loadDrafts = useCallback(async () => {
    // Only update loading state if component is mounted
    if (!mountedRef.current) return
    
    const isInitial = isInitialLoadRef.current
    isInitialLoadRef.current = false
    
    try {
      setLoading(true)
      setError(null)
      // Load ALL prospects with a high limit to find all drafts (not just first 50)
      // This ensures drafts from leads and scraped emails are included, even if they're not in the first page
      const response = await listProspects(0, 1000)
      
      // Check if component unmounted during async operation
      if (!mountedRef.current) return
      
      const allProspects = Array.isArray(response?.data) ? response.data : []
      
      // Filter for prospects with drafts from ANY source (website, leads, scraped_emails)
      // Include all prospects that have draft_subject and draft_body, regardless of source_type
      // Check for both non-null and non-empty strings to ensure valid drafts
      const draftedProspects = allProspects.filter((p: Prospect) => {
        const hasSubject = p.draft_subject && p.draft_subject.trim().length > 0
        const hasBody = p.draft_body && p.draft_body.trim().length > 0
        const outreachStatus = (p as any).outreach_status ? String((p as any).outreach_status).toLowerCase() : ''
        const sendStatus = (p as any).send_status ? String((p as any).send_status).toLowerCase() : ''
        const lastSent = (p as any).last_sent
        const isSent = outreachStatus === 'sent' || sendStatus === 'sent' || !!lastSent
        return hasSubject && hasBody && !isSent
      })
      
      // Debug log to help diagnose filtering issues (always log in production for debugging)
      console.log(`🔍 [DRAFTS] Filtered ${draftedProspects.length} drafts from ${allProspects.length} total prospects`)
      if (draftedProspects.length === 0 && allProspects.length > 0) {
        // Check if any prospects have partial drafts
        const withSubject = allProspects.filter((p: Prospect) => p.draft_subject && p.draft_subject.trim().length > 0)
        const withBody = allProspects.filter((p: Prospect) => p.draft_body && p.draft_body.trim().length > 0)
        console.log(`🔍 [DRAFTS] Debug: ${withSubject.length} with subject, ${withBody.length} with body`)
        // Log sample prospects to see what we're getting
        if (allProspects.length > 0) {
          const sample = allProspects[0]
          console.log(`🔍 [DRAFTS] Sample prospect:`, {
            id: sample.id,
            has_draft_subject: !!sample.draft_subject,
            has_draft_body: !!sample.draft_body,
            draft_subject_length: sample.draft_subject?.length || 0,
            draft_body_length: sample.draft_body?.length || 0
          })
        }
      }
      
      // Only update state if component is still mounted
      if (mountedRef.current) {
        setAllDrafts(
          draftedProspects.map((p: any) => ({
            ...p,
            discovery_category: mapCategoryForDisplay(p.discovery_category),
          }))
        )
        // Total is the count of drafted prospects, not all prospects
        setTotal(draftedProspects.length)
        setError(null) // Clear error on successful load
      }
    } catch (error: any) {
      // Check if component unmounted during error handling
      if (!mountedRef.current) return
      
      console.error('Failed to load drafts:', error)
      
      // Extract error message - distinguish network errors from business logic errors
      const errorMessage = error?.message || 'Failed to load drafts'
      
      // Set error state but DO NOT clear prospects array on subsequent loads
      // This allows error message to display while preserving any previously loaded data
      setError(errorMessage)
      
      // Only clear prospects if this is the initial load (no existing data)
      // This prevents "No drafts found" from showing when there's an error
      if (isInitial && mountedRef.current) {
        setAllDrafts([])
        setTotal(0)
      }
    } finally {
      // Only update loading state if component is still mounted
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [skip, limit]) // Remove prospects.length from dependencies to prevent loops

  const filteredDrafts = allDrafts.filter((p) => {
    try {
      if (categoryFilter) {
        const cat = ((p as any).discovery_category ?? '').toString().trim()
        if (cat !== categoryFilter) return false
      }

      const rawQuery = (locationQuery ?? '').toString()
      if (rawQuery.trim()) {
        const q = rawQuery.trim().toLowerCase()
        const loc = ((p as any).discovery_location ?? '').toString().toLowerCase()
        const domainLoc = (extractLocationFromDomain(p.domain, p.contact_email) ?? '').toString().toLowerCase()
        const domain = (p?.domain ?? '').toString().toLowerCase()
        const email = (p?.contact_email ?? '').toString().toLowerCase()
        if (!loc.includes(q) && !domainLoc.includes(q) && !domain.includes(q) && !email.includes(q)) return false
      }

      return true
    } catch (e) {
      console.error('Drafts filter error (skipping row):', e, p)
      return true
    }
  })

  const buildGlobalBlockHtml = useCallback(() => {
    const docName = globalDocFile?.name || ''

    const widthPx =
      globalImageSize === 'sm'
        ? 200
        : globalImageSize === 'md'
          ? 360
          : globalImageSize === 'lg'
            ? 520
            : null

    // Inline image (no external link). This renders in the email body and supports sizing.
    const imgHtml = globalImageDataUrl
      ? `<div style="margin: 12px 0 0 0;"><img src="${globalImageDataUrl}" alt="" style="${widthPx ? `width:${widthPx}px;` : ''}max-width:100%;height:auto;display:block;" /></div>`
      : ''

    const docHtml = docName
      ? `<div style="margin: 8px 0 0 0;"><em>Document attached: ${docName}</em></div>`
      : ''

    const html = `${imgHtml}${docHtml}`.trim()
    return html
  }, [globalDocFile, globalImageDataUrl, globalImageSize])

  const applyGlobalAdd = useCallback(async () => {
    if (selected.size === 0) {
      setError('Please select at least one draft before using Global Add')
      return
    }

    const blockHtml = buildGlobalBlockHtml()
    const nextCc = globalCc.trim()

    if (!blockHtml && !nextCc) {
      setError('Please attach an image, attach a document, or set a CC before applying Global Add')
      return
    }

    try {
      setIsApplyingGlobalAdd(true)
      setError(null)

      const draftById = new Map(allDrafts.map((p) => [p.id, p]))
      const ids = Array.from(selected)

      await Promise.all(
        ids.map(async (id) => {
          const p = draftById.get(id)
          if (!p) return

          // Upload attachments per-prospect so they will send with that prospect.
          // This is required because attachments are stored per-prospect in the DB.
          if (globalDocFile) {
            await uploadProspectAttachment({ prospectId: id, file: globalDocFile })
          }

          if (nextCc) {
            try {
              if (typeof window !== 'undefined') {
                window.localStorage.setItem(getCcStorageKey(id), nextCc)
              }
            } catch {
            }
          }

          if (blockHtml) {
            const existingBody = ((p as any).draft_body ?? '').toString()
            const body = `${existingBody}\n${blockHtml}`
            await updateProspectDraft(id, { body })
          }
        })
      )

      setShowGlobalAdd(false)
      setGlobalCc('')
      setGlobalImageFile(null)
      setGlobalImageDataUrl('')
      setGlobalDocFile(null)
      setGlobalImageSize('md')
      await loadDrafts()
    } catch (e: any) {
      setError(e?.message || 'Failed to apply Global Add')
    } finally {
      setIsApplyingGlobalAdd(false)
    }
  }, [allDrafts, buildGlobalBlockHtml, getCcStorageKey, globalCc, globalDocFile, loadDrafts, selected])

  useEffect(() => {
    setSelected((prev) => {
      if (prev.size === 0) return prev
      const allowed = new Set(filteredDrafts.map((p) => p.id))
      const next = new Set<string>()
      prev.forEach((id) => {
        if (allowed.has(id)) next.add(id)
      })
      return next
    })
  }, [categoryFilter, locationQuery, allDrafts])

  const handleAutoDraft = useCallback(async (showConfirm = true) => {
    // Prevent concurrent requests - check via ref to avoid closure issues
    if (draftStateRef.current === 'loading') {
      return
    }

    if (selected.size === 0) {
      if (mountedRef.current) {
        setDraftState({
          status: 'error',
          message: 'Please select at least one row before generating drafts.',
          jobId: null,
          progress: null,
        })
      }
      return
    }

    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    // Create new AbortController for this request
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    // Removed confirm dialog - it's blocked by no-alert-script anyway
    // Proceed directly with draft generation

    // Single state update: transition to loading
    if (mountedRef.current) {
      setDraftState({ 
        status: 'loading', 
        message: null,
        jobId: null,
        progress: null
      })
      setError(null)
      // Ref will be synced by useEffect
    }
    
    let timeoutId: NodeJS.Timeout | null = null
    
    try {
      // Draft only the selected prospects
      const result = await pipelineDraft({ prospect_ids: Array.from(selected) })
      
      // Check if request was aborted
      if (abortController.signal.aborted || !mountedRef.current) {
        return
      }
      
      // Store job_id and start polling for progress
      if (mountedRef.current && !abortController.signal.aborted) {
        setDraftState({ 
          status: 'loading', 
          message: 'Drafting job queued. Starting...',
          jobId: result.job_id,
          progress: {
            drafts_created: 0,
            total_targets: null,
            status: 'pending'
          }
        })
        
        // Start polling for progress
        startPollingProgress(result.job_id)
      }
    } catch (err: any) {
      // Check if request was aborted or component unmounted
      if (abortController.signal.aborted || !mountedRef.current) {
        return
      }
      
      // Extract error message - distinguish 422 (validation) from other errors
      let errorMessage = err?.message || 'Failed to generate drafts'
      
      // For 422 responses, the backend message is already in err.message
      // Ensure it's displayed prominently in the UI
      if (err?.status === 422) {
        // 422 is a validation error - show the backend's explanation
        errorMessage = err.message || 'No prospects ready for drafting. Ensure prospects have verification_status=\'verified\' and contact_email IS NOT NULL.'
      } else if (err?.message?.includes('Failed to fetch') || err?.message?.includes('network')) {
        // Network errors should be retryable
        errorMessage = 'Network error: Failed to connect to server. Please check your connection and try again.'
      }
      
      // Single state update: transition to error (consolidated)
      if (mountedRef.current && !abortController.signal.aborted) {
        setDraftState({ 
          status: 'error', 
          message: errorMessage,
          jobId: null,
          progress: null
        })
        // Also set in main error state so it shows in the error banner
        setError(errorMessage)
      }
      
      // Removed alert - it's blocked by no-alert-script anyway
    } finally {
      // Cleanup
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null
      }
    }
  }, [loadDrafts]) // Removed draftState from dependencies to prevent recreation loop

  // Use a ref to store the latest loadDrafts function to avoid dependency issues
  const loadDraftsRef = useRef(loadDrafts)
  useEffect(() => {
    loadDraftsRef.current = loadDrafts
  }, [loadDrafts])

  // Polling for draft job progress
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  const startPollingProgress = useCallback((jobId: string) => {
    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
    }
    
    const pollProgress = async () => {
      if (!mountedRef.current) {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
        return
      }
      
      try {
        const status = await getDraftJobStatus(jobId)
        
        if (!mountedRef.current) return
        
        // Update progress state
        setDraftState(prev => ({
          ...prev,
          progress: {
            drafts_created: status.drafts_created,
            total_targets: status.total_targets,
            status: status.status
          },
          message: status.status === 'running' 
            ? `Drafting in progress... ${status.drafts_created}${status.total_targets ? ` / ${status.total_targets}` : ''} drafts created`
            : status.status === 'pending'
            ? 'Drafting job queued. Starting...'
            : prev.message
        }))
        
        // Refresh drafts list periodically while job is running to show new drafts as they're created
        if (status.status === 'running' && status.drafts_created > 0) {
          // Refresh drafts list every time we see progress (drafts_created increased)
          // This ensures new drafts appear in the list as they're generated
          loadDraftsRef.current()
        }
        
        // Handle completion
        if (status.status === 'completed') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }
          
          setDraftState(prev => ({
            ...prev,
            status: 'success',
            message: `Drafting completed! ${status.drafts_created} drafts created.`
          }))
          
          // Refresh drafts list
          setTimeout(() => {
            if (mountedRef.current) {
              loadDrafts()
              if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent('jobsCompleted'))
              }
            }
          }, 1000)
        }
        
        // Handle failure
        if (status.status === 'failed') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }
          
          setDraftState(prev => ({
            ...prev,
            status: 'error',
            message: status.error_message || 'Drafting job failed'
          }))
          setError(status.error_message || 'Drafting job failed')
        }
      } catch (err: any) {
        // Don't stop polling on network errors - retry next interval
        console.error('Failed to poll draft job status:', err)
      }
    }
    
    // Poll immediately, then every 3 seconds
    pollProgress()
    pollingIntervalRef.current = setInterval(pollProgress, 3000)
  }, [loadDrafts])
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    // Only run if component is mounted
    if (!mountedRef.current) return
    
    // Reset initial load flag when skip changes (new page)
    isInitialLoadRef.current = true
    
    // Use setTimeout to defer state updates to avoid React invariant errors
    // This ensures state updates happen after render is complete
    const timeoutId = setTimeout(() => {
      if (mountedRef.current) {
        loadDraftsRef.current()
      }
    }, 0)
    
    const interval = setInterval(() => {
      if (mountedRef.current) {
        loadDraftsRef.current()
      }
    }, 15000)
    
    const handleJobCompleted = () => {
      // Defer to avoid state updates during render
      setTimeout(() => {
        if (mountedRef.current) {
          loadDraftsRef.current()
        }
      }, 0)
    }
    
    const handleRefreshDrafts = () => {
      // Defer to avoid state updates during render
      setTimeout(() => {
        if (mountedRef.current) {
          loadDraftsRef.current()
        }
      }, 0)
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('jobsCompleted', handleJobCompleted)
      window.addEventListener('refreshDrafts', handleRefreshDrafts)
    }
    
    return () => {
      clearTimeout(timeoutId)
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('jobsCompleted', handleJobCompleted)
        window.removeEventListener('refreshDrafts', handleRefreshDrafts)
      }
    }
  }, [skip]) // Only depend on skip, use ref for loadDrafts

  // DISABLED: Auto-draft on mount to prevent React invariant errors
  // Auto-drafting is now opt-in only via the "Generate Drafts" button
  // This prevents render loops and state update conflicts during initial render
  // useEffect(() => {
  //   // Auto-draft logic removed - user must explicitly click "Generate Drafts"
  // }, [])

  const handleSend = async () => {
    if (selected.size === 0) {
      setError('Please select at least one draft')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      const prospectIds = Array.from(selected)
      const ccMap: Record<string, string> = {}
      if (typeof window !== 'undefined') {
        prospectIds.forEach((id) => {
          const cc = window.localStorage.getItem(getCcStorageKey(id))
          if (cc && cc.trim()) {
            ccMap[id] = cc.trim()
          }
        })
      }

      await pipelineSend({ prospect_ids: prospectIds, cc_map: ccMap })
      setSelected(new Set())
      await loadDrafts()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
      }
      // Removed alert - it's blocked by no-alert-script anyway
      // Success is indicated by the table refresh and job completion event
    } catch (err: any) {
      setError(err.message || 'Failed to send emails')
      // Removed alert - error is shown in the error banner above the table
    } finally {
      setActionLoading(false)
    }
  }

  const handleEdit = (prospect: Prospect) => {
    setEditingProspect(prospect.id)
    setEditSubject(prospect.draft_subject || '')
    setEditBody(prospect.draft_body || '')

    if (typeof window !== 'undefined') {
      const stored = window.localStorage.getItem(getCcStorageKey(prospect.id))
      setEditCc(stored || '')
    }
  }

  const handleSaveEdit = async (prospectId: string) => {
    try {
      setIsSavingEdit(true)
      await updateProspectDraft(prospectId, {
        subject: editSubject,
        body: editBody
      })
      setEditingProspect(null)
      await loadDrafts()
    } catch (err: any) {
      setError(err.message || 'Failed to update draft')
    } finally {
      setIsSavingEdit(false)
    }
  }

  const handleCancelEdit = () => {
    setEditingProspect(null)
    setEditSubject('')
    setEditBody('')
    setEditCc('')
  }

  const handleExport = async () => {
    try {
      // Export all prospects with drafts (regardless of source type - includes leads and scraped emails)
      const csv = await exportProspectsCSV('drafted')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `drafts-${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(err.message || 'Failed to export drafts')
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'N/A'
    }
  }

  // Extract location from domain or email TLD
  function extractLocationFromDomain(domain?: string, email?: string): string {
    // First, try discovery_location if available (most accurate)
    // This is handled in the component where we have access to prospect.discovery_location
    
    // Extract from domain TLD
    const domainToCheck = domain || (email ? email.split('@')[1] : '')
    if (!domainToCheck) return 'N/A'
    
    // Common TLD to country mappings
    const tldToCountry: Record<string, string> = {
      'uk': 'United Kingdom',
      'co.uk': 'United Kingdom',
      'au': 'Australia',
      'com.au': 'Australia',
      'ca': 'Canada',
      'de': 'Germany',
      'fr': 'France',
      'it': 'Italy',
      'es': 'Spain',
      'nl': 'Netherlands',
      'be': 'Belgium',
      'ch': 'Switzerland',
      'at': 'Austria',
      'se': 'Sweden',
      'no': 'Norway',
      'dk': 'Denmark',
      'fi': 'Finland',
      'ie': 'Ireland',
      'nz': 'New Zealand',
      'sg': 'Singapore',
      'jp': 'Japan',
      'cn': 'China',
      'in': 'India',
      'br': 'Brazil',
      'mx': 'Mexico',
      'za': 'South Africa',
    }
    
    // Extract TLD (last part after last dot)
    const parts = domainToCheck.toLowerCase().split('.')
    if (parts.length >= 2) {
      const tld = parts.slice(-2).join('.') // Check for two-part TLDs like .co.uk
      if (tldToCountry[tld]) {
        return tldToCountry[tld]
      }
      const singleTld = parts[parts.length - 1]
      if (tldToCountry[singleTld]) {
        return tldToCountry[singleTld]
      }
    }
    
    return 'N/A'
  }

  if (loading && allDrafts.length === 0) {
    return (
      <div className="glass rounded-xl shadow-lg border border-white/20 p-6">
        <div className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-olive-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading drafts...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-gray-900">Email Drafts</h2>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              // Reset state and trigger new request
              setDraftState({ 
                status: 'idle', 
                message: null,
                jobId: null,
                progress: null
              })
              handleAutoDraft(true)
            }}
            disabled={draftState.status === 'loading'}
            className="px-3 py-1.5 text-xs font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          >
            {draftState.status === 'loading' ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Generating...</span>
              </>
            ) : draftState.status === 'error' ? (
              <>
                <X className="w-3 h-3" />
                <span>Retry</span>
              </>
            ) : (
              <>
                <FileText className="w-3 h-3" />
                <span>Generate Drafts</span>
              </>
            )}
          </button>
          {filteredDrafts.length > 0 && selected.size < filteredDrafts.length && (
            <button
              onClick={() => {
                // Select all prospects
                setSelected(new Set(filteredDrafts.map(p => p.id)))
              }}
              className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1"
              title="Select all drafts for bulk sending"
            >
              <CheckCircle className="w-3 h-3" />
              <span>Select All ({filteredDrafts.length})</span>
            </button>
          )}
          {selected.size > 0 && (
            <>
              <button
                onClick={() => setShowGlobalAdd(true)}
                disabled={isApplyingGlobalAdd}
                className="px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                title={categoryFilter ? `Global add to selected drafts in ${categoryFilter}` : 'Global add to selected drafts'}
              >
                {isApplyingGlobalAdd ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Applying...</span>
                  </>
                ) : (
                  <>
                    <Edit className="w-3 h-3" />
                    <span>Global Add</span>
                  </>
                )}
              </button>
              <button
                onClick={handleSend}
                disabled={actionLoading}
                className={`px-3 py-1.5 text-xs font-medium text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 ${
                  selected.size === filteredDrafts.length && filteredDrafts.length > 0
                    ? 'bg-green-700 hover:bg-green-800'
                    : 'bg-green-600'
                }`}
              >
                {actionLoading ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>{selected.size === filteredDrafts.length ? 'Sending All...' : 'Sending...'}</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3 h-3" />
                    <span>
                      {selected.size === filteredDrafts.length
                        ? `Send All (${filteredDrafts.length})`
                        : `Send (${selected.size})`}
                    </span>
                  </>
                )}
              </button>
              <button
                onClick={handleExport}
                className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1"
              >
                <Download className="w-3 h-3" />
                <span>Export</span>
              </button>
            </>
          )}
          <button
            onClick={loadDrafts}
            className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-white/50 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">
          {error}
        </div>
      )}
      
      {/* Removed draft state success/error messages - user requested removal of "draft signal at the top" */}

      {/* Show error state if there's an error and no prospects (don't show empty state when error exists) */}
      {error && filteredDrafts.length === 0 && !loading ? (
        <div className="text-center py-8">
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm font-medium text-red-800 mb-2">Error loading drafts</p>
            <p className="text-xs text-red-700">{error}</p>
            {error.includes('Failed to fetch') || error.includes('network') || error.includes('SSL') ? (
              <button
                onClick={() => {
                  setError(null)
                  loadDrafts()
                }}
                className="mt-3 px-4 py-2 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Retry
              </button>
            ) : null}
          </div>
        </div>
      ) : filteredDrafts.length === 0 && !loading && !error ? (
        <div className="text-center py-8 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-400" />
          <p className="text-sm font-medium mb-1">No drafts found</p>
          <p className="text-xs">Click "Generate Drafts" to create drafts for all verified leads and scraped emails</p>
        </div>
      ) : (
        <>
          {showGlobalAdd && typeof document !== 'undefined'
            ? createPortal(
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
                  <div className="w-full max-w-2xl rounded-xl bg-white shadow-xl border border-gray-200 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                      <div>
                        <div className="text-sm font-semibold text-gray-900">Global Add</div>
                        <div className="text-xs text-gray-600">
                          Apply to {selected.size} selected draft{selected.size === 1 ? '' : 's'}{categoryFilter ? ` (filtered: ${categoryFilter})` : ''}
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          if (isApplyingGlobalAdd) return
                          setShowGlobalAdd(false)
                        }}
                        className="p-1 rounded hover:bg-gray-100"
                        aria-label="Close"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="px-4 py-4 space-y-3">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null
                            setGlobalImageFile(file)
                            if (!file) {
                              setGlobalImageDataUrl('')
                              return
                            }
                            const reader = new FileReader()
                            reader.onload = () => {
                              const result = typeof reader.result === 'string' ? reader.result : ''
                              setGlobalImageDataUrl(result)
                            }
                            reader.onerror = () => setGlobalImageDataUrl('')
                            reader.readAsDataURL(file)
                          }}
                          className="md:col-span-2 px-2.5 py-2 text-xs border border-gray-200 rounded-lg bg-white"
                        />
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setGlobalImageSize('sm')}
                            className={`px-2 py-1.5 text-[11px] font-medium rounded-lg border ${
                              globalImageSize === 'sm'
                                ? 'bg-purple-600 text-white border-purple-600'
                                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                            }`}
                          >
                            S
                          </button>
                          <button
                            type="button"
                            onClick={() => setGlobalImageSize('md')}
                            className={`px-2 py-1.5 text-[11px] font-medium rounded-lg border ${
                              globalImageSize === 'md'
                                ? 'bg-purple-600 text-white border-purple-600'
                                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                            }`}
                          >
                            M
                          </button>
                          <button
                            type="button"
                            onClick={() => setGlobalImageSize('lg')}
                            className={`px-2 py-1.5 text-[11px] font-medium rounded-lg border ${
                              globalImageSize === 'lg'
                                ? 'bg-purple-600 text-white border-purple-600'
                                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                            }`}
                          >
                            L
                          </button>
                          <button
                            type="button"
                            onClick={() => setGlobalImageSize('full')}
                            className={`px-2 py-1.5 text-[11px] font-medium rounded-lg border ${
                              globalImageSize === 'full'
                                ? 'bg-purple-600 text-white border-purple-600'
                                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                            }`}
                          >
                            Full
                          </button>
                        </div>
                      </div>

                      {globalImageDataUrl ? (
                        <div className="border border-gray-200 rounded-lg p-2 bg-white">
                          <div className="text-[11px] text-gray-600 mb-2">Preview (size: {globalImageSize})</div>
                          <img
                            src={globalImageDataUrl}
                            alt=""
                            style={{
                              width:
                                globalImageSize === 'sm'
                                  ? 200
                                  : globalImageSize === 'md'
                                    ? 360
                                    : globalImageSize === 'lg'
                                      ? 520
                                      : '100%',
                              maxWidth: '100%',
                              height: 'auto',
                              display: 'block',
                            }}
                          />
                        </div>
                      ) : null}

                      <input
                        type="file"
                        onChange={(e) => setGlobalDocFile(e.target.files?.[0] || null)}
                        className="w-full px-2.5 py-2 text-xs border border-gray-200 rounded-lg bg-white"
                      />

                      <input
                        value={globalCc}
                        onChange={(e) => setGlobalCc(e.target.value)}
                        placeholder="CC (applied to all selected)"
                        className="w-full px-2.5 py-2 text-xs border border-gray-200 rounded-lg"
                      />

                      <div className="text-[11px] text-gray-600">
                        Attachments will be uploaded and sent with each selected prospect. A short note is appended to the bottom of each draft body.
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-gray-100 bg-gray-50">
                      <button
                        onClick={() => setShowGlobalAdd(false)}
                        disabled={isApplyingGlobalAdd}
                        className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={applyGlobalAdd}
                        disabled={isApplyingGlobalAdd}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1"
                      >
                        {isApplyingGlobalAdd ? (
                          <>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            <span>Applying...</span>
                          </>
                        ) : (
                          <span>Apply</span>
                        )}
                      </button>
                    </div>
                  </div>
                </div>,
                document.body
              )
            : null}
          <div className="mb-3 flex items-center gap-2">
            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value)
                setSkip(0)
              }}
              className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg bg-white"
              title="Filter by category (does not update categories)"
            >
              <option value="">All Categories (Filter)</option>
              {availableCategories.map((c) => (
                <option key={c} value={c}>
                  {c} (Filter)
                </option>
              ))}
            </select>
            <input
              value={locationQuery}
              onChange={(e) => {
                setLocationQuery(e.target.value)
                setSkip(0)
              }}
              placeholder="Search location (or domain/email)"
              className="flex-1 min-w-[220px] px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg"
            />
            <div className="text-xs text-gray-600 whitespace-nowrap">
              Showing {filteredDrafts.length} of {total} drafts
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left p-2">
                    <input
                      type="checkbox"
                      checked={selected.size === filteredDrafts.length && filteredDrafts.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelected(new Set(filteredDrafts.map(p => p.id)))
                        } else {
                          setSelected(new Set())
                        }
                      }}
                      className="rounded border-gray-300 text-olive-600 focus:ring-olive-500"
                    />
                  </th>
                  <th className="text-left p-2 font-semibold text-gray-700">Domain</th>
                  <th className="text-left p-2 font-semibold text-gray-700">Email</th>
                  <th className="text-left p-2 font-semibold text-gray-700">Subject</th>
                  <th className="text-left p-2 font-semibold text-gray-700">Category</th>
                  <th className="text-left p-2 font-semibold text-gray-700">Location</th>
                  <th className="text-left p-2 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDrafts.map((prospect) => (
                  <tr key={prospect.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={selected.has(prospect.id)}
                        onChange={(e) => {
                          const newSelected = new Set(selected)
                          if (e.target.checked) {
                            newSelected.add(prospect.id)
                          } else {
                            newSelected.delete(prospect.id)
                          }
                          setSelected(newSelected)
                        }}
                        className="rounded border-gray-300 text-olive-600 focus:ring-olive-500"
                      />
                    </td>
                    <td className="p-2">
                      <a
                        href={prospect.page_url || `https://${prospect.domain}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-olive-600 hover:text-olive-700 hover:underline flex items-center gap-1"
                      >
                        {prospect.domain || 'N/A'}
                        <Mail className="w-3 h-3" />
                      </a>
                    </td>
                    <td className="p-2 text-gray-700">{prospect.contact_email || 'N/A'}</td>
                    <td className="p-2">
                      <span className="text-gray-700">{prospect.draft_subject || 'N/A'}</span>
                    </td>
                    <td className="p-2">
                      <span className="text-gray-700 font-medium">{prospect.discovery_category || 'N/A'}</span>
                    </td>
                    <td className="p-2">
                      <span className="text-gray-700 font-medium">
                        {prospect.discovery_location || extractLocationFromDomain(prospect.domain, prospect.contact_email) || 'N/A'}
                      </span>
                    </td>
                    <td className="p-2">
                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => handleEdit(prospect)}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                          title="Edit"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filteredDrafts.length > 0 && (
            <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
              <div>
                {skip > 0 && (
                  <button
                    onClick={() => setSkip(Math.max(0, skip - limit))}
                    className="px-2 py-1 text-olive-600 hover:text-olive-700 hover:underline"
                  >
                    Previous
                  </button>
                )}
              </div>
              <div>
                Page {Math.floor(skip / limit) + 1} of {Math.ceil(total / limit)}
              </div>
              <div>
                {skip + limit < total && (
                  <button
                    onClick={() => setSkip(skip + limit)}
                    className="px-2 py-1 text-olive-600 hover:text-olive-700 hover:underline"
                  >
                    Next
                  </button>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {editingProspect && typeof document !== 'undefined'
        ? createPortal(
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
              <div className="glass rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col border border-white/20">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200/50 bg-gradient-to-r from-liquid-50/50 to-purple-50/30">
                  <div>
                    <h3 className="text-base font-bold liquid-gradient-text">Edit Draft</h3>
                    <p className="text-xs text-gray-600 mt-0.5 font-medium">Update subject and body</p>
                  </div>
                  <button
                    onClick={handleCancelEdit}
                    className="p-1.5 rounded-lg hover:bg-white/80 text-gray-500 transition-all duration-200 hover:scale-110"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Subject</label>
                    <input
                      type="text"
                      value={editSubject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                      placeholder="Email subject..."
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Cc</label>
                    <input
                      type="text"
                      value={editCc}
                      onChange={(e) => {
                        const next = e.target.value
                        setEditCc(next)
                        if (typeof window !== 'undefined' && editingProspect) {
                          window.localStorage.setItem(getCcStorageKey(editingProspect), next)
                        }
                      }}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                      placeholder="Add Cc recipients (comma separated)"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Message Body</label>
                    <RichEmailEditor value={editBody} onChange={(html) => setEditBody(html)} placeholder="Email body" />
                  </div>
                </div>

                <div className="border-t p-2.5 flex items-center justify-end gap-2">
                  <button
                    onClick={handleCancelEdit}
                    className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleSaveEdit(editingProspect)}
                    disabled={isSavingEdit}
                    className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {isSavingEdit ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-3 h-3" />
                        Save
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}

