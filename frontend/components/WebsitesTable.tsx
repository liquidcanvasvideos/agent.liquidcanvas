'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, Loader2, Globe, CheckCircle2, X, Trash2 } from 'lucide-react'
import { listWebsites, pipelineApprove, type Prospect } from '@/lib/api'

interface Website {
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
}

export default function WebsitesTable() {
  const [websites, setWebsites] = useState<Website[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadWebsites = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await listWebsites(skip, limit)
      console.log('📊 [WEBSITES] API Response:', { 
        dataLength: response?.data?.length, 
        total: response?.total,
        hasData: !!response?.data,
        isArray: Array.isArray(response?.data)
      })
      if (response?.data && Array.isArray(response.data)) {
        setWebsites(response.data)
        setTotal(response.total ?? response.data.length)
        console.log('✅ [WEBSITES] Set websites:', response.data.length)
      } else {
        console.warn('⚠️ [WEBSITES] Invalid response structure:', response)
        setWebsites([])
        setTotal(0)
      }
    } catch (error: any) {
      console.error('❌ [WEBSITES] Failed to load websites:', error)
      setError(error?.message || 'Failed to load websites. Check if backend is running.')
      setWebsites([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWebsites()
    const interval = setInterval(loadWebsites, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [skip])

  const handleApprove = async () => {
    if (selected.size === 0) {
      setError('Please select at least one website to approve')
      return
    }

    setActionLoading(true)
    setError(null)

    try {
      await pipelineApprove({
        prospect_ids: Array.from(selected),
        action: 'approve'
      })
      setSelected(new Set())
      await loadWebsites()
    } catch (err: any) {
      setError(err.message || 'Failed to approve websites')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApproveSingle = async (id: string) => {
    setActionLoading(true)
    setError(null)
    try {
      await pipelineApprove({
        prospect_ids: [id],
        action: 'approve',
      })
      const newSelected = new Set(selected)
      newSelected.delete(id)
      setSelected(newSelected)
      await loadWebsites()
    } catch (err: any) {
      setError(err.message || 'Failed to approve website')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this website?')) return

    setActionLoading(true)
    try {
      await pipelineApprove({
        prospect_ids: [id],
        action: 'delete'
      })
      await loadWebsites()
    } catch (err: any) {
      setError(err.message || 'Failed to delete website')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (id: string) => {
    setActionLoading(true)
    try {
      await pipelineApprove({
        prospect_ids: [id],
        action: 'reject'
      })
      await loadWebsites()
    } catch (err: any) {
      setError(err.message || 'Failed to reject website')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading && websites.length === 0) {
    return (
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
        <div className="text-center py-12">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-olive-600" />
          <p className="text-gray-500 mt-2">Loading websites...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Discovered Websites</h2>
          <p className="text-sm text-gray-600 mt-1">
            Websites found during discovery. Approve them to proceed with scraping.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={loadWebsites}
            disabled={loading}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md flex items-center space-x-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {websites.length === 0 && !loading ? (
        <div className="text-center py-12">
          <Globe className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 font-medium mb-2">No websites discovered yet</p>
          <p className="text-gray-500 text-sm mb-4">
            Run a discovery job in the Pipeline tab to find websites.
          </p>
          <p className="text-gray-400 text-xs">
            Discovery results will appear here once jobs complete.
          </p>
        </div>
      ) : (
        <>
          {selected.size > 0 && (
            <div className="mb-4 p-4 bg-olive-50 border border-olive-200 rounded-lg flex items-center justify-between">
              <p className="text-sm text-olive-900">
                {selected.size} website{selected.size !== 1 ? 's' : ''} selected
              </p>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50 flex items-center space-x-2"
              >
                {actionLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Approving...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve Selected</span>
                  </>
                )}
              </button>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4">
                    <input
                      type="checkbox"
                      checked={selected.size === websites.length && websites.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelected(new Set(websites.map(w => w.id)))
                        } else {
                          setSelected(new Set())
                        }
                      }}
                      className="w-4 h-4 text-olive-600"
                    />
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Domain</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Title</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Category</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Location</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {websites.map(website => (
                  <tr key={website.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <input
                        type="checkbox"
                        checked={selected.has(website.id)}
                        onChange={(e) => {
                          const newSelected = new Set(selected)
                          if (e.target.checked) {
                            newSelected.add(website.id)
                          } else {
                            newSelected.delete(website.id)
                          }
                          setSelected(newSelected)
                        }}
                        className="w-4 h-4 text-olive-600"
                      />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <a
                          href={website.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-olive-600 hover:text-olive-700 font-medium flex items-center space-x-1"
                        >
                          <span>{website.domain}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-700">{website.title}</td>
                    <td className="py-3 px-4 text-sm text-gray-600">{website.category}</td>
                    <td className="py-3 px-4 text-sm text-gray-600">{website.location}</td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col space-y-1">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          website.approval_status === 'approved' ? 'bg-green-100 text-green-800' :
                          website.approval_status === 'rejected' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {website.approval_status || 'PENDING'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          website.scrape_status === 'SCRAPED' || website.scrape_status === 'ENRICHED' ? 'bg-blue-100 text-blue-800' :
                          website.scrape_status === 'NO_EMAIL_FOUND' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {website.scrape_status || 'NOT_STARTED'}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {website.approval_status !== 'approved' && (
                          <button
                            onClick={() => handleApproveSingle(website.id)}
                            disabled={actionLoading}
                            className="p-1 text-green-600 hover:bg-green-50 rounded disabled:opacity-50"
                            title="Approve"
                          >
                            <CheckCircle2 className="w-4 h-4" />
                          </button>
                        )}
                        {website.approval_status !== 'rejected' && (
                          <button
                            onClick={() => handleReject(website.id)}
                            disabled={actionLoading}
                            className="p-1 text-yellow-600 hover:bg-yellow-50 rounded disabled:opacity-50"
                            title="Reject"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(website.id)}
                          disabled={actionLoading}
                          className="p-1 text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > limit && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-gray-600">
                Showing {skip + 1}-{Math.min(skip + limit, total)} of {total} websites
              </p>
              <div className="flex space-x-2">
                <button
                  onClick={() => setSkip(Math.max(0, skip - limit))}
                  disabled={skip === 0}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setSkip(skip + limit)}
                  disabled={skip + limit >= total}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
