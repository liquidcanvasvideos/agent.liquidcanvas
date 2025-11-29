'use client'

// Version: 2.0 - Complete redesign, no alert() popups, categories-first approach
import { useState } from 'react'
import { Search, Play, Square, Loader2, MapPin, Tag } from 'lucide-react'
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

export default function DiscoveryControl() {
  const [keywords, setKeywords] = useState('')
  const [selectedLocations, setSelectedLocations] = useState<string[]>(['usa'])
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggleLocation = (value: string) => {
    setSelectedLocations((prev) => {
      if (prev.includes(value)) {
        const next = prev.filter((v) => v !== value)
        return next.length > 0 ? next : prev
      }
      return [...prev, value]
    })
    setError(null)
  }

  const toggleCategory = (value: string) => {
    setSelectedCategories((prev) => {
      const newCategories = prev.includes(value)
        ? prev.filter((v) => v !== value)
        : [...prev, value]
      setError(null)
      return newCategories
    })
  }

  const canStart = () => {
    // Can start if: (keywords OR categories) AND at least one location
    const hasSearchCriteria = keywords.trim().length > 0 || selectedCategories.length > 0
    const hasLocation = selectedLocations.length > 0
    return hasSearchCriteria && hasLocation
  }

  const handleDiscover = async () => {
    // Clear any previous errors
    setError(null)

    // Client-side validation (prevents unnecessary API calls)
    if (!keywords.trim() && selectedCategories.length === 0) {
      setError('Please select at least one category OR enter keywords to search')
      return
    }

    if (selectedLocations.length === 0) {
      setError('Please select at least one location')
      return
    }

    setLoading(true)
    try {
      const result = await createDiscoveryJob(
        keywords.trim() || '',
        selectedLocations,
        100,
        selectedCategories.length > 0 ? selectedCategories : []
      )
      
      // Success - job created
      setIsRunning(true)
      setError(null)
      
      // Show success message briefly
      setTimeout(() => {
        // Job started successfully
      }, 1000)
      
    } catch (error: any) {
      // Extract error message from API response
      let errorMessage = 'Failed to start discovery'
      
      if (error?.message) {
        errorMessage = error.message
      } else if (typeof error === 'string') {
        errorMessage = error
      }
      
      // Never use alert() - always use setError() for inline display
      setError(errorMessage)
      setIsRunning(false)
      console.error('Discovery job creation failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = () => {
    setIsRunning(false)
    // TODO: Implement stop job endpoint
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Website Discovery</h2>
        {isRunning && (
          <div className="flex items-center space-x-2 text-olive-600">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-medium">Running...</span>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      <div className="space-y-6">
        {/* Categories Section - Primary */}
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

        {/* Keywords Section - Optional */}
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

        {/* Action Button */}
        <div className="pt-4 border-t border-gray-200">
          <button
            onClick={handleDiscover}
            disabled={loading || !canStart() || isRunning}
            className={`w-full flex items-center justify-center space-x-2 px-6 py-3 rounded-lg font-semibold transition-all ${
              canStart() && !loading && !isRunning
                ? 'bg-olive-600 text-white hover:bg-olive-700 shadow-md hover:shadow-lg transform hover:scale-105'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Starting Discovery...</span>
              </>
            ) : isRunning ? (
              <>
                <Square className="w-5 h-5" />
                <span>Stop Discovery</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                <span>Start Discovery</span>
              </>
            )}
          </button>
          
          {!canStart() && (
            <p className="mt-2 text-xs text-center text-gray-500">
              {!keywords.trim() && selectedCategories.length === 0
                ? 'Select at least one category or enter keywords'
                : 'Select at least one location'}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
