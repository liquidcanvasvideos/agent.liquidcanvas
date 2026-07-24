'use client'

import { useState } from 'react'
import { Search, Play, Loader2, MapPin, Tag, CheckCircle, XCircle } from 'lucide-react'
import { createDiscoveryJob } from '@/lib/api'

const LOCATION_OPTIONS = [
  { value: 'usa', label: 'USA' },
  { value: 'canada', label: 'Canada' },
  { value: 'uk_london', label: 'UK / London' },
  { value: 'germany', label: 'Germany' },
  { value: 'france', label: 'France' },
  { value: 'europe', label: 'Europe' },
]

const CATEGORY_OPTIONS = [
  { value: 'Art Lovers', label: 'Art Lovers' },
  { value: 'Interior Design', label: 'Interior Design' },
  { value: 'Pet Lovers', label: 'Pet Lovers' },
  { value: 'Dogs and Cat Owners - Fur Parent', label: 'Dogs and Cat Owners - Fur Parent' },
  { value: 'Childhood Development', label: 'Childhood Development' },
  { value: 'Holidays', label: 'Holidays' },
  { value: 'Famous Quotes', label: 'Famous Quotes' },
  { value: 'Home Decor', label: 'Home Decor' },
  { value: 'Audio Visual', label: 'Audio Visual' },
  { value: 'Interior Decor', label: 'Interior Decor' },
  { value: 'Holiday Decor', label: 'Holiday Decor' },
  { value: 'Home Tech', label: 'Home Tech' },
  { value: 'Parenting', label: 'Parenting (Mom Site)' },
  { value: 'NFTs', label: 'NFTs' },
  { value: 'Museum', label: 'Museum' },
]

