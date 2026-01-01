'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, Loader2, Globe, CheckCircle2, X, Trash2 } from 'lucide-react'
import { listWebsites, pipelineApprove, updateProspectCategory, type Prospect } from '@/lib/api'

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
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [showCategoryUpdate, setShowCategoryUpdate] = useState(false)
  const [updateCategory, setUpdateCategory] = useState<string>('')
  const [isUpdatingCategory, setIsUpdatingCategory] = useState(false)

  // Available categories
  const availableCategories = [
    'Art Gallery', 'Museum', 'Museums', 'Art Studio', 'Art School', 'Art Fair', 
    'Art Dealer', 'Art Consultant', 'Art Publisher', 'Art Magazine'
  ]

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
        let websitesData = response.data
        
        // Filter by category if selected
        if (selectedCategory !== 'all') {
          websitesData = websitesData.filter((w: Website) => 
            w.category === selectedCategory || w.category?.toLowerCase() === selectedCategory.toLowerCase()
          )
        }
        
        // Sort by category in ascending order
        websitesData.sort((a: Website, b: Website) => {
          const catA = a.category || ''
          const catB = b.category || ''
          return catA.localeCompare(catB)
        })
        
        setWebsites(websitesData)
        setTotal(selectedCategory === 'all' ? (response.total ?? websitesData.length) : websitesData.length)
        console.log('✅ [WEBSITES] Set websites:', websitesData.length)
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
  }, [skip, selectedCategory])

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

  const handleUpdateCategory = async () => {
    if (selected.size === 0) {
      setError('Please select at least one website to update')
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
        prospect_ids: Array.from(selected),
        category: updateCategory.trim()
      })
      setError(`✅ ${result.message}`)
      setSelected(new Set())
      setShowCategoryUpdate(false)
      setUpdateCategory('')
      setTimeout(() => {
        loadWebsites()
      }, 500)
    } catch (err: any) {
      setError(err.message || 'Failed to update category')
    } finally {
      setIsUpdatingCategory(false)
    }
  }

  if (loading && websites.length === 0) {
    return (
      <div className="glass rounded-3xl shadow-xl p-8 animate-fade-in">
        <div className="text-center py-12">
          <div className="relative inline-block">
            <div className="w-12 h-12 rounded-full border-4 border-liquid-200"></div>
            <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-4 border-t-liquid-500 border-r-purple-500 animate-spin"></div>
          </div>
          <p className="text-gray-600 mt-4 font-medium">Loading websites...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-sm font-bold text-olive-700 mb-1">Discovered Websites</h2>
          <p className="text-sm text-gray-600">
            Websites found during discovery. Approve them to proceed with scraping.
          </p>
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
          {selected.size > 0 && (
            <button
              onClick={() => setShowCategoryUpdate(true)}
              className="px-2 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Update Category ({selected.size})
            </button>
          )}
          <button
            onClick={loadWebsites}
            disabled={loading}
            className="px-2 py-1 text-xs glass hover:bg-white/80 text-gray-700 rounded-lg flex items-center space-x-1 disabled:opacity-50 transition-all duration-200 font-medium hover:shadow-md"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-gradient-to-r from-red-50 to-pink-50 border-2 border-red-300 rounded-xl text-red-700 text-sm font-medium animate-slide-up">
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
            <div className="mb-2 p-2 bg-gradient-to-r from-olive-50 to-olive-50 border border-olive-200 rounded-lg flex items-center justify-between shadow-sm animate-slide-up">
              <p className="text-sm font-semibold text-gray-700">
                {selected.size} website{selected.size !== 1 ? 's' : ''} selected
              </p>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-2 py-1 text-xs bg-olive-600 text-white rounded-lg hover:bg-olive-700 hover:shadow-md transition-all duration-200 disabled:opacity-50 flex items-center space-x-1 font-semibold shadow-sm"
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
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Domain</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Title</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Category</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Location</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Status</th>
                  <th className="text-left py-2 px-3 text-xs font-bold text-gray-700 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {websites.map(website => (
                  <tr key={website.id} className="border-b border-gray-100 hover:bg-gradient-to-r hover:from-liquid-50/30 hover:to-purple-50/30 transition-all duration-200">
                    <td className="py-2 px-3 text-xs">
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
                    <td className="py-4 px-6">
                      <div className="flex items-center space-x-2">
                        <a
                          href={website.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-olive-700 hover:underline text-xs font-semibold flex items-center space-x-1 transition-all duration-200"
                        >
                          <span>{website.domain}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </td>
                    <td className="py-2 px-3 text-xs text-gray-700 font-medium">{website.title}</td>
                    <td className="py-2 px-3 text-xs text-gray-600">{website.category}</td>
                    <td className="py-2 px-3 text-xs text-gray-600">{website.location}</td>
                    <td className="py-4 px-6">
                      <div className="flex flex-col space-y-1">
                        <span className={`px-3 py-1 rounded-lg text-xs font-semibold shadow-sm ${
                          website.approval_status === 'approved' ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white' :
                          website.approval_status === 'rejected' ? 'bg-gradient-to-r from-red-500 to-pink-600 text-white' :
                          'bg-gray-200 text-gray-700'
                        }`}>
                          {website.approval_status || 'PENDING'}
                        </span>
                        <span className={`px-3 py-1 rounded-lg text-xs font-semibold shadow-sm ${
                          website.scrape_status === 'SCRAPED' || website.scrape_status === 'ENRICHED' ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white' :
                          website.scrape_status === 'NO_EMAIL_FOUND' ? 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white' :
                          'bg-gray-200 text-gray-700'
                        }`}>
                          {website.scrape_status || 'NOT_STARTED'}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center space-x-2">
                        {website.approval_status !== 'approved' && (
                          <button
                            onClick={() => handleApproveSingle(website.id)}
                            disabled={actionLoading}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-xl transition-all duration-200 disabled:opacity-50 hover:scale-110"
                            title="Approve"
                          >
                            <CheckCircle2 className="w-4 h-4" />
                          </button>
                        )}
                        {website.approval_status !== 'rejected' && (
                          <button
                            onClick={() => handleReject(website.id)}
                            disabled={actionLoading}
                            className="p-2 text-yellow-600 hover:bg-yellow-50 rounded-xl transition-all duration-200 disabled:opacity-50 hover:scale-110"
                            title="Reject"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(website.id)}
                          disabled={actionLoading}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-xl transition-all duration-200 disabled:opacity-50 hover:scale-110"
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
                Update category for {selected.size} selected website(s)
              </p>
              <select
                value={updateCategory}
                onChange={(e) => setUpdateCategory(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-olive-500 focus:border-olive-500 bg-white"
              >
                <option value="">Select Category</option>
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
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
    </div>
  )
}
