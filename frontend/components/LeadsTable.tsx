'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2, Users, Globe, CheckCircle, Eye, Edit2 } from 'lucide-react'
import { listLeads, listScrapedEmails, promoteToLead, composeEmail, sendEmail, manualScrape, manualVerify, updateProspectCategory, autoCategorizeAll, type Prospect } from '@/lib/api'
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
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedProspects, setSelectedProspects] = useState<Set<string>>(new Set())
  const [showCategoryUpdate, setShowCategoryUpdate] = useState(false)
  const [updateCategory, setUpdateCategory] = useState<string>('')
  const [isUpdatingCategory, setIsUpdatingCategory] = useState(false)
  const [isAutoCategorizing, setIsAutoCategorizing] = useState(false)

  // Available categories
  const availableCategories = [
    'Art Gallery', 'Museums', 'Art Studio', 'Art School', 'Art Fair', 
    'Art Dealer', 'Art Consultant', 'Art Publisher', 'Art Magazine'
  ]

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
      
      let leads = Array.isArray(response?.data) ? response.data : []
      
      // Filter by category if selected
      if (selectedCategory !== 'all') {
        leads = leads.filter((p: Prospect) => 
          p.discovery_category === selectedCategory || p.discovery_category?.toLowerCase() === selectedCategory.toLowerCase()
        )
      }
      
      // Sort by category in ascending order
      leads.sort((a: Prospect, b: Prospect) => {
        const catA = a.discovery_category || ''
        const catB = b.discovery_category || ''
        return catA.localeCompare(catB)
      })
      
      if (leads.length > 0 || response?.total > 0) {
        console.log(`✅ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Setting prospects:`, leads.length, 'total:', response?.total)
      } else {
        console.warn(`⚠️ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Empty response - data:`, response?.data, 'total:', response?.total)
      }
      
      setProspects(leads)
      setTotal(selectedCategory === 'all' ? (response.total ?? leads.length) : leads.length)
      // Clear error if we successfully got data (even if empty)
      // Empty data is not an error, it's a valid state
    } catch (error: any) {
      console.error(`❌ [${emailsOnly ? 'SCRAPED EMAILS' : 'LEADS'}] Failed to load:`, error)
      let errorMessage = error?.message || `Failed to load ${emailsOnly ? 'scraped emails' : 'leads'}.`
      
      // Provide more specific error messages
      if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
        errorMessage = 'Unable to connect to backend. Please check if the server is running.'
      } else if (errorMessage.includes('401') || errorMessage.includes('Unauthorized')) {
        errorMessage = 'Authentication required. Please log in again.'
      } else if (errorMessage.includes('404')) {
        errorMessage = 'API endpoint not found. Please check backend configuration.'
      } else if (errorMessage.includes('500')) {
        errorMessage = 'Backend server error. Please try again later.'
      }
      
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
  }, [skip, emailsOnly, selectedCategory])

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
        category: updateCategory.trim()
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

  const handleAutoCategorize = async () => {
    setIsAutoCategorizing(true)
    setError(null)
    try {
      const result = await autoCategorizeAll()
      setTimeout(() => {
        loadProspects().catch(err => console.error('Error reloading prospects:', err))
      }, 500)
      setError(`✅ ${result.message}`)
      setTimeout(() => setError(null), 5000)
    } catch (err: any) {
      setError(err.message || 'Failed to auto-categorize')
    } finally {
      setIsAutoCategorizing(false)
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
        <div className="flex items-center space-x-2">
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-olive-500 focus:border-olive-500 bg-white"
          >
            <option value="all">All Categories</option>
            {availableCategories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
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
            onClick={handleAutoCategorize}
            disabled={isAutoCategorizing}
            className="px-2 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          >
            {isAutoCategorizing ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Auto-Categorizing...
              </>
            ) : (
              <>
                <Users className="w-3 h-3" />
                Auto-Categorize All
              </>
            )}
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
                      checked={selectedProspects.size === prospects.length && prospects.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedProspects(new Set(prospects.map(p => p.id)))
                        } else {
                          setSelectedProspects(new Set())
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
                        checked={selectedProspects.has(prospect.id)}
                        onChange={(e) => {
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
                      <span className="text-gray-700 font-medium">{prospect.discovery_category || 'N/A'}</span>
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

      {/* Compose / Review Modal */}
      {activeProspect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass rounded-3xl shadow-2xl w-full max-w-4xl max-height-[85vh] max-h-[85vh] overflow-hidden flex flex-col border border-white/20 animate-scale-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200/50 bg-gradient-to-r from-liquid-50/50 to-purple-50/30">
              <div>
                <h3 className="text-xl font-bold liquid-gradient-text">
                  Review Draft Email
                </h3>
                <p className="text-xs text-gray-600 mt-1 font-medium">
                  {activeProspect.domain} — {activeProspect.contact_email}
                </p>
              </div>
              <button
                onClick={closeComposeModal}
                className="p-2 rounded-xl hover:bg-white/80 text-gray-500 transition-all duration-200 hover:scale-110"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-200/50 bg-gradient-to-r from-gray-50/50 to-white/50">
              <button
                onClick={() => setActiveTab('edit')}
                className={`flex items-center space-x-2 px-6 py-3 text-sm font-semibold transition-all duration-200 ${
                  activeTab === 'edit'
                    ? 'liquid-gradient-text border-b-2 border-liquid-500 bg-white/80'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
                }`}
              >
                <Edit2 className="w-4 h-4" />
                <span>Edit</span>
              </button>
              <button
                onClick={() => setActiveTab('preview')}
                className={`flex items-center space-x-2 px-6 py-3 text-sm font-semibold transition-all duration-200 ${
                  activeTab === 'preview'
                    ? 'liquid-gradient-text border-b-2 border-liquid-500 bg-white/80'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
                }`}
              >
                <Eye className="w-4 h-4" />
                <span>Preview</span>
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'edit' ? (
                <div className="p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Subject
                    </label>
                    <input
                      type="text"
                      value={draftSubject}
                      onChange={(e) => setDraftSubject(e.target.value)}
                      className="w-full px-4 py-3 glass border border-gray-200/50 rounded-xl focus:outline-none focus:ring-2 focus:ring-liquid-500 focus:border-liquid-500 text-sm transition-all duration-200"
                      placeholder="Email subject"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Message
                    </label>
                    <textarea
                      value={draftBody}
                      onChange={(e) => setDraftBody(e.target.value)}
                      className="w-full px-4 py-3 glass border border-gray-200/50 rounded-xl focus:outline-none focus:ring-2 focus:ring-liquid-500 focus:border-liquid-500 text-sm h-64 resize-vertical transition-all duration-200"
                      placeholder="Your email message will appear here. You can edit it before sending."
                    />
                  </div>
                </div>
              ) : (
                <div className="p-4">
                  {/* Email Preview - styled like Gmail */}
                  <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                    {/* Email Header */}
                    <div className="bg-gray-50 border-b border-gray-200 px-4 py-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="text-sm font-semibold text-gray-900 mb-1">
                            {draftSubject || '(No subject)'}
                          </div>
                          <div className="text-xs text-gray-600 space-y-1">
                            <div className="flex items-center space-x-2">
                              <span className="font-medium">From:</span>
                              <span>Your Email (via Gmail)</span>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="font-medium">To:</span>
                              <span>{activeProspect.contact_email}</span>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="font-medium">Date:</span>
                              <span>{new Date().toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Email Body */}
                    <div className="px-4 py-6">
                      <div className="prose prose-sm max-w-none">
                        <div 
                          className="text-gray-900 whitespace-pre-wrap leading-relaxed"
                          style={{ 
                            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                            lineHeight: '1.6'
                          }}
                        >
                          {draftBody || (
                            <span className="text-gray-400 italic">No message content yet. Switch to Edit tab to compose.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Preview Info */}
                  <div className="mt-4 p-4 bg-gradient-to-r from-liquid-50 to-purple-50 border-2 border-liquid-200 rounded-xl shadow-sm">
                    <p className="text-xs text-gray-700 font-medium">
                      <strong className="liquid-gradient-text">Preview:</strong> This is how your email will appear to the recipient. 
                      The actual email will be sent via Gmail API.
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200/50 bg-gradient-to-r from-gray-50/50 to-white/50">
              <p className="text-xs text-gray-600 font-medium">
                {activeProspect.draft_subject && activeProspect.draft_body
                  ? '✨ Review and send your drafted email, or send via Pipeline.'
                  : '📝 This is a DRAFT ONLY. To send emails, use the Pipeline → Send card.'}
              </p>
              <div className="flex items-center space-x-3">
                <button
                  onClick={closeComposeModal}
                  className="px-4 py-2 text-sm font-medium text-gray-700 glass hover:bg-white/80 rounded-xl transition-all duration-200 hover:shadow-md"
                >
                  Close
                </button>
                {activeProspect.draft_subject && activeProspect.draft_body && (
                  <button
                    onClick={handleSendNow}
                    disabled={isSending}
                    className="flex items-center space-x-2 px-5 py-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg"
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
                  className="flex items-center space-x-2 px-5 py-2 liquid-gradient text-white rounded-xl hover:shadow-xl hover:scale-105 transition-all duration-200 font-semibold shadow-lg"
                >
                  <Send className="w-4 h-4" />
                  <span>Go to Pipeline</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

