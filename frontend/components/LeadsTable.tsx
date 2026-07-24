'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2, Users, Globe, CheckCircle, Eye, Edit2, Download, FileText } from 'lucide-react'
import { listLeads, listScrapedEmails, promoteToLead, composeEmail, sendEmail, updateProspectDraft, manualScrape, manualVerify, updateProspectCategory, exportLeadsCSV, exportScrapedEmailsCSV, pipelineDraft, getDraftJobStatus, generateCategoryTemplate, pipelineDraftCategory, type Prospect } from '@/lib/api'
import GeminiChatPanel from '@/components/GeminiChatPanel'
import RichEmailEditor from '@/components/RichEmailEditor'
import FloatingComposeWindow from '@/components/FloatingComposeWindow'
import { safeToFixed } from '@/lib/safe-utils'

interface LeadsTableProps {
  emailsOnly?: boolean
}

export default function LeadsTable({ emailsOnly = false }: LeadsTableProps) {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  const [activeProspect, setActiveProspect] = useState<Prospect | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')
  const [composeMinimized, setComposeMinimized] = useState(false)
  const [composeMaximized, setComposeMaximized] = useState(false)
  const [composeCc, setComposeCc] = useState('')

  const getCcStorageKey = (prospectId: string) => `prospect_cc_${prospectId}`

  // Manual actions state
  const [showManualActions, setShowManualActions] = useState(false)
  const [manualWebsiteUrl, setManualWebsiteUrl] = useState('')
  const [manualEmail, setManualEmail] = useState('')
  const [isManualScraping, setIsManualScraping] = useState(false)
  const [isManualVerifying, setIsManualVerifying] = useState(false)
  const [manualSuccess, setManualSuccess] = useState<string | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedProspects, setSelectedProspects] = useState<Set<string>>(new Set())
  const [allFilteredSelected, setAllFilteredSelected] = useState(false)
  const [showCategoryUpdate, setShowCategoryUpdate] = useState(false)
  const [updateCategory, setUpdateCategory] = useState<string>('')
  const [isUpdatingCategory, setIsUpdatingCategory] = useState(false)
  const [isAutoDrafting, setIsAutoDrafting] = useState(false)
  const [showCategoryDraftModal, setShowCategoryDraftModal] = useState(false)
  const [categoryDraftNotes, setCategoryDraftNotes] = useState('')
  const [isGeneratingCategoryTemplate, setIsGeneratingCategoryTemplate] = useState(false)
  const [categoryConcept, setCategoryConcept] = useState('')
  const [categorySubjectTemplate, setCategorySubjectTemplate] = useState('')
  const [categoryBodyTemplate, setCategoryBodyTemplate] = useState('')
  const [availableCategories, setAvailableCategories] = useState<string[]>([
    'Art Lovers', 'Interior Design', 'Pet Lovers', 'Dogs and Cat Owners - Fur Parent', 'Childhood Development', 
    'Holidays', 'Famous Quotes', 'Home Decor', 
    'Audio Visual', 'Interior Decor', 'Holiday Decor', 'Home Tech', 
    'Parenting (Mom Site)', 'NFTs', 'Museum'
  ])

  const normalizeCategoryForBackend = (category: string) => {
    if (category === 'Parenting (Mom Site)') return 'Parenting'
    return category
  }

  const mapCategoryForDisplay = (category?: string | null) => {
    if (!category) return category
    if (category === 'Parenting') return 'Parenting (Mom Site)'
    return category
  }

  const loadProspects = async () => {
    try {
      setLoading(true)
      setError(null)
      // Use different endpoints based on emailsOnly prop
      // Leads tab: prospects with scrape_status IN (SCRAPED, ENRICHED) - matches pipeline "Scraped" count
      // Scraped Emails tab: same as leads (for now, both show scraped emails)
      const normalizedSelectedCategory =
        selectedCategory !== 'all' ? normalizeCategoryForBackend(selectedCategory) : undefined
      const response = emailsOnly 
        ? await listScrapedEmails(skip, limit, normalizedSelectedCategory)
        : await listLeads(skip, limit, normalizedSelectedCategory)
      
      console.log(`📊 [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] API Response:`, { 
        dataLength: response?.data?.length, 
        total: response?.total,
        hasData: !!response?.data,
        isArray: Array.isArray(response?.data)
      })
      
      let leads = Array.isArray(response?.data)
        ? response.data.map((p: any) => ({
            ...p,
            discovery_category: mapCategoryForDisplay(p.discovery_category),
          }))
        : []
      
      // Backend now handles category filtering, so no need to filter on frontend
      // But we can still log for debugging
      if (selectedCategory !== 'all') {
        console.log(`🔍 [FILTER] Backend filtered for category: "${normalizedSelectedCategory}"`)
        console.log(`🔍 [FILTER] Results returned: ${leads.length} items (total: ${response.total})`)
      }
      
      // Sort by category in ascending order
      leads.sort((a: Prospect, b: Prospect) => {
        const catA = a.discovery_category || ''
        const catB = b.discovery_category || ''
        return catA.localeCompare(catB)
      })
      
      // CRITICAL: Log raw response before any filtering
      console.log(`📊 [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] RAW API RESPONSE:`, {
        dataLength: response?.data?.length,
        total: response?.total,
        hasData: !!response?.data,
        isArray: Array.isArray(response?.data),
        firstItem: response?.data?.[0]
      })
      
      // Log all unique categories in the current page for debugging
      const categoriesInPage = Array.from(new Set(leads.map((p: Prospect) => p.discovery_category).filter((cat): cat is string => !!cat)))
      console.log(`📊 [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Categories in current page:`, categoriesInPage)
      
      // CRITICAL: If backend says there's data but we got empty array, this is an error
      if (response?.total > 0 && (!response?.data || response.data.length === 0)) {
        const errorMsg = `Backend reports ${response.total} ${emailsOnly ? 'scraped emails' : 'leads'} but returned empty data array. This indicates a data visibility issue.`
        console.error(`❌ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] ${errorMsg}`)
        setError(errorMsg)
        setProspects([])
        setTotal(response.total)
        return
      }
      
      if (leads.length > 0 || response?.total > 0) {
        console.log(`✅ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Setting prospects:`, leads.length, 'total:', response?.total)
      } else {
        console.warn(`⚠️ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Empty response - data:`, response?.data, 'total:', response?.total)
      }
      
      setProspects(leads)
      setTotal(response.total ?? leads.length)
      
      // Clear error on successful load (even if empty data)
      setError(null)
      // Empty data is not an error, it's a valid state
    } catch (error: any) {
      // CRITICAL: Do not suppress errors - log them clearly
      console.error(`❌ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Failed to load:`, error)
      console.error(`❌ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Error details:`, {
        message: error?.message,
        stack: error?.stack,
        response: error?.response,
        status: error?.status
      })
      
      let errorMessage = error?.message || `Failed to load ${emailsOnly ? 'scraped emails' : 'leads'}.`
      
      // Provide more specific error messages
      if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
        errorMessage = 'Unable to connect to backend. Please check if the server is running.'
      } else if (errorMessage.includes('401') || errorMessage.includes('Unauthorized')) {
        errorMessage = 'Authentication required. Please log in again.'
      } else if (errorMessage.includes('404')) {
        errorMessage = 'API endpoint not found. Please check backend configuration.'
      } else if (errorMessage.includes('500') || errorMessage.includes('Database query failed')) {
        errorMessage = `Backend server error: ${errorMessage}. Check backend logs for details.`
      }
      
      // In development, show full error
      if (process.env.NODE_ENV === 'development') {
        errorMessage = `${errorMessage} (Full error: ${error?.message || 'Unknown error'})`
      }
      
      setError(errorMessage)
      setProspects([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // loadCategories() // Load categories first, then load prospects - TODO: implement if needed
    let abortController = new AbortController()
    let debounceTimeout: NodeJS.Timeout | null = null
    
    const loadProspectsDebounced = () => {
      // Cancel previous request if still in flight
      abortController.abort()
      abortController = new AbortController()
      
      // Clear existing debounce timeout
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      
      // Debounce: wait 500ms before making request
      debounceTimeout = setTimeout(() => {
    loadProspects()
      }, 500)
    }
    
    // Initial load
    loadProspectsDebounced()
    
    // Debounced refresh every 30 seconds
    const interval = setInterval(() => {
      loadProspectsDebounced()
    }, 30000)
    
    const handleJobCompleted = () => {
      console.log('🔄 Job completed event received, refreshing leads table...')
      loadProspectsDebounced()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('jobsCompleted', handleJobCompleted)
    }
    
    return () => {
      abortController.abort()
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('jobsCompleted', handleJobCompleted)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, emailsOnly, selectedCategory])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const normalizeDraft = (input: { subject?: string | null; body?: string | null }): { subject: string; body: string } => {
    const rawSubject = (input.subject || '').trim()
    const rawBody = (input.body || '').trim()

    const maybeJson = rawBody || rawSubject
    if (!maybeJson || !maybeJson.startsWith('{')) {
      return { subject: rawSubject, body: rawBody }
    }

    try {
      const parsed = JSON.parse(maybeJson)
      if (parsed && typeof parsed === 'object') {
        const subject = typeof parsed.subject === 'string' ? parsed.subject.trim() : rawSubject
        const body = typeof parsed.body === 'string' ? parsed.body.trim() : rawBody
        return { subject, body }
      }
    } catch {
      // ignore
    }

    return { subject: rawSubject, body: rawBody }
  }

  const openComposeModal = async (prospect: Prospect) => {
    if (!prospect.contact_email) {
      alert('This lead does not have an email address yet. Please enrich first.')
      return
    }

    if (typeof window !== 'undefined') {
      const stored = window.localStorage.getItem(getCcStorageKey(prospect.id))
      setComposeCc(stored || '')
    }

    setIsComposing(true)
    try {
      const result = await composeEmail(prospect.id)

      // Use returned draft, falling back to existing values
      const normalized = normalizeDraft({
        subject: result.subject || prospect.draft_subject || '',
        body: result.body || prospect.draft_body || '',
      })
      const draftSub = normalized.subject
      const draftBdy = normalized.body

      setActiveProspect({ ...prospect, draft_subject: draftSub, draft_body: draftBdy })
      setDraftSubject(draftSub)
      setDraftBody(draftBdy)
      
      // Trigger pipeline status refresh so Drafting card updates
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
      }
    } catch (error: any) {
      console.error('Failed to compose email:', error)
      alert(error.message || 'Failed to compose email')
    } finally {
      setIsComposing(false)
    }
  }

  const closeComposeModal = () => {
    setActiveProspect(null)
    setDraftSubject('')
    setDraftBody('')
    setComposeCc('')
    setComposeMinimized(false)
    setComposeMaximized(false)
  }

  const handleSaveDraft = async () => {
    if (!activeProspect) return

    try {
      setError(null)
      // Update draft directly (manual editing)
      await updateProspectDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody
      })
      await loadProspects()
      // Update active prospect state
      setActiveProspect({
        ...activeProspect,
        draft_subject: draftSubject,
        draft_body: draftBody
      })
      // Trigger pipeline status refresh
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
        // Trigger drafts refresh so the draft appears immediately
        window.dispatchEvent(new CustomEvent('refreshDrafts'))
      }
      // Show success message and navigate to drafts tab
      setError('✅ Draft saved successfully! Navigating to Drafts tab...')
      setTimeout(() => {
        setError(null)
        // Navigate to drafts tab
        if (typeof window !== 'undefined') {
          const event = new CustomEvent('change-tab', { detail: 'drafts' })
          window.dispatchEvent(event)
        }
      }, 1000)
    } catch (err: any) {
      console.error('Failed to save draft:', err)
      setError(err.message || 'Failed to save draft')
    }
  }

  const handleDraftAdopted = (subject: string, body: string) => {
    const normalized = normalizeDraft({ subject, body })
    setDraftSubject(normalized.subject)
    setDraftBody(normalized.body)
    if (activeProspect) {
      // Update the active prospect's draft fields
      setActiveProspect({
        ...activeProspect,
        draft_subject: normalized.subject,
        draft_body: normalized.body
      })
    }
  }

  const handleAutoDraftSelectedLeads = async () => {
    try {
      if (selectedProspects.size === 0) {
        setError('Please select at least one lead to draft')
        return
      }
      setIsAutoDrafting(true)
      setError(null)
      
      // Draft only the selected leads
      const result = await pipelineDraft({ prospect_ids: Array.from(selectedProspects) })
      
      if (!result.job_id) {
        throw new Error('No job ID returned from drafting request')
      }
      
      // Show success message
      setError('✅ Auto-drafting started! Checking progress...')
      
      const pollInterval = setInterval(async () => {
        try {
          const status = await getDraftJobStatus(result.job_id)

          if (status.status === 'failed') {
            clearInterval(pollInterval)
            setIsAutoDrafting(false)
            setError(`❌ Drafting failed: ${status.error_message || 'Unknown error'}`)
            return
          }

          if (status.status === 'completed') {
            clearInterval(pollInterval)
            setIsAutoDrafting(false)
            setError(`✅ Drafting completed! ${status.drafts_created} drafts created. Navigating to Drafts tab...`)

            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
              window.dispatchEvent(new CustomEvent('jobsCompleted'))
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }

            setTimeout(() => {
              setError(null)
              if (typeof window !== 'undefined') {
                const event = new CustomEvent('change-tab', { detail: 'drafts' })
                window.dispatchEvent(event)
              }
            }, 2000)
            return
          }

          if (status.status === 'running') {
            const progressMsg = status.total_targets
              ? `⏳ Drafting in progress... ${status.drafts_created} / ${status.total_targets} drafts created`
              : `⏳ Drafting in progress... ${status.drafts_created} drafts created so far`
            setError(progressMsg)
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }
          } else if (status.status === 'pending') {
            setError('⏳ Drafting job queued. Starting soon...')
          }
        } catch (pollErr: any) {
          console.error('Error polling draft job status:', pollErr)
          if (pollErr.message?.includes('500') || pollErr.message?.includes('Failed to get job status')) {
            setError('⏳ Drafting in progress... (checking status)')
          }
        }
      }, 3000)
      
      // Store interval ID so we can clear it on component unmount
      const cleanup = () => {
        if (pollInterval) {
          clearInterval(pollInterval)
        }
      }
      
      // Cleanup on unmount
      if (typeof window !== 'undefined') {
        window.addEventListener('beforeunload', cleanup)
      }
      
      // Trigger pipeline status refresh immediately
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
        window.dispatchEvent(new CustomEvent('refreshDrafts'))
      }
    } catch (err: any) {
      console.error('Failed to auto-draft leads:', err)
      setError(err.message || 'Failed to start auto-drafting')
      setIsAutoDrafting(false)
    }
  }

  const openCategoryDraftModal = () => {
    setCategoryDraftNotes('')
    setCategoryConcept('')
    setCategorySubjectTemplate('')
    setCategoryBodyTemplate('')
    setShowCategoryDraftModal(true)
  }

  const handleGenerateCategoryTemplate = async () => {
    if (selectedCategory === 'all') {
      setError('Please filter a category first')
      return
    }

    try {
      setIsGeneratingCategoryTemplate(true)
      setError(null)
      const normalizedSelectedCategory = normalizeCategoryForBackend(selectedCategory)
      const result = await generateCategoryTemplate({
        category: normalizedSelectedCategory,
        notes: categoryDraftNotes.trim() ? categoryDraftNotes.trim() : undefined,
      })
      setCategoryConcept(result.concept)
      setCategorySubjectTemplate(result.subject_template)
      setCategoryBodyTemplate(result.body_template)
    } catch (err: any) {
      setError(err.message || 'Failed to generate template')
    } finally {
      setIsGeneratingCategoryTemplate(false)
    }
  }

  const handlePropagateCategoryDraft = async () => {
    if (selectedCategory === 'all') {
      setError('Please filter a category first')
      return
    }

    if (!categoryConcept.trim() || !categorySubjectTemplate.trim() || !categoryBodyTemplate.trim()) {
      setError('Please generate a template first')
      return
    }

    try {
      setIsAutoDrafting(true)
      setError(null)
      const normalizedSelectedCategory = normalizeCategoryForBackend(selectedCategory)

      const request = allFilteredSelected
        ? {
            filters: { category: normalizedSelectedCategory },
            category: normalizedSelectedCategory,
            concept: categoryConcept,
            subject_template: categorySubjectTemplate,
            body_template: categoryBodyTemplate,
          }
        : {
            prospect_ids: Array.from(selectedProspects),
            category: normalizedSelectedCategory,
            concept: categoryConcept,
            subject_template: categorySubjectTemplate,
            body_template: categoryBodyTemplate,
          }

      if (!allFilteredSelected && selectedProspects.size === 0) {
        setError('Please select at least one lead to propagate to, or enable all-filtered selection')
        setIsAutoDrafting(false)
        return
      }

      const result = await pipelineDraftCategory(request as any)

      if (!result.job_id) {
        throw new Error('No job ID returned from drafting request')
      }

      setShowCategoryDraftModal(false)
      setError('✅ Category drafting started! Checking progress...')

      const pollInterval = setInterval(async () => {
        try {
          const status = await getDraftJobStatus(result.job_id)

          if (status.status === 'failed') {
            clearInterval(pollInterval)
            setIsAutoDrafting(false)
            setError(`❌ Drafting failed: ${status.error_message || 'Unknown error'}`)
            return
          }

          if (status.status === 'completed') {
            clearInterval(pollInterval)
            setIsAutoDrafting(false)
            setError(`✅ Drafting completed! ${status.drafts_created} drafts created. Navigating to Drafts tab...`)

            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
              window.dispatchEvent(new CustomEvent('jobsCompleted'))
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }

            setTimeout(() => {
              setError(null)
              if (typeof window !== 'undefined') {
                const event = new CustomEvent('change-tab', { detail: 'drafts' })
                window.dispatchEvent(event)
              }
            }, 2000)
            return
          }

          if (status.status === 'running') {
            const progressMsg = status.total_targets
              ? `⏳ Drafting in progress... ${status.drafts_created} / ${status.total_targets} drafts created`
              : `⏳ Drafting in progress... ${status.drafts_created} drafts created so far`
            setError(progressMsg)
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('refreshDrafts'))
            }
          } else if (status.status === 'pending') {
            setError('⏳ Drafting job queued. Starting soon...')
          }
        } catch (pollErr: any) {
          console.error('Error polling draft job status:', pollErr)
          if (pollErr.message?.includes('500') || pollErr.message?.includes('Failed to get job status')) {
            setError('⏳ Drafting in progress... (checking status)')
          }
        }
      }, 3000)

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
        window.dispatchEvent(new CustomEvent('refreshDrafts'))
      }
    } catch (err: any) {
      console.error('Failed to propagate category draft:', err)
      setError(err.message || 'Failed to start category drafting')
      setIsAutoDrafting(false)
    }
  }

  const handleSendNow = async () => {
    if (!activeProspect) return

    // Prevent sending when email isn't verified (backend will reject with 400)
    if ((activeProspect.verification_status || '').toLowerCase() !== 'verified') {
      setError(
        `Cannot send yet: email is not verified (status: ${activeProspect.verification_status || 'pending'}). Verify email first.`
      )
      return
    }
    
    // Validate current editor state (do not rely on activeProspect draft fields which may be stale)
    if (!draftSubject.trim() || !draftBody.trim()) {
      alert('Please provide both a subject and a message body before sending.')
      return
    }
    
    setIsSending(true)
    try {
      // Persist latest edits before sending (send endpoint uses DB draft only)
      await updateProspectDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody,
      })

      await sendEmail(activeProspect.id, {
        cc: composeCc,
      })
      
      // Success - close modal, refresh data, show confirmation
      closeComposeModal()
      
      // Refresh prospects list
      await loadProspects()
      
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
      }
      
      // Success - show inline success message instead of alert
      setError(null)
      // Show success message briefly
      const successMsg = 'Email sent successfully!'
      setError(successMsg)
      setTimeout(() => setError(null), 3000)
    } catch (error: any) {
      console.error('Failed to send email:', error)
      // Parse error message - API returns detailed errors
      const errorMsg = error?.message || 'Failed to send email'
      
      // Check for specific error types
      if (errorMsg.includes('Gmail') || errorMsg.includes('access token') || errorMsg.includes('refresh token')) {
        setError(`Gmail Configuration Error: ${errorMsg}. Check /api/health/gmail for details.`)
      } else if (errorMsg.toLowerCase().includes('not verified') || errorMsg.toLowerCase().includes('verify email first')) {
        setError(`Cannot send yet: ${errorMsg}`)
      } else if (errorMsg.includes('not ready') || errorMsg.includes('draft')) {
        setError(`Draft Error: ${errorMsg}`)
      } else if (errorMsg.includes('already sent')) {
        setError(`Already Sent: ${errorMsg}`)
      } else {
        setError(`Send Failed: ${errorMsg}`)
      }
    } finally {
      setIsSending(false)
    }
  }

  const handleManualScrape = async () => {
    if (!manualWebsiteUrl.trim()) {
      setError('Please enter a website URL')
      return
    }

    try {
      setIsManualScraping(true)
      setError(null)
      setManualSuccess(null)
      const raw = manualWebsiteUrl.trim()
      const website_url = raw.includes('://') ? raw : `https://${raw}`
      const result = await manualScrape({ website_url })
      setManualSuccess(result.is_followup 
        ? `✅ Website already exists - marked as follow-up candidate. ${result.message}`
        : `✅ Website scraped successfully! ${result.message}`)
      setManualWebsiteUrl('')
      // Reload prospects and refresh pipeline status after scraping
      setTimeout(() => {
        loadProspects()
        // Trigger pipeline status refresh
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
          window.dispatchEvent(new CustomEvent('jobsCompleted'))
        }
      }, 1000)
    } catch (err: any) {
      setError(err?.message || 'Failed to scrape website')
    } finally {
      setIsManualScraping(false)
    }
  }

  const handleManualVerify = async () => {
    if (!manualEmail.trim()) {
      setError('Please enter an email address')
      return
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(manualEmail.trim())) {
      setError('Please enter a valid email address')
      return
    }

    try {
      setIsManualVerifying(true)
      setError(null)
      setManualSuccess(null)
      const result = await manualVerify({ email: manualEmail.trim() })
      setManualSuccess(result.is_followup
        ? `✅ Email already exists - verified. Status: ${result.verification_status}`
        : `✅ Email verified! Status: ${result.verification_status}`)
      setManualEmail('')
      // Reload prospects and refresh pipeline status after verification
      setTimeout(() => {
        loadProspects()
        // Trigger pipeline status refresh
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
          window.dispatchEvent(new CustomEvent('jobsCompleted'))
        }
      }, 1000)
    } catch (err: any) {
      setError(err?.message || 'Failed to verify email')
    } finally {
      setIsManualVerifying(false)
    }
  }

  const handleUpdateCategory = async () => {
    if (selectedProspects.size === 0) {
      setError('Please select at least one prospect to update')
      return
    }
    
    if (!updateCategory || !updateCategory.trim()) {
      setError('Please select a category')
      return
    }

    try {
      setIsUpdatingCategory(true)
      setError(null)
      const result = await updateProspectCategory({
        prospect_ids: Array.from(selectedProspects),
        category: normalizeCategoryForBackend(updateCategory.trim())
      })
      setError(`✅ ${result.message}`)
      setSelectedProspects(new Set())
      setShowCategoryUpdate(false)
      setUpdateCategory('')
      setTimeout(() => {
        loadProspects().catch(err => console.error('Error reloading prospects:', err))
      }, 500)
    } catch (err: any) {
      setError(err.message || 'Failed to update category')
    } finally {
      setIsUpdatingCategory(false)
    }
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-olive-700">
            {emailsOnly ? 'Scraped Emails' : 'Leads'}
          </h2>
          <p className="text-xs text-gray-500 mt-1">Liquid Canvas Outreach</p>
        </div>
        <div className="flex items-center space-x-2 flex-wrap gap-2 overflow-visible">
          {!emailsOnly && (
            <button
              onClick={handleAutoDraftSelectedLeads}
              disabled={isAutoDrafting || loading}
              className="px-3 py-1.5 text-xs font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-sm"
              title="Auto-draft emails for the selected leads and navigate to Drafts tab"
            >
              {isAutoDrafting ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Drafting...</span>
                </>
              ) : (
                <>
                  <FileText className="w-3 h-3" />
                  <span>Auto-Draft Selected ({selectedProspects.size})</span>
                </>
              )}
            </button>
          )}
          {!emailsOnly && selectedCategory !== 'all' && (
            <button
              onClick={openCategoryDraftModal}
              disabled={loading || isAutoDrafting}
              className="px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-sm"
              title="Generate a category template with Gemini and propagate it to the selected leads"
            >
              <FileText className="w-3 h-3" />
              <span>Generate for category</span>
            </button>
          )}
          <select
            value={selectedCategory}
            onChange={(e) => {
              // Only filter - never update categories
              setSelectedCategory(e.target.value)
              setSelectedProspects(new Set())
              setAllFilteredSelected(false)
            }}
            className="px-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-olive-500 focus:border-olive-500 bg-white"
            title="Filter by category (does not update categories)"
          >
            <option value="all">All Categories (Filter)</option>
            {availableCategories.map((cat) => (
              <option key={cat} value={cat}>{cat} (Filter)</option>
            ))}
          </select>
          {selectedProspects.size > 0 && (
            <button
              onClick={() => setShowCategoryUpdate(true)}
              className="px-2 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Update Category ({selectedProspects.size})
            </button>
          )}
          {prospects.filter(p => !p.discovery_category || p.discovery_category === 'N/A').length > 0 && (
            <button
              onClick={() => {
                // Select all uncategorized prospects
                const uncategorized = prospects
                  .filter(p => !p.discovery_category || p.discovery_category === 'N/A')
                  .map(p => p.id)
                setSelectedProspects(new Set(uncategorized))
                setShowCategoryUpdate(true)
              }}
              className="px-2 py-1.5 text-xs bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              Categorize All ({prospects.filter(p => !p.discovery_category || p.discovery_category === 'N/A').length})
            </button>
          )}
          <button
            onClick={async () => {
              try {
                const blob = emailsOnly ? await exportScrapedEmailsCSV() : await exportLeadsCSV()
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${emailsOnly ? 'scraped_emails' : 'leads'}_${new Date().toISOString().split('T')[0]}.csv`
                document.body.appendChild(a)
                a.click()
                window.URL.revokeObjectURL(url)
                document.body.removeChild(a)
              } catch (error: any) {
                alert(`Failed to export CSV: ${error.message}`)
              }
            }}
            className="flex items-center space-x-1 px-2 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-medium transition-all duration-200"
          >
            <Download className="w-3 h-3" />
            <span>Download CSV</span>
          </button>
          <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowManualActions(!showManualActions)}
            className="flex items-center space-x-1 px-2 py-1 glass hover:bg-white/80 text-gray-700 rounded-lg transition-all duration-200 text-xs font-medium hover:shadow-md"
          >
            <Globe className="w-4 h-4" />
            <span>Manual Actions</span>
          </button>
        <button
          onClick={loadProspects}
          className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg transition-all duration-200 text-xs font-medium shadow-md hover:bg-olive-700"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
        </button>
          </div>
        </div>
      </div>

      {/* Error/Success Message Display */}
      {error && (
        <div className={`mb-4 p-4 rounded-xl shadow-md border-2 animate-slide-up ${
          error.includes('successfully') || error.includes('✅')
            ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300 text-green-800'
            : 'bg-gradient-to-r from-red-50 to-pink-50 border-red-300 text-red-800'
        }`}>
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Manual Actions Panel */}
      {showManualActions && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Manual Input</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Manual Scrape */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Globe className="w-4 h-4 inline mr-1" />
                Scrape Website
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={manualWebsiteUrl}
                  onChange={(e) => setManualWebsiteUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-olive-500 focus:border-olive-500"
                  disabled={isManualScraping}
                />
                <button
                  onClick={handleManualScrape}
                  disabled={isManualScraping || !manualWebsiteUrl.trim()}
                  className="px-2 py-1 bg-olive-600 text-white rounded-lg hover:bg-olive-700 hover:shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1 text-xs font-medium shadow-sm"
                >
                  {isManualScraping ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Scraping...</span>
                    </>
                  ) : (
                    <>
                      <Globe className="w-4 h-4" />
                      <span>Scrape</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Manual Verify */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <CheckCircle className="w-4 h-4 inline mr-1" />
                Verify Email
              </label>
              <div className="flex space-x-2">
                <input
                  type="email"
                  value={manualEmail}
                  onChange={(e) => setManualEmail(e.target.value)}
                  placeholder="email@example.com"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-olive-500 focus:border-olive-500"
                  disabled={isManualVerifying}
                />
                <button
                  onClick={handleManualVerify}
                  disabled={isManualVerifying || !manualEmail.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  {isManualVerifying ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Verifying...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      <span>Verify</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          {manualSuccess && (
            <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
              {manualSuccess}
            </div>
          )}
        </div>
      )}

      {loading && prospects.length === 0 ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2">Loading {emailsOnly ? 'emails' : 'leads'}...</p>
        </div>
      ) : error ? (
        <div className="text-center py-8">
          <p className="text-red-600 mb-2 font-semibold">Error loading {emailsOnly ? 'emails' : 'leads'}</p>
          <p className="text-gray-600 text-sm">{error}</p>
          <button
            onClick={loadProspects}
            className="mt-4 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
          >
            Retry
          </button>
        </div>
      ) : prospects.length === 0 && !loading ? (
        <div className="text-center py-12">
          <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 font-medium mb-2">
            No {emailsOnly ? 'prospects with emails' : 'prospects'} yet
          </p>
          <p className="text-gray-500 text-sm mb-4">
            {emailsOnly 
              ? 'No prospects with emails yet. Scrape discovered websites to extract contact information.'
              : 'No prospects yet. Scrape discovered websites to create prospects.'}
          </p>
          <p className="text-gray-400 text-xs">
            {emailsOnly 
              ? 'Prospects appear here after scraping finds emails. Go to the Websites tab to approve and scrape websites.'
              : 'Prospects are created after scraping. Go to the Websites tab to approve websites, then use the Pipeline tab to scrape them.'}
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-gray-200/50 shadow-lg">
            <table className="w-full">
              <thead>
                <tr className="bg-gradient-to-r from-liquid-50 to-purple-50 border-b border-gray-200/50">
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">
                    <input
                      type="checkbox"
                      checked={allFilteredSelected || (selectedProspects.size === prospects.length && prospects.length > 0)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          if (selectedCategory !== 'all') {
                            setAllFilteredSelected(true)
                            setSelectedProspects(new Set())
                          } else {
                            setSelectedProspects(new Set(prospects.map(p => p.id)))
                          }
                        } else {
                          setSelectedProspects(new Set())
                          setAllFilteredSelected(false)
                        }
                      }}
                      className="w-3 h-3 text-olive-600"
                    />
                  </th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Category</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Domain</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Email</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Status</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Score</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Created</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {prospects.map((prospect) => (
                  <tr key={prospect.id} className="hover:bg-gradient-to-r hover:from-liquid-50/30 hover:to-purple-50/30 transition-all duration-200">
                    <td className="py-2 px-3 text-xs">
                      <input
                        type="checkbox"
                        checked={allFilteredSelected || selectedProspects.has(prospect.id)}
                        onChange={(e) => {
                          if (allFilteredSelected) {
                            return
                          }
                          const newSelected = new Set(selectedProspects)
                          if (e.target.checked) {
                            newSelected.add(prospect.id)
                          } else {
                            newSelected.delete(prospect.id)
                          }
                          setSelectedProspects(newSelected)
                        }}
                        className="w-3 h-3 text-olive-600"
                      />
                    </td>
                    <td className="py-2 px-3 text-xs">
                      <span className={`px-2 py-1 rounded-lg text-xs font-medium ${
                        prospect.discovery_category 
                          ? 'bg-olive-100 text-olive-800 border border-olive-300' 
                          : 'bg-gray-100 text-gray-500 border border-gray-300'
                      }`}>
                        {prospect.discovery_category || 'N/A'}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-gray-900">{prospect.domain}</span>
                        {prospect.page_url && (
                          <a
                            href={prospect.page_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-liquid-600 hover:text-liquid-700 transition-colors"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3 text-xs">
                      {prospect.contact_email ? (
                        <div className="flex items-center space-x-2">
                          <Mail className="w-4 h-4 text-liquid-500" />
                          <span className="text-gray-900 font-medium">{prospect.contact_email}</span>
                        </div>
                      ) : (
                        <span className="text-gray-400 italic">No email</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-xs">
                      <div className="flex flex-col space-y-0.5">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            prospect.verification_status === 'verified'
                              ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white'
                              : prospect.verification_status === 'unverified' || prospect.verification_status === 'UNVERIFIED'
                              ? 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white'
                              : prospect.verification_status === 'failed'
                              ? 'bg-gradient-to-r from-red-500 to-pink-600 text-white'
                              : 'bg-gray-200 text-gray-700'
                          }`}
                        >
                          {prospect.verification_status || 'PENDING'}
                        </span>
                        {/* Show outreach_status (secondary, for sent/replied) */}
                        {prospect.outreach_status && prospect.outreach_status !== 'pending' && (
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              prospect.outreach_status === 'sent'
                                ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white'
                                : prospect.outreach_status === 'replied'
                                ? 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white'
                                : 'bg-gray-200 text-gray-700'
                            }`}
                          >
                            {prospect.outreach_status}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3 text-xs">
                      <span className="text-gray-900 font-semibold">{safeToFixed(prospect.score, 2)}</span>
                    </td>
                    <td className="py-4 px-6 text-sm text-gray-600">
                      {formatDate(prospect.created_at)}
                    </td>
                    <td className="py-2 px-3 text-xs">
                      <div className="flex items-center space-x-2">
                        {prospect.contact_email && (
                          <button
                            onClick={() => openComposeModal(prospect)}
                            disabled={isComposing}
                            className="text-olive-700 hover:underline text-xs font-semibold transition-all duration-200"
                          >
                            {prospect.draft_subject ? 'View / Edit Email' : 'Compose Email'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-600">
              Showing {skip + 1}-{Math.min(skip + limit, total)} of {total}
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
                  className="px-2 py-1 text-xs glass hover:bg-white/80 text-gray-700 rounded-lg hover:shadow-md transition-all duration-200 disabled:opacity-50 font-medium"
              >
                Previous
              </button>
              <button
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= total}
                className="px-3 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      {/* Category Update Modal */}
      {showCategoryUpdate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass rounded-xl shadow-2xl w-full max-w-md p-4 border border-white/20 animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-900">Update Category</h3>
              <button
                onClick={() => {
                  setShowCategoryUpdate(false)
                  setUpdateCategory('')
                }}
                className="p-1 rounded-lg hover:bg-white/80 text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <p className="text-xs text-gray-600">
                Update category for {selectedProspects.size} selected prospect(s)
              </p>
              <div className="text-xs text-gray-500 mb-2">
                {selectedProspects.size > 0 && (
                  <div>
                    Current categories: {Array.from(new Set(
                      prospects
                        .filter(p => selectedProspects.has(p.id))
                        .map(p => p.discovery_category || 'N/A')
                    )).join(', ')}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <label className="block text-xs font-medium text-gray-700 mb-2">
                  Select Category to Assign:
                </label>
                <div className="grid grid-cols-2 gap-1.5 mb-2 max-h-32 overflow-y-auto p-2 bg-gray-50 rounded-lg">
                  {availableCategories.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setUpdateCategory(cat)}
                      className={`px-2 py-1.5 rounded text-xs font-medium transition-all ${
                        updateCategory === cat
                          ? 'bg-olive-600 text-white shadow-md'
                          : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
                <select
                  value={updateCategory}
                  onChange={(e) => setUpdateCategory(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-olive-500 focus:border-olive-500 bg-white"
                >
                  <option value="">-- Or choose from dropdown --</option>
                  {availableCategories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    setShowCategoryUpdate(false)
                    setUpdateCategory('')
                  }}
                  className="flex-1 px-3 py-2 text-xs font-medium text-gray-700 glass hover:bg-white/80 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpdateCategory}
                  disabled={isUpdatingCategory || !updateCategory}
                  className="flex-1 px-3 py-2 text-xs font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50"
                >
                  {isUpdatingCategory ? 'Updating...' : 'Update'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showCategoryDraftModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass rounded-xl shadow-2xl w-full max-w-2xl p-4 border border-white/20 animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-900">Generate category template</h3>
              <button
                onClick={() => setShowCategoryDraftModal(false)}
                className="p-1 rounded-lg hover:bg-white/80 text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="text-xs text-gray-600">
                Category: <span className="font-semibold">{selectedCategory}</span>
              </div>
              <textarea
                value={categoryDraftNotes}
                onChange={(e) => setCategoryDraftNotes(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-purple-500 focus:border-purple-500 bg-white"
                rows={3}
                placeholder="Optional notes for Gemini (tone, CTA, style, etc.)"
                disabled={isGeneratingCategoryTemplate || isAutoDrafting}
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerateCategoryTemplate}
                  disabled={isGeneratingCategoryTemplate || isAutoDrafting}
                  className="px-3 py-2 text-xs font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                >
                  {isGeneratingCategoryTemplate ? 'Generating...' : 'Generate template'}
                </button>
                <button
                  onClick={handlePropagateCategoryDraft}
                  disabled={isGeneratingCategoryTemplate || isAutoDrafting}
                  className="px-3 py-2 text-xs font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50"
                >
                  {isAutoDrafting ? 'Propagating...' : 'Propagate'}
                </button>
              </div>
              {(categoryConcept || categorySubjectTemplate || categoryBodyTemplate) && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-gray-700">Concept</div>
                  <div className="text-xs text-gray-700 whitespace-pre-wrap border border-gray-200 rounded-lg p-2 bg-white">
                    {categoryConcept}
                  </div>
                  <div className="text-xs font-semibold text-gray-700">Subject template</div>
                  <div className="text-xs text-gray-700 whitespace-pre-wrap border border-gray-200 rounded-lg p-2 bg-white">
                    {categorySubjectTemplate}
                  </div>
                  <div className="text-xs font-semibold text-gray-700">Body template</div>
                  <div className="text-xs text-gray-700 whitespace-pre-wrap border border-gray-200 rounded-lg p-2 bg-white max-h-48 overflow-y-auto">
                    {categoryBodyTemplate}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Compose / Review Window */}
      {activeProspect && (
        <FloatingComposeWindow
          title="New Message"
          subtitle={`${activeProspect.domain} — ${activeProspect.contact_email || ''}`}
          minimized={composeMinimized}
          maximized={composeMaximized}
          onMinimize={() => setComposeMinimized((v) => !v)}
          onMaximize={() => setComposeMaximized((v) => !v)}
          onClose={closeComposeModal}
          footer={
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={handleSaveDraft}
                className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Save to Draft
              </button>
              {draftSubject && draftBody && (
                <button
                  onClick={handleSendNow}
                  disabled={isSending || (activeProspect.verification_status || '').toLowerCase() !== 'verified'}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-olive-600 rounded-lg hover:bg-olive-700 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {isSending ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="w-3 h-3" />
                      Send
                    </>
                  )}
                </button>
              )}
            </div>
          }
        >
          <div className="h-full flex min-h-0">
            <div className={composeMaximized ? 'w-[380px] border-r flex flex-col min-h-0' : 'w-[260px] border-r flex flex-col min-h-0'}>
              <GeminiChatPanel
                prospectId={activeProspect.id}
                currentSubject={draftSubject}
                currentBody={draftBody}
                onDraftAdopted={handleDraftAdopted}
              />
            </div>

            <div className="flex-1 flex flex-col min-h-0">
              {(() => {
                const status = (activeProspect.verification_status || '').toLowerCase()
                if (!status || status === 'pending' || status === 'unverified' || status === 'failed') {
                  const label = activeProspect.verification_status || 'pending'
                  const isOk = status === 'verified'
                  if (isOk) return null
                  return (
                    <div className="px-3 py-2 text-xs border-b border-gray-200 bg-amber-50 text-amber-900">
                      Email must be verified before sending. Current status: <span className="font-semibold">{label}</span>.
                    </div>
                  )
                }
                return null
              })()}

              <div className="border-b px-3 py-2 text-xs">
                <div className="flex items-center gap-2">
                  <div className="text-gray-600 w-8">To</div>
                  <input value={activeProspect.contact_email || ''} readOnly className="flex-1 bg-transparent outline-none text-gray-900" />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <div className="text-gray-600 w-8">Cc</div>
                  <input
                    value={composeCc}
                    onChange={(e) => {
                      const next = e.target.value
                      setComposeCc(next)
                      if (typeof window !== 'undefined' && activeProspect?.id) {
                        window.localStorage.setItem(getCcStorageKey(activeProspect.id), next)
                      }
                    }}
                    className="flex-1 bg-transparent outline-none text-gray-900"
                    placeholder="Add Cc recipients (comma separated)"
                  />
                </div>
              </div>

              <div className="flex border-b">
                <button
                  onClick={() => setActiveTab('edit')}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    activeTab === 'edit'
                      ? 'border-b-2 border-olive-600 text-olive-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Edit
                </button>
                <button
                  onClick={() => setActiveTab('preview')}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    activeTab === 'preview'
                      ? 'border-b-2 border-olive-600 text-olive-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Preview
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-3">
                {activeTab === 'edit' ? (
                  <div className="space-y-3">
                    <div>
                      <input
                        type="text"
                        value={draftSubject}
                        onChange={(e) => {
                          const next = e.target.value
                          setDraftSubject(next)
                          setActiveProspect((prev) => (prev ? { ...prev, draft_subject: next } : prev))
                        }}
                        className="w-full px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                        placeholder="Subject"
                      />
                    </div>
                    <div>
                      <RichEmailEditor
                        value={draftBody}
                        onChange={(html) => {
                          setDraftBody(html)
                          setActiveProspect((prev) => (prev ? { ...prev, draft_body: html } : prev))
                        }}
                        placeholder="Write your message here..."
                        className={composeMaximized ? 'min-h-[420px]' : undefined}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-1">Subject:</h4>
                      <p className="text-xs text-gray-900">{draftSubject || '(No subject)'}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-1">Body:</h4>
                      {draftBody ? (
                        <div className="text-xs text-gray-900" dangerouslySetInnerHTML={{ __html: draftBody }} />
                      ) : (
                        <div className="text-xs text-gray-900">(No body)</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </FloatingComposeWindow>
      )}
    </div>
  )
}