export default function ManualScrape() {
  const [keywords, setKeywords] = useState('')
  const [selectedLocations, setSelectedLocations] = useState<string[]>(['usa'])
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [maxResults, setMaxResults] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<boolean>(false)

  const toggleLocation = (value: string) => {
    setSelectedLocations((prev) => {
      if (prev.includes(value)) {
        const next = prev.filter((v) => v !== value)
        return next.length > 0 ? next : prev // Ensure at least one is always selected
      }
      return [...prev, value]
    })
    setError(null)
    setSuccess(false)
  }

  const toggleCategory = (value: string) => {
    setSelectedCategories((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    )
    setError(null)
    setSuccess(false)
  }

  const handleMaxResultsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value)
    if (!isNaN(value) && value >= 1 && value <= 1000) {
      setMaxResults(value)
    } else if (e.target.value === '') {
      setMaxResults(0) // Allow empty input temporarily
    }
    setError(null)
    setSuccess(false)
  }

  const canStart = () => {
    const hasSearchCriteria = keywords.trim().length > 0 || selectedCategories.length > 0
    const hasLocation = selectedLocations.length > 0
    const hasMaxResults = maxResults > 0
    return hasSearchCriteria && hasLocation && hasMaxResults
  }

  /**
   * Handle manual scraping with robust error handling and validation
   * Ensures authentication, validates input, and handles all error cases gracefully
   */
  const handleScrape = async () => {
    // Reset state
    setError(null)
    setSuccess(false)

    // Validate input before making request
    if (!canStart()) {
      if (!keywords.trim() && selectedCategories.length === 0) {
        setError('Please select at least one category OR enter keywords to search.')
      } else if (selectedLocations.length === 0) {
        setError('Please select at least one location.')
      } else if (maxResults === 0) {
        setError('Please enter a valid number for max results (1-1000).')
      }
      return
    }

    // Check for authentication token before proceeding
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (!token) {
      setError('Authentication required. Please log in first.')
      // Optionally redirect to login
      if (typeof window !== 'undefined') {
        setTimeout(() => {
          window.location.href = '/login'
        }, 2000)
      }
      return
    }

    setLoading(true)
    
    try {
      console.log('🚀 Starting manual scrape:', {
        keywords: keywords.trim() || '(none)',
        locations: selectedLocations.length,
        categories: selectedCategories.length,
        maxResults
      })
      
      // Call API with validated parameters
      const result = await createDiscoveryJob(
        keywords.trim(),
        selectedLocations, // Already validated as non-empty array
        maxResults, // Already validated as > 0
        selectedCategories // Already validated (either this or keywords exists)
      )
      
      // Validate response - ensure we got a valid job object
      if (!result || typeof result !== 'object') {
        throw new Error('Invalid response from server: expected job object')
      }
      
      // Check if result has required fields (id or job_id)
      const jobId = result.id || (result as any).job_id
      if (!jobId) {
        console.warn('⚠️ Manual scrape: Response missing job ID:', result)
        // Still show success if status indicates job was created
        if (result.status === 'pending' || result.status === 'running') {
          setSuccess(true)
          setKeywords('')
          setSelectedCategories([])
          return
        }
        throw new Error('Server response missing job ID')
      }
      
      console.log('✅ Manual scrape job created successfully:', jobId)
      
      // Success - clear form and show message
      setSuccess(true)
      setKeywords('') // Clear keywords after successful job creation
      setSelectedCategories([]) // Clear categories after successful job creation
      // Keep locations selected as they are often reused
      
    } catch (err: any) {
      // Enhanced error handling with specific error messages
      const errorMessage = err?.message || String(err) || 'Failed to start manual scraping'
      
      console.error('❌ Manual scrape error:', {
        message: errorMessage,
        error: err,
        stack: err?.stack
      })
      
      // Set user-friendly error message
      if (errorMessage.includes('Authentication') || errorMessage.includes('Unauthorized')) {
        setError('Authentication required. Please log in and try again.')
        // Redirect to login after showing error
        if (typeof window !== 'undefined') {
          setTimeout(() => {
            window.location.href = '/login'
          }, 2000)
        }
      } else if (errorMessage.includes('already running')) {
        setError('A discovery job is already running. Please wait for it to complete or cancel it first.')
      } else if (errorMessage.includes('Network') || errorMessage.includes('Failed to fetch')) {
        setError('Network error: Unable to connect to server. Please check your connection and try again.')
      } else {
        // Use the error message from the API or a generic one
        setError(errorMessage || 'Failed to start manual scraping. Please check the console for details.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-gray-900">Manual Website Scrape</h2>
        {loading && (
          <div className="flex items-center space-x-1 text-olive-600">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-xs font-medium">Starting job...</span>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs text-red-800">{error}</p>
        </div>
      )}
      {success && (
        <div className="mb-3 p-2 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-xs text-green-800 flex items-center">
            <CheckCircle className="w-3 h-3 mr-1" />
            Discovery job started successfully! Check the &quot;Jobs&quot; tab for status.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {/* Categories Section */}
        <div>
          <label className="flex items-center space-x-1 text-xs font-semibold text-gray-700 mb-2">
            <Tag className="w-3 h-3" />
            <span>Select Categories (Recommended)</span>
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
            {CATEGORY_OPTIONS.map((cat) => {
              const isSelected = selectedCategories.includes(cat.value)
              return (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => toggleCategory(cat.value)}
                  className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isSelected
                      ? 'bg-olive-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  {cat.label}
                </button>
              )
            })}
          </div>
          {selectedCategories.length > 0 && (
            <p className="mt-1.5 text-xs text-gray-500">
              {selectedCategories.length} categor{selectedCategories.length === 1 ? 'y' : 'ies'} selected
            </p>
          )}
        </div>

        {/* Keywords Section */}
        <div>
          <label className="flex items-center space-x-1 text-xs font-semibold text-gray-700 mb-1.5">
            <Search className="w-3 h-3" />
            <span>Keywords (Optional)</span>
          </label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => {
              setKeywords(e.target.value)
              setError(null)
              setSuccess(false)
            }}
            placeholder="e.g., art blog, creative agency, design studio"
            className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-500">
            Leave empty if using categories only
          </p>
        </div>

        {/* Locations Section */}
        <div>
          <label className="flex items-center space-x-1 text-xs font-semibold text-gray-700 mb-2">
            <MapPin className="w-3 h-3" />
            <span>Locations (Required)</span>
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
            {LOCATION_OPTIONS.map((loc) => {
              const isSelected = selectedLocations.includes(loc.value)
              return (
                <button
                  key={loc.value}
                  type="button"
                  onClick={() => toggleLocation(loc.value)}
                  className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  {loc.label}
                </button>
              )
            })}
          </div>
          {selectedLocations.length > 0 && (
            <p className="mt-1.5 text-xs text-gray-500">
              {selectedLocations.length} location{selectedLocations.length === 1 ? '' : 's'} selected
            </p>
          )}
        </div>

        {/* Max Results */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">
            Max Results (1-1000)
          </label>
          <input
            type="number"
            value={maxResults}
            onChange={handleMaxResultsChange}
            min="1"
            max="1000"
            className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-transparent"
          />
        </div>

        {/* Action Button */}
        <div className="pt-2 border-t border-gray-200">
          <button
            onClick={handleScrape}
            disabled={loading || !canStart()}
            className={`w-full flex items-center justify-center space-x-1 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
              canStart() && !loading
                ? 'bg-olive-600 text-white hover:bg-olive-700 shadow-md'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Starting Scraping...</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3" />
                <span>Start Manual Scraping</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

