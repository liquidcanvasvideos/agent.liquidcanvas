'use client'

import { useState, useEffect } from 'react'
import { Search, Clock } from 'lucide-react'

interface AutomationStatus {
  automation_enabled: boolean
  search_interval_seconds: number
}

interface SearchFrequencyControlProps {
  automationStatus: AutomationStatus | null
}

export default function SearchFrequencyControl({ automationStatus }: SearchFrequencyControlProps) {
  const [updating, setUpdating] = useState(false)
  const [intervalSeconds, setIntervalSeconds] = useState(900)

  useEffect(() => {
    if (automationStatus?.search_interval_seconds) {
      setIntervalSeconds(automationStatus.search_interval_seconds)
    }
  }, [automationStatus])

  const setSearchInterval = async (seconds: number) => {
    if (seconds < 900) return
    
    setUpdating(true)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/search-interval`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ interval_seconds: seconds })
        }
      )
      if (response.ok) {
        setIntervalSeconds(seconds)
        // Reload page data
        window.location.reload()
      } else {
        const error = await response.json()
        alert(`Failed to set interval: ${error.detail || 'Unknown error'}`)
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setUpdating(false)
    }
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 3600) {
      return `${Math.round(seconds / 60)} minutes`
    }
    return `${Math.round(seconds / 3600)} hours`
  }

  const presets = [
    { seconds: 900, label: '15m' },
    { seconds: 1800, label: '30m' },
    { seconds: 3600, label: '1h' },
    { seconds: 7200, label: '2h' },
    { seconds: 14400, label: '4h' },
    { seconds: 86400, label: '24h' },
  ]

  return (
    <div className="bg-gradient-to-br from-white to-gray-50/50 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-200/60 p-5 hover:shadow-xl transition-all duration-300">
      <div className="flex items-center space-x-2.5 mb-4">
        <div className="p-2 bg-olive-600 rounded-xl shadow-md">
          <Clock className="w-4 h-4 text-white" />
        </div>
        <div>
          <h3 className="text-base font-bold text-gray-900">Search Frequency</h3>
          <p className="text-xs text-gray-500">Automatic discovery interval</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Current Interval Display */}
        <div className="bg-olive-50/50 border border-olive-200/50 rounded-xl p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-600 mb-0.5">Current Interval</p>
              <p className="text-lg font-bold text-olive-700">
                {formatInterval(intervalSeconds)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500">Every</p>
              <p className="text-sm font-semibold text-gray-700">
                {intervalSeconds < 3600 
                  ? `${Math.round(intervalSeconds / 60)} min`
                  : `${Math.round(intervalSeconds / 3600)} hr`
                }
              </p>
            </div>
          </div>
        </div>

        {/* Custom Input */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">
            Custom Interval (seconds)
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              min="900"
              step="60"
              value={intervalSeconds}
              onChange={(e) => {
                const seconds = parseInt(e.target.value) || 900
                if (seconds >= 900) {
                  setIntervalSeconds(seconds)
                }
              }}
              onBlur={() => {
                if (intervalSeconds >= 900) {
                  setSearchInterval(intervalSeconds)
                }
              }}
              disabled={updating || !automationStatus?.automation_enabled}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 text-sm focus:ring-2 focus:ring-olive-500 focus:border-olive-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
            />
            <button
              onClick={() => setSearchInterval(intervalSeconds)}
              disabled={updating || !automationStatus?.automation_enabled || intervalSeconds < 900}
              className="px-4 py-2 bg-olive-600 hover:bg-olive-700 text-white rounded-lg font-medium text-xs disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
            >
              {updating ? 'Saving...' : 'Save'}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1.5">Minimum: 900 seconds (15 minutes)</p>
        </div>

        {/* Quick Presets */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">
            Quick Presets
          </label>
          <div className="grid grid-cols-3 gap-2">
            {presets.map((preset) => (
              <button
                key={preset.seconds}
                onClick={() => setSearchInterval(preset.seconds)}
                disabled={updating || !automationStatus?.automation_enabled}
                className={`px-3 py-2 text-xs font-medium rounded-lg border transition-all ${
                  intervalSeconds === preset.seconds
                    ? 'bg-olive-600 text-white border-olive-700 shadow-md'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-olive-300'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {!automationStatus?.automation_enabled && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-2.5">
            <p className="text-xs text-yellow-800 text-center">
              Enable automation to configure search frequency
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

