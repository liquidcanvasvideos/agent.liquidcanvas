'use client'

import { useState } from 'react'
import { Search, Play, Square } from 'lucide-react'
import { createDiscoveryJob } from '@/lib/api'

export default function DiscoveryControl() {
  const [keywords, setKeywords] = useState('')
  const [location, setLocation] = useState('usa')
  const [loading, setLoading] = useState(false)
  const [isRunning, setIsRunning] = useState(false)

  const locations = [
    { value: 'usa', label: 'USA' },
    { value: 'canada', label: 'Canada' },
    { value: 'uk_london', label: 'UK/London' },
    { value: 'germany', label: 'Germany' },
    { value: 'france', label: 'France' },
    { value: 'europe', label: 'Europe' },
  ]

  const handleDiscover = async () => {
    if (!keywords.trim()) {
      alert('Please enter keywords')
      return
    }
    setLoading(true)
    try {
      await createDiscoveryJob(keywords, location, 100)
      setIsRunning(true)
    } catch (error: any) {
      alert(`Failed to start discovery: ${error.message}`)
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
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., home decor blog, parenting website"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Location
          </label>
          <select
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500"
          >
            {locations.map((loc) => (
              <option key={loc.value} value={loc.value}>
                {loc.label}
              </option>
            ))}
          </select>
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

