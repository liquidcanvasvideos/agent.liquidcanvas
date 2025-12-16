'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, Mail, Loader2, Zap } from 'lucide-react'
import { listProspects, enrichProspectById, createEnrichmentJob, type Prospect } from '@/lib/api'
import { safeToFixed } from '@/lib/safe-utils'

export default function WebsitesTable() {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [enrichingIds, setEnrichingIds] = useState<Set<string>>(new Set())
  const [bulkEnriching, setBulkEnriching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showEnrichModal, setShowEnrichModal] = useState<{ show: boolean; maxProspects: number }>({ show: false, maxProspects: 0 })

  const loadWebsites = async (preserveCurrentPage = false) => {
    try {
      // Only show loading if not preserving current page (to avoid flicker during enrichment)
      if (!preserveCurrentPage) {
        setLoading(true)
      }
      setError(null)
      console.log(`📥 Loading websites: skip=${skip}, limit=${limit}, page=${Math.floor(skip / limit) + 1}`)
      const response = await listProspects(skip, limit)
      const data = Array.isArray(response?.data) ? response.data : 
                   Array.isArray(response) ? response : []
      console.log(`📊 Loaded ${data.length} websites (total: ${response?.total ?? data.length})`)
      setProspects(data)
      setTotal(response?.total ?? data.length)
      // Clear error if we successfully got data (even if empty)
      // Empty data is not an error, it's a valid state
    } catch (error: any) {
      console.error('Failed to load websites:', error)
      const errorMessage = error?.message || 'Failed to load websites. Check if backend is running.'
      setError(errorMessage)
      setProspects([])
      setTotal(0)
    } finally {
      if (!preserveCurrentPage) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    loadWebsites()
    const interval = setInterval(() => {
      loadWebsites()
    }, 30000)
    
    const handleJobCompleted = () => {
      console.log('🔄 Job completed event received, refreshing websites table...')
      loadWebsites()
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
  }, [skip])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleEnrichEmail = async (prospectId: string, domain: string) => {
    setEnrichingIds(prev => new Set(prev).add(prospectId))
    try {
      console.log(`🔄 Starting enrichment for ${domain} (ID: ${prospectId})...`)
      const result = await enrichProspectById(prospectId)
      
      // Optimistically update the prospect in the local state immediately
      // This prevents the prospect from disappearing while we refresh
      if (result.success && result.email) {
        console.log(`✅ Email found for ${domain}: ${result.email}`)
        
        // Update the prospect in local state immediately
        setProspects(prevProspects => 
          prevProspects.map(p => 
            p.id === prospectId 
              ? { ...p, contact_email: result.email, contact_method: result.source || 'snov_io' }
              : p
          )
        )
        
        // Show success message
        alert(`✅ Email found: ${result.email}\n\nSource: ${result.source || 'Snov.io'}\nConfidence: ${result.confidence || 'N/A'}\n\nThe email has been saved and will appear in the Scraped Emails tab.`)
        
        // Trigger refresh of Scraped Emails tab so it shows the new email
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('jobsCompleted'))
        }
        
        // DON'T refresh the websites list immediately - the optimistic update keeps it visible
        // The periodic refresh (every 30s) will sync with backend later
        // This prevents the prospect from disappearing due to pagination/sorting
      } else {
        const message = result.message || result.error || 'No email found'
        console.warn(`⚠️ No email found for ${domain}: ${message}`)
        
        // Update the prospect to show it was attempted (even if no email found)
        setProspects(prevProspects => 
          prevProspects.map(p => 
            p.id === prospectId 
              ? { ...p, contact_method: 'enrichment_attempted' }
              : p
          )
        )
        
        // Show info message
        alert(`⚠️ No email found for ${domain}.\n\n${message}\n\nThe website will remain in the list.`)
        
        // DON'T refresh - the prospect stays in the list with the attempted status
        // The periodic refresh will sync with backend later
      }
    } catch (error: any) {
      console.error(`❌ Error enriching ${domain}:`, error)
      // Show error message to user
      alert(`❌ Failed to enrich ${domain}:\n\n${error.message || 'Unknown error'}\n\nThe website will remain in the list.`)
    } finally {
      setEnrichingIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(prospectId)
        return newSet
      })
    }
  }

  const handleBulkEnrich = () => {
    if (bulkEnriching) return
    
    const prospectsWithoutEmail = prospects.filter(p => !p.contact_email || p.contact_email.trim() === '')
    const count = prospectsWithoutEmail.length
    
    if (count === 0) {
      console.log('✅ All prospects already have emails!')
      return
    }
    
    // Show modal instead of prompt
    setShowEnrichModal({ show: true, maxProspects: Math.min(count, 100) })
  }

  const confirmBulkEnrich = async () => {
    const { maxProspects } = showEnrichModal
    if (!maxProspects || maxProspects <= 0) {
      setShowEnrichModal({ show: false, maxProspects: 0 })
      return
    }
    
    setShowEnrichModal({ show: false, maxProspects: 0 })
    setBulkEnriching(true)
    
    try {
      console.log(`🚀 Starting bulk enrichment job for ${maxProspects} prospects...`)
      const result = await createEnrichmentJob(undefined, maxProspects)
      console.log('✅ Enrichment job created:', result)
      console.log(`✅ Enrichment job started! Job ID: ${result.job_id}, Status: ${result.status}`)
      
      // Refresh after a delay to see updated emails
      setTimeout(() => {
        loadWebsites(true)
        // Trigger refresh of Scraped Emails tab
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('jobsCompleted'))
        }
      }, 2000)
    } catch (error: any) {
      console.error('❌ Failed to start enrichment job:', error)
      console.error(`❌ Failed to start enrichment job: ${error.message || 'Unknown error'}`)
    } finally {
      setBulkEnriching(false)
    }
  }

  const prospectsWithoutEmail = prospects.filter(p => !p.contact_email || p.contact_email.trim() === '').length

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Discovered Websites</h2>
          {prospects.length > 0 && (
            <p className="text-sm text-gray-600 mt-1">
              {prospects.length} total • {prospectsWithoutEmail} without email
            </p>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {prospects.length > 0 && (
            <button
              onClick={handleBulkEnrich}
              disabled={bulkEnriching || prospectsWithoutEmail === 0}
              className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                bulkEnriching || prospectsWithoutEmail === 0
                  ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                  : 'bg-olive-600 text-white hover:bg-olive-700'
              }`}
              title={
                prospectsWithoutEmail === 0
                  ? "All prospects already have emails"
                  : "Enrich all prospects without emails (service/brand intent only)"
              }
            >
              {bulkEnriching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Enriching...</span>
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Bulk Enrich {prospectsWithoutEmail > 0 && `(${prospectsWithoutEmail})`}</span>
                </>
              )}
            </button>
          )}
          <button
            onClick={() => loadWebsites(false)}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {loading && prospects.length === 0 ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2">Loading websites...</p>
        </div>
      ) : error ? (
        <div className="text-center py-8">
          <p className="text-red-600 mb-2 font-semibold">Error loading websites</p>
          <p className="text-gray-600 text-sm">{error}</p>
          <button
            onClick={() => loadWebsites(false)}
            className="mt-4 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
          >
            Retry
          </button>
        </div>
      ) : prospects.length === 0 && !loading ? (
        <div className="text-center py-8">
          <p className="text-gray-500 mb-2">No websites found</p>
          <p className="text-gray-400 text-sm">Run a discovery job from the Overview tab to find websites.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Domain</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Page Title</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">DA Score</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Score</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Email</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Created</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((prospect) => {
                  const isEnriching = enrichingIds.has(prospect.id)
                  const hasEmail: boolean = Boolean(prospect.contact_email && prospect.contact_email.trim() !== '')
                  return (
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
                      <span className="text-gray-900">{prospect.page_title || 'N/A'}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{safeToFixed(prospect.da_est, 1)}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{safeToFixed(prospect.score, 2)}</span>
                    </td>
                      <td className="py-3 px-4">
                        {hasEmail ? (
                          <span className="text-green-700 font-medium">{prospect.contact_email}</span>
                        ) : (
                          <span className="text-gray-500">No Email</span>
                        )}
                      </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        prospect.outreach_status === 'sent' ? 'bg-green-100 text-green-800' :
                        prospect.outreach_status === 'replied' ? 'bg-blue-100 text-blue-800' :
                        prospect.outreach_status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {prospect.outreach_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatDate(prospect.created_at)}
                    </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => handleEnrichEmail(prospect.id, prospect.domain)}
                          disabled={isEnriching || hasEmail}
                          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs transition-colors ${
                            hasEmail
                              ? 'bg-green-100 text-green-700 cursor-not-allowed'
                              : isEnriching
                                ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                                : 'bg-olive-100 text-olive-700 hover:bg-olive-200'
                          }`}
                          title={hasEmail ? "Email already found" : "Enrich email for this website"}
                        >
                          {isEnriching ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Mail className="w-3 h-3" />
                          )}
                          <span>{hasEmail ? 'Has Email' : (isEnriching ? 'Enriching...' : 'Enrich')}</span>
                        </button>
                      </td>
                  </tr>
                  )
                })}
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
    </div>
  )
}

