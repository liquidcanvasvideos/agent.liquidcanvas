'use client'

import { useState, useEffect } from 'react'
import { Globe, ExternalLink, Filter, RefreshCw, Search, CheckCircle } from 'lucide-react'
import { getDiscoveredWebsites, type DiscoveredWebsite } from '@/lib/api'

interface Website {
  id: number
  url: string
  domain: string | null
  title: string | null
  description: string | null
  category: string | null
  website_type: string | null
  status: string
  is_art_related: boolean
  quality_score: number | null
  created_at: string
}

export default function WebsitesTable() {
  const [viewMode, setViewMode] = useState<'scraped' | 'discovered'>('discovered')
  const [websites, setWebsites] = useState<Website[]>([])
  const [discovered, setDiscovered] = useState<DiscoveredWebsite[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [limit] = useState(50)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [source, setSource] = useState<string>('')
  const [isScraped, setIsScraped] = useState<boolean | undefined>(undefined)

  const categories = [
    'interior_decor',
    'art_gallery',
    'home_tech',
    'mom_blogs',
    'nft_tech',
    'editorial_media',
    'holiday_family',
  ]

  useEffect(() => {
    if (viewMode === 'scraped') {
      loadWebsites()
    } else {
      loadDiscovered()
    }
  }, [skip, category, status, source, isScraped, viewMode])

  const loadWebsites = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        skip: skip.toString(),
        limit: limit.toString(),
      })
      if (category) params.append('category', category)
      if (status) params.append('status', status)

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/websites?${params}`
      )
      if (!res.ok) throw new Error('Failed to fetch websites')
      const data = await res.json()
      setWebsites(data)
      setTotal(data.length) // API returns array, not paginated object
    } catch (error) {
      console.error('Error loading websites:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadDiscovered = async () => {
    setLoading(true)
    try {
      const data = await getDiscoveredWebsites(skip, limit, isScraped, source || undefined, category || undefined)
      setDiscovered(data.discovered)
      setTotal(data.total)
    } catch (error) {
      console.error('Error loading discovered websites:', error)
    } finally {
      setLoading(false)
    }
  }

  const extractContacts = async (websiteId: number) => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/websites/${websiteId}/extract-contacts`,
        { method: 'POST' }
      )
      if (res.ok) {
        alert('Contact extraction started! Check Activity Feed for progress.')
        loadWebsites()
      } else {
        const error = await res.json()
        alert(`Error: ${error.detail || 'Failed to extract contacts'}`)
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <Globe className="w-5 h-5 mr-2" />
            {viewMode === 'discovered' ? 'Discovered Websites' : 'Scraped Websites'} ({total})
          </h2>
          <div className="flex items-center space-x-2 border border-gray-300 rounded-md p-1">
            <button
              onClick={() => {
                setViewMode('discovered')
                setSkip(0)
              }}
              className={`px-3 py-1 text-sm rounded ${
                viewMode === 'discovered'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <Search className="w-4 h-4 inline mr-1" />
              Discovered
            </button>
            <button
              onClick={() => {
                setViewMode('scraped')
                setSkip(0)
              }}
              className={`px-3 py-1 text-sm rounded ${
                viewMode === 'scraped'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <CheckCircle className="w-4 h-4 inline mr-1" />
              Scraped
            </button>
          </div>
        </div>
        <button
          onClick={viewMode === 'discovered' ? loadDiscovered : loadWebsites}
          className="flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-4">
          <Filter className="w-5 h-5 text-gray-500" />
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value)
              setSkip(0)
            }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </option>
            ))}
          </select>
          {viewMode === 'scraped' ? (
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value)
                setSkip(0)
              }}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="processed">Processed</option>
              <option value="failed">Failed</option>
            </select>
          ) : (
            <>
              <select
                value={source}
                onChange={(e) => {
                  setSource(e.target.value)
                  setSkip(0)
                }}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">All Sources</option>
                <option value="duckduckgo">DuckDuckGo</option>
                <option value="seed_list">Seed List</option>
                <option value="google">Google</option>
                <option value="bing">Bing</option>
              </select>
              <select
                value={isScraped === undefined ? '' : isScraped.toString()}
                onChange={(e) => {
                  const val = e.target.value
                  setIsScraped(val === '' ? undefined : val === 'true')
                  setSkip(0)
                }}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">All</option>
                <option value="false">Not Scraped</option>
                <option value="true">Scraped</option>
              </select>
            </>
          )}
          <div className="ml-auto text-sm text-gray-600">
            Showing {viewMode === 'discovered' ? discovered.length : websites.length} of {total}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading {viewMode === 'discovered' ? 'discovered websites' : 'websites'}...</div>
        ) : (viewMode === 'discovered' ? discovered.length === 0 : websites.length === 0) ? (
          <div className="p-8 text-center text-gray-500">
            {viewMode === 'discovered' 
              ? 'No discovered websites found. Run a discovery search to find websites.'
              : 'No websites found. Start scraping to see results here.'}
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Website
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Category
                </th>
                {viewMode === 'discovered' ? (
                  <>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Source
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </>
                ) : (
                  <>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Quality
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {viewMode === 'discovered' ? (
                discovered.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {item.title || item.domain || 'Untitled'}
                          </div>
                          <div className="text-sm text-gray-500 flex items-center">
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-600 hover:text-primary-800 flex items-center"
                            >
                              {item.url}
                              <ExternalLink className="w-3 h-3 ml-1" />
                            </a>
                          </div>
                          {item.snippet && (
                            <div className="text-xs text-gray-400 mt-1 line-clamp-1">
                              {item.snippet}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-olive-100 text-olive-800">
                        {item.category || 'unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
                        {item.source}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          item.is_scraped
                            ? 'bg-green-100 text-green-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {item.is_scraped ? 'Scraped' : 'Not Scraped'}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                websites.map((website) => (
                  <tr key={website.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {website.title || website.domain || 'Untitled'}
                          </div>
                          <div className="text-sm text-gray-500 flex items-center">
                            <a
                              href={website.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-600 hover:text-primary-800 flex items-center"
                            >
                              {website.url}
                              <ExternalLink className="w-3 h-3 ml-1" />
                            </a>
                          </div>
                          {website.description && (
                            <div className="text-xs text-gray-400 mt-1 line-clamp-1">
                              {website.description}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-olive-100 text-olive-800">
                        {website.category || 'unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          website.status === 'processed'
                            ? 'bg-green-100 text-green-800'
                            : website.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {website.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {website.quality_score !== null ? (
                        <span className="font-medium">{website.quality_score}/100</span>
                      ) : (
                        <span className="text-gray-400">N/A</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => extractContacts(website.id)}
                        className="text-primary-600 hover:text-primary-800 font-medium"
                      >
                        Extract Contacts
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={() => setSkip(Math.max(0, skip - limit))}
            disabled={skip === 0}
            className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">
            Page {Math.floor(skip / limit) + 1} of {Math.ceil(total / limit)}
          </span>
          <button
            onClick={() => setSkip(skip + limit)}
            disabled={skip + limit >= total}
            className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

