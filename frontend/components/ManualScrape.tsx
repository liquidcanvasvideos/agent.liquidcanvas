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
  { value: 'home_decor', label: 'Home decor' },
  { value: 'holiday', label: 'Holiday' },
  { value: 'parenting', label: 'Parenting' },
  { value: 'audio_visuals', label: 'Audio visuals' },
  { value: 'gift_guides', label: 'Gift guides' },
  { value: 'tech_innovation', label: 'Tech innovation' },
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

  const handleScrape = async () => {
    setError(null)
    setSuccess(false)

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

    setLoading(true)
    try {
      await createDiscoveryJob(
        keywords.trim(),
        selectedLocations,
        maxResults,
        selectedCategories
      )
      setSuccess(true)
      setKeywords('') // Clear keywords after successful job creation
      setSelectedCategories([]) // Clear categories after successful job creation
      // Keep locations selected as they are often reused
    } catch (err: any) {
      console.error('Manual scrape error:', err)
      setError(err.message || 'Failed to start manual scraping. Check console for details.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Manual Website Scrape</h2>
        {loading && (
          <div className="flex items-center space-x-2 text-olive-600">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-medium">Starting job...</span>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-sm text-green-800 flex items-center">
            <CheckCircle className="w-4 h-4 mr-2" />
            Discovery job started successfully! Check the &quot;Jobs&quot; tab for status.
          </p>
        </div>
      )}

      <div className="space-y-6">
        {/* Categories Section */}
        <div>
          <label className="flex items-center space-x-2 text-sm font-semibold text-gray-700 mb-3">
            <Tag className="w-4 h-4" />
            <span>Select Categories (Recommended)</span>
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {CATEGORY_OPTIONS.map((cat) => {
              const isSelected = selectedCategories.includes(cat.value)
              return (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => toggleCategory(cat.value)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isSelected
                      ? 'bg-olive-600 text-white shadow-md transform scale-105'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  {cat.label}
                </button>
              )
            })}
          </div>
          {selectedCategories.length > 0 && (
            <p className="mt-2 text-xs text-gray-500">
              {selectedCategories.length} categor{selectedCategories.length === 1 ? 'y' : 'ies'} selected
            </p>
          )}
        </div>

        {/* Keywords Section */}
        <div>
          <label className="flex items-center space-x-2 text-sm font-semibold text-gray-700 mb-2">
            <Search className="w-4 h-4" />
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
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-500">
            Leave empty if using categories only
          </p>
        </div>

        {/* Locations Section */}
        <div>
          <label className="flex items-center space-x-2 text-sm font-semibold text-gray-700 mb-3">
            <MapPin className="w-4 h-4" />
            <span>Locations (Required)</span>
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {LOCATION_OPTIONS.map((loc) => {
              const isSelected = selectedLocations.includes(loc.value)
              return (
                <button
                  key={loc.value}
                  type="button"
                  onClick={() => toggleLocation(loc.value)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow-md transform scale-105'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  {loc.label}
                </button>
              )
            })}
          </div>
          {selectedLocations.length > 0 && (
            <p className="mt-2 text-xs text-gray-500">
              {selectedLocations.length} location{selectedLocations.length === 1 ? '' : 's'} selected
            </p>
          )}
        </div>

        {/* Max Results */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Max Results (1-1000)
          </label>
          <input
            type="number"
            value={maxResults}
            onChange={handleMaxResultsChange}
            min="1"
            max="1000"
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-transparent"
          />
        </div>

        {/* Action Button */}
        <div className="pt-4 border-t border-gray-200">
          <button
            onClick={handleScrape}
            disabled={loading || !canStart()}
            className={`w-full flex items-center justify-center space-x-2 px-6 py-3 rounded-lg font-semibold transition-all ${
              canStart() && !loading
                ? 'bg-olive-600 text-white hover:bg-olive-700 shadow-md hover:shadow-lg transform hover:scale-105'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Starting Scraping...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                <span>Start Manual Scraping</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

