'use client'

import { useState } from 'react'
import { Search, Play, Square } from 'lucide-react'
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

  const toggleLocation = (value: string) => {
    setSelectedLocations((prev) => {
      if (prev.includes(value)) {
        const next = prev.filter((v) => v !== value)
        // Ensure at least one location remains selected
        return next.length > 0 ? next : prev
      }
      return [...prev, value]
    })
  }

  const toggleCategory = (value: string) => {
    setSelectedCategories((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    )
  }

  const handleDiscover = async () => {
    // Debug: log current state - use console.error so it always shows
    const debugInfo = {
      keywords: keywords.trim(),
      keywordsLength: keywords.trim().length,
      selectedCategories: selectedCategories,
      categoriesLength: selectedCategories.length,
      selectedLocations: selectedLocations,
      locationsLength: selectedLocations.length
    }
    console.error('🔍 DISCOVERY DEBUG:', debugInfo)
    console.log('🔍 DISCOVERY DEBUG:', debugInfo)

    // Require at least one signal to search: keywords or categories
    const hasKeywords = keywords.trim().length > 0
    const hasCategories = selectedCategories.length > 0
    
    if (!hasKeywords && !hasCategories) {
      console.error('❌ VALIDATION FAILED: No keywords and no categories selected')
      alert(`Please enter keywords OR select at least one category.\n\nCurrent state:\n- Keywords: "${keywords.trim()}"\n- Categories selected: ${selectedCategories.length}\n- Categories: ${selectedCategories.join(', ') || 'none'}`)
      return
    }

    if (selectedLocations.length === 0) {
      console.error('❌ VALIDATION FAILED: No locations selected')
      alert('Please select at least one location')
      return
    }

    setLoading(true)
    try {
      // Pass locations and categories arrays to the API
      // Send empty string if no keywords (backend expects string, not null)
      await createDiscoveryJob(
        hasKeywords ? keywords.trim() : '', 
        selectedLocations, 
        100, 
        hasCategories ? selectedCategories : []
      )
      setIsRunning(true)
      // Clear form after successful start
      setKeywords('')
      setSelectedCategories([])
    } catch (error: any) {
      console.error('Discovery error:', error)
      alert(`Failed to start discovery: ${error.message || 'Unknown error'}`)
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
      <h2 className="text-lg font-bold text-gray-900 mb-4">Website Discovery</h2>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Keywords
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="w-4 h-4 text-gray-400" />
            </span>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="e.g., home decor blog, parenting website"
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Locations (select one or more)
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {LOCATION_OPTIONS.map((loc) => (
              <label
                key={loc.value}
                className={`flex items-center space-x-2 px-3 py-2 border rounded-lg text-sm cursor-pointer ${
                  selectedLocations.includes(loc.value)
                    ? 'border-olive-600 bg-olive-50 text-olive-800'
                    : 'border-gray-300 text-gray-700 hover:border-olive-400'
                }`}
              >
                <input
                  type="checkbox"
                  className="hidden"
                  checked={selectedLocations.includes(loc.value)}
                  onChange={() => toggleLocation(loc.value)}
                />
                <span>{loc.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Categories (optional, select multiple)
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {CATEGORY_OPTIONS.map((cat) => (
              <label
                key={cat.value}
                className={`flex items-center space-x-2 px-3 py-2 border rounded-lg text-sm cursor-pointer ${
                  selectedCategories.includes(cat.value)
                    ? 'border-olive-600 bg-olive-50 text-olive-800'
                    : 'border-gray-300 text-gray-700 hover:border-olive-400'
                }`}
              >
                <input
                  type="checkbox"
                  className="hidden"
                  checked={selectedCategories.includes(cat.value)}
                  onChange={() => toggleCategory(cat.value)}
                />
                <span>{cat.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Debug panel - shows current state */}
        <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-600">
          <div className="font-semibold mb-1">Debug Info:</div>
          <div>Keywords: "{keywords.trim()}" ({keywords.trim().length} chars)</div>
          <div>Categories: {selectedCategories.length} selected - {selectedCategories.join(', ') || 'none'}</div>
          <div>Locations: {selectedLocations.length} selected - {selectedLocations.join(', ')}</div>
          <div className="mt-1">
            Can start: {((keywords.trim().length > 0 || selectedCategories.length > 0) && selectedLocations.length > 0) ? '✅ YES' : '❌ NO'}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {!isRunning ? (
            <button
              onClick={handleDiscover}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              <span>Start Discovery</span>
            </button>
          ) : (
            <button
              onClick={handleStop}
              className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              <Square className="w-4 h-4" />
              <span>Stop</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

