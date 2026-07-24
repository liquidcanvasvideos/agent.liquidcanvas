'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Mail, CheckCircle, XCircle, Clock, RefreshCw, X, Loader2, Download, Eye } from 'lucide-react'
import { listProspects, exportProspectsCSV, getAvailableCategories, getProspectSentEmail, type Prospect, type SentEmailDetails } from '@/lib/api'

export default function EmailsTable() {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedProspects, setSelectedProspects] = useState<Set<string>>(new Set())
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

  const [viewingProspectId, setViewingProspectId] = useState<string | null>(null)
  const [sentEmailDetails, setSentEmailDetails] = useState<SentEmailDetails | null>(null)
  const [isLoadingSentEmail, setIsLoadingSentEmail] = useState(false)

  useEffect(() => {
    if (typeof document === 'undefined') return
    if (!viewingProspectId) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [viewingProspectId])

  // Load available categories from API (dynamic, reflects migrated categories)
  const loadCategories = async () => {
    try {
      const response = await getAvailableCategories()
      if (response.categories && response.categories.length > 0) {
        const mapped = response.categories.map((c: string) =>
          c === 'Parenting' ? 'Parenting (Mom Site)' : c
        )
        setAvailableCategories(mapped)
        console.log(`📊 [CATEGORIES] Loaded ${response.categories.length} categories from API (${response.from_database} from DB)`)
      }
    } catch (err) {
      console.warn('⚠️ [CATEGORIES] Failed to load categories from API, using defaults:', err)
      // Keep default categories if API fails
    }
  }

  const handleViewSentEmail = async (prospectId: string) => {
    setViewingProspectId(prospectId)
    setIsLoadingSentEmail(true)
    setSentEmailDetails(null)
    setError(null)
    try {
      const details = await getProspectSentEmail(prospectId)
      setSentEmailDetails(details)
    } catch (err: any) {
      setError(err?.message || 'Failed to load sent email')
    } finally {
      setIsLoadingSentEmail(false)
    }
  }

  const loadSentEmails = async () => {
    try {
      setLoading(true)
      setError(null)
      const normalizedSelectedCategory =
        selectedCategory !== 'all' ? normalizeCategoryForBackend(selectedCategory) : undefined

      const response = await listProspects(skip, limit, 'sent', undefined, undefined, normalizedSelectedCategory)
      // Ensure data is always an array
      let prospectsData = Array.isArray(response?.data) ? response.data : []

      prospectsData = prospectsData.map((p: any) => ({
        ...p,
        discovery_category: mapCategoryForDisplay(p.discovery_category),
      }))
      
      // Sort by category in ascending order
      prospectsData.sort((a: Prospect, b: Prospect) => {
        const catA = a.discovery_category || ''
        const catB = b.discovery_category || ''
        return catA.localeCompare(catB)
      })
      
      setProspects(prospectsData)
      setTotal(response?.total ?? 0)
      // Clear error on successful load (even if empty data)
      setError(null)
      // Empty data is not an error, it's a valid state
    } catch (error: any) {
      console.error('Failed to load sent emails:', error)
      let errorMessage = error?.message || 'Failed to load sent emails.'
      
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
    loadCategories() // Load categories first
    loadSentEmails()
    const interval = setInterval(loadSentEmails, 15000)
    
    const handleJobCompleted = () => {
      console.log('🔄 Job completed event received, refreshing emails table...')
      loadSentEmails()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('jobsCompleted', handleJobCompleted)
    }
    
    return () => {
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('jobsCompleted', handleJobCompleted)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, selectedCategory])

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-gray-900">Sent Emails</h2>
        <div className="flex items-center space-x-2">
          <select
            value={selectedCategory}
            onChange={(e) => {
              // Only filter - never update categories
              setSelectedCategory(e.target.value)
            }}
            className="px-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-olive-500 focus:border-olive-500 bg-white"
            title="Filter by category (does not update categories)"
          >
            <option value="all">All Categories (Filter)</option>
            {availableCategories.map((cat) => (
              <option key={cat} value={cat}>{cat} (Filter)</option>
            ))}
          </select>
          <button
            onClick={async () => {
              try {
                const blob = await exportProspectsCSV(undefined, 'sent')
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `sent_emails_${new Date().toISOString().split('T')[0]}.csv`
                document.body.appendChild(a)
                a.click()
                window.URL.revokeObjectURL(url)
                document.body.removeChild(a)
              } catch (error: any) {
                alert(`Failed to export CSV: ${error.message}`)
              }
            }}
            className="flex items-center space-x-1 px-2 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-medium"
          >
            <Download className="w-3 h-3" />
            <span>Download CSV</span>
          </button>
          <button
            onClick={loadSentEmails}
            className="flex items-center space-x-1 px-2 py-1.5 bg-olive-600 text-white rounded-lg hover:bg-olive-700 text-xs font-medium"
          >
            <RefreshCw className="w-3 h-3" />
            <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {loading && prospects.length === 0 ? (
        <div className="text-center py-4">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2 text-xs">Loading sent emails...</p>
        </div>
      ) : error ? (
        <div className="text-center py-4">
          <p className="text-red-600 mb-2 font-semibold text-xs">Error loading sent emails</p>
          <p className="text-gray-600 text-xs">{error}</p>
          <button
            onClick={loadSentEmails}
            className="mt-3 px-2 py-1.5 bg-olive-600 text-white rounded-lg hover:bg-olive-700 text-xs font-medium"
          >
            Retry
          </button>
        </div>
      ) : prospects.length === 0 && !loading ? (
        <div className="text-center py-4">
          <p className="text-gray-500 mb-2 text-xs">No sent emails found</p>
          <p className="text-gray-400 text-xs">Send emails to prospects from the Leads tab to see them here.</p>
        </div>
      ) : (
        <>
          {viewingProspectId &&
            typeof document !== 'undefined' &&
            createPortal(
              <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 p-4">
                <div className="w-full max-w-4xl max-h-[90vh] rounded-xl bg-white shadow-xl border border-gray-200 overflow-hidden flex flex-col">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">Sent Email</div>
                      <div className="text-xs text-gray-600">
                        {sentEmailDetails?.provider ? `Provider: ${sentEmailDetails.provider}` : ''}
                        {sentEmailDetails?.sent_at ? ` • Sent: ${formatDate(sentEmailDetails.sent_at)}` : ''}
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setViewingProspectId(null)
                        setSentEmailDetails(null)
                      }}
                      className="p-1 rounded hover:bg-gray-100"
                      aria-label="Close"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="px-4 py-4 space-y-3 flex-1 min-h-0 overflow-y-auto">
                    {isLoadingSentEmail ? (
                      <div className="flex items-center gap-2 text-xs text-gray-700">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Loading message…</span>
                      </div>
                    ) : sentEmailDetails ? (
                      <>
                        <div className="text-xs">
                          <div className="font-semibold text-gray-900 mb-1">Subject</div>
                          <div className="text-gray-800">{sentEmailDetails.subject || '(no subject)'}</div>
                        </div>

                        {sentEmailDetails.attachments?.length ? (
                          <div className="text-xs">
                            <div className="font-semibold text-gray-900 mb-1">Attachments</div>
                            <div className="text-gray-800">
                              {sentEmailDetails.attachments.map((a) => a.filename).join(', ')}
                            </div>
                          </div>
                        ) : null}

                        <div className="text-xs">
                          <div className="font-semibold text-gray-900 mb-1">Message (rendered)</div>
                          <div className="border border-gray-200 rounded-lg p-3 bg-white">
                            <div dangerouslySetInnerHTML={{ __html: sentEmailDetails.body || '' }} />
                          </div>
                        </div>

                        <details className="text-xs">
                          <summary className="cursor-pointer text-gray-700 font-medium">Raw details</summary>
                          <pre className="mt-2 p-2 bg-gray-50 border border-gray-200 rounded-lg overflow-auto text-[11px]">{JSON.stringify({
                            email_log_id: sentEmailDetails.email_log_id,
                            message_id: sentEmailDetails.message_id,
                            thread_id: sentEmailDetails.thread_id,
                            raw_response: sentEmailDetails.raw_response,
                          }, null, 2)}</pre>
                        </details>
                      </>
                    ) : (
                      <div className="text-xs text-gray-700">No details available.</div>
                    )}
                  </div>
                </div>
              </div>,
              document.body
            )}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Category</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Recipient</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Subject</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">View</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Status</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Sent At</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Follow-ups</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((prospect) => (
                  <tr key={prospect.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3">
                      <span className="text-gray-700 text-xs font-medium">{prospect.discovery_category || 'N/A'}</span>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center space-x-1">
                        <Mail className="w-3 h-3 text-gray-400" />
                        <span className="text-gray-900 text-xs">{prospect.contact_email || 'N/A'}</span>
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-gray-900 text-xs">{prospect.draft_subject || 'No subject'}</span>
                    </td>
                    <td className="py-2 px-3">
                      <button
                        onClick={() => handleViewSentEmail(prospect.id)}
                        className="px-2 py-1 text-xs bg-white border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1"
                        title="View full sent email"
                      >
                        <Eye className="w-3 h-3" />
                        <span>View</span>
                      </button>
                    </td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        prospect.outreach_status === 'replied' ? 'bg-blue-100 text-blue-800' :
                        prospect.outreach_status === 'sent' ? 'bg-green-100 text-green-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {prospect.outreach_status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-xs text-gray-600">
                      {formatDate(prospect.last_sent)}
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-gray-900 text-xs">{prospect.followups_sent || 0}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-3">
            <p className="text-xs text-gray-600">
              Showing {skip + 1}-{Math.min(skip + limit, total)} of {total}
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
                className="px-2 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 text-xs font-medium"
              >
                Previous
              </button>
              <button
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= total}
                className="px-2 py-1.5 bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 text-xs font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
