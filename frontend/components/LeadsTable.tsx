'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2, Users, Globe, CheckCircle } from 'lucide-react'
import { listLeads, listScrapedEmails, promoteToLead, composeEmail, sendEmail, manualScrape, manualVerify, type Prospect } from '@/lib/api'
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

  // Manual actions state
  const [showManualActions, setShowManualActions] = useState(false)
  const [manualWebsiteUrl, setManualWebsiteUrl] = useState('')
  const [manualEmail, setManualEmail] = useState('')
  const [isManualScraping, setIsManualScraping] = useState(false)
  const [isManualVerifying, setIsManualVerifying] = useState(false)
  const [manualSuccess, setManualSuccess] = useState<string | null>(null)

  const [error, setError] = useState<string | null>(null)

  const loadProspects = async () => {
    try {
      setLoading(true)
      setError(null)
      // Use different endpoints based on emailsOnly prop
      // Leads tab: prospects with scrape_status IN (SCRAPED, ENRICHED) - matches pipeline "Scraped" count
      // Scraped Emails tab: same as leads (for now, both show scraped emails)
      const response = emailsOnly 
        ? await listScrapedEmails(skip, limit)
        : await listLeads(skip, limit)
      
      console.log(`📊 [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] API Response:`, { 
        dataLength: response?.data?.length, 
        total: response?.total,
        hasData: !!response?.data,
        isArray: Array.isArray(response?.data)
      })
      
      const leads = Array.isArray(response?.data) ? response.data : []
      if (leads.length > 0 || response?.total > 0) {
        console.log(`✅ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Setting prospects:`, leads.length, 'total:', response?.total)
      } else {
        console.warn(`⚠️ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Empty response - data:`, response?.data, 'total:', response?.total)
      }
      
      setProspects(leads)
      setTotal(response.total ?? leads.length)
      // Clear error if we successfully got data (even if empty)
      // Empty data is not an error, it's a valid state
    } catch (error: any) {
      console.error(`❌ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Failed to load:`, error)
      const errorMessage = error?.message || `Failed to load ${emailsOnly ? 'scraped emails' : 'leads'}. Check if backend is running.`
      setError(errorMessage)
      setProspects([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
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
  }, [skip, emailsOnly])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const openComposeModal = async (prospect: Prospect) => {
    if (!prospect.contact_email) {
      alert('This lead does not have an email address yet. Please enrich first.')
      return
    }

    setIsComposing(true)
    try {
      const result = await composeEmail(prospect.id)

      // Use returned draft, falling back to existing values
      const draftSub = result.subject || prospect.draft_subject || ''
      const draftBdy = result.body || prospect.draft_body || ''

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
  }

  const handleSendNow = async () => {
    if (!activeProspect) return
    
    // Validate draft exists
    if (!activeProspect.draft_subject || !activeProspect.draft_body) {
      alert('No draft email found. Please compose email first.')
      return
    }
    
    setIsSending(true)
    try {
      await sendEmail(activeProspect.id)
      
      // Success - close modal, refresh data, show confirmation
      closeComposeModal()
      
      // Refresh prospects list
      await loadProspects()
      
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshPipelineStatus'))
      }
      
      alert('Email sent successfully!')
    } catch (error: any) {
      console.error('Failed to send email:', error)
      // Error messages are already specific from API (400, 409, 500)
      alert(error.message || 'Failed to send email')
    } finally {
      setIsSending(false)
    }
  }
  // Use pipelineSend() from the Pipeline page instead.

  const handleManualScrape = async () => {
    if (!manualWebsiteUrl.trim()) {
      setError('Please enter a website URL')
      return
    }

    try {
      setIsManualScraping(true)
      setError(null)
      setManualSuccess(null)
      const result = await manualScrape({ website_url: manualWebsiteUrl.trim() })
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
        }
      }, 1000)
    } catch (err: any) {
      setError(err.message || 'Failed to scrape website')
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
        }
      }, 1000)
    } catch (err: any) {
      setError(err.message || 'Failed to verify email')
    } finally {
      setIsManualVerifying(false)
    }
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">
          {emailsOnly ? 'Scraped Emails' : 'Leads'}
        </h2>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowManualActions(!showManualActions)}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md"
          >
            <Globe className="w-4 h-4" />
            <span>Manual Actions</span>
          </button>
        <button
          onClick={loadProspects}
          className="flex items-center space-x-2 px-3 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
        >
          <RefreshCw className="w-4 h-4" />
          <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>
      </div>

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
                  className="px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
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
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Domain</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Email</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Score</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Created</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((prospect) => (
                  <tr key={prospect.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{prospect.domain}</span>
                        {prospect.page_url && (
                          <a
                            href={prospect.page_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-olive-600 hover:text-olive-700"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {prospect.contact_email ? (
                        <div className="flex items-center space-x-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-900">{prospect.contact_email}</span>
                        </div>
                      ) : (
                        <span className="text-gray-400">No email</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          prospect.outreach_status === 'sent'
                            ? 'bg-green-100 text-green-800'
                            : prospect.outreach_status === 'replied'
                            ? 'bg-blue-100 text-blue-800'
                            : prospect.outreach_status === 'pending'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {prospect.outreach_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{safeToFixed(prospect.score, 2)}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatDate(prospect.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {prospect.contact_email && (
                          <button
                            onClick={() => openComposeModal(prospect)}
                            disabled={isComposing}
                            className="text-olive-600 hover:text-olive-700 text-sm underline"
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
                className="px-3 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
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

      {/* Compose / Review Modal */}
      {activeProspect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-height-[80vh] max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Review Draft Email
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {activeProspect.domain} — {activeProspect.contact_email}
                </p>
              </div>
              <button
                onClick={closeComposeModal}
                className="p-1 rounded-full hover:bg-gray-200 text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  value={draftSubject}
                  onChange={(e) => setDraftSubject(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500 text-sm"
                  placeholder="Email subject"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Message
                </label>
                <textarea
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500 text-sm h-48 resize-vertical"
                  placeholder="Your email message will appear here. You can edit it before sending."
                />
              </div>
            </div>

            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
              <p className="text-xs text-gray-500">
                {activeProspect.draft_subject && activeProspect.draft_body
                  ? 'Review and send your drafted email, or send via Pipeline.'
                  : 'This is a DRAFT ONLY. To send emails, use the Pipeline → Send card.'}
              </p>
              <div className="flex items-center space-x-2">
                <button
                  onClick={closeComposeModal}
                  className="px-3 py-2 text-sm text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300"
                >
                  Close
                </button>
                {activeProspect.draft_subject && activeProspect.draft_body && (
                  <button
                    onClick={handleSendNow}
                    disabled={isSending}
                    className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send className="w-4 h-4" />
                    <span>{isSending ? 'Sending...' : 'Send Now'}</span>
                  </button>
                )}
                <button
                  onClick={() => {
                    // Navigate to Pipeline tab to use Send card
                    const event = new CustomEvent('change-tab', { detail: 'pipeline' })
                    window.dispatchEvent(event)
                    closeComposeModal()
                  }}
                  className="flex items-center space-x-2 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
                >
                  <Send className="w-4 h-4" />
                  <span>Go to Pipeline to Send</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

