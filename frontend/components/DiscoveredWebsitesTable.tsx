'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, Loader2, AlertCircle, Search } from 'lucide-react'
import { listProspects, type Prospect } from '@/lib/api'
import { safeToFixed } from '@/lib/safe-utils'

interface DiscoveredWebsite {
  id: string
  domain: string
  page_title?: string
  discovery_category?: string | null
  discovery_location?: string
  discovery_keywords?: string
  scrape_status?: string
  discovery_status?: string
  created_at: string
}

export default function DiscoveredWebsitesTable() {
  const [websites, setWebsites] = useState<DiscoveredWebsite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  // Available categories
  const availableCategories = [
    'Art Lovers', 'Interior Design', 'Pet Lovers', 'Dogs and Cat Owners - Fur Parent', 'Childhood Development', 
    'Holidays', 'Famous Quotes', 'Home Decor', 
    'Audio Visual', 'Interior Decor', 'Holiday Decor', 'Home Tech', 
    'Parenting (Mom Site)', 'NFTs', 'Museum'
  ]

  const normalizeCategoryForFilter = (category: string) => {
    if (category === 'Parenting (Mom Site)') return 'Parenting'
    return category
  }

  const mapCategoryForDisplay = (category?: string | null) => {
    if (!category) return category
    if (category === 'Parenting') return 'Parenting (Mom Site)'
    return category
  }

  const loadWebsites = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Fetch discovered websites (discovery_status = 'DISCOVERED')
      const response = await listProspects(0, 1000)
      const allProspects = Array.isArray(response?.data) ? response.data : []
      
      // Filter to only discovered websites (not yet prospects - those appear after scraping)
      let discovered: DiscoveredWebsite[] = allProspects
        .filter((p: Prospect) => p.discovery_status === 'DISCOVERED')
        .map((p: Prospect) => ({
          id: p.id,
          domain: p.domain,
          page_title: p.page_title,
          discovery_category: mapCategoryForDisplay(p.discovery_category),
          discovery_location: p.discovery_location,
          discovery_keywords: p.discovery_keywords,
          scrape_status: p.scrape_status || 'DISCOVERED',
          discovery_status: p.discovery_status,
          created_at: p.created_at
        }))
      
      // Filter by category if selected
      const normalizedSelectedCategory =
        selectedCategory !== 'all' ? normalizeCategoryForFilter(selectedCategory) : 'all'

      if (normalizedSelectedCategory !== 'all') {
        discovered = discovered.filter((w: DiscoveredWebsite) => 
          w.discovery_category === normalizedSelectedCategory ||
          w.discovery_category?.toLowerCase() === normalizedSelectedCategory.toLowerCase()
        )
      }
      
      // Sort by category in ascending order
      discovered.sort((a: DiscoveredWebsite, b: DiscoveredWebsite) => {
        const catA = a.discovery_category || ''
        const catB = b.discovery_category || ''
        return catA.localeCompare(catB)
      })
      
      setWebsites(discovered)
      setTotal(discovered.length)
    } catch (error: any) {
      console.error('Failed to load discovered websites:', error)
      setError(error?.message || 'Failed to load discovered websites. Check if backend is running.')
      setWebsites([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWebsites()
    
    // Poll for new discoveries every 10 seconds
    const interval = setInterval(loadWebsites, 10000)
    
    // Listen for job completion events
    const handleJobCompleted = () => {
      console.log('🔄 Discovery job completed, refreshing websites...')
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
  }, [selectedCategory])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const getScrapeStatusBadge = (status?: string) => {
    if (!status || status === 'DISCOVERED') {
      return <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800">Ready for Scraping</span>
    }
    if (status === 'SCRAPED' || status === 'ENRICHED') {
      return <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">Scraped</span>
    }
    if (status === 'NO_EMAIL_FOUND') {
      return <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">No Email Found</span>
    }
    if (status === 'failed') {
      return <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">Failed</span>
    }
    return <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">{status}</span>
  }

  if (loading && websites.length === 0) {
    return (
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
        <div className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-olive-600 mb-4" />
          <p className="text-gray-500">Loading discovered websites...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-8 h-8 mx-auto text-red-500 mb-4" />
          <p className="text-red-600 mb-2 font-semibold">Error loading websites</p>
          <p className="text-gray-600 text-sm mb-4">{error}</p>
          <button
            onClick={loadWebsites}
            className="px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Discovered Websites</h2>
          {total > 0 && (
            <p className="text-sm text-gray-600 mt-1">
              {total} website{total !== 1 ? 's' : ''} discovered
            </p>
          )}
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
          <button
            onClick={loadWebsites}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {websites.length === 0 ? (
        <div className="text-center py-12">
          <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 font-medium mb-2">No websites discovered yet</p>
          <p className="text-gray-500 text-sm mb-4">
            Start by running a discovery search in the Pipeline tab to find websites.
          </p>
          <p className="text-gray-400 text-xs">
            Discovery jobs will appear here once they complete. Websites become prospects after scraping.
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Domain</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Title</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Category</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Location</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Discovered</th>
                </tr>
              </thead>
              <tbody>
                {websites.map((website) => (
                  <tr key={website.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{website.domain}</span>
                        <a
                          href={`https://${website.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-olive-600 hover:text-olive-700"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{website.page_title || 'N/A'}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-700">{website.discovery_category || 'N/A'}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-700">{website.discovery_location || 'N/A'}</span>
                    </td>
                    <td className="py-3 px-4">
                      {getScrapeStatusBadge(website.scrape_status)}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatDate(website.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

