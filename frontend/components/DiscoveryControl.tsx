'use client'

import { useState, useEffect } from 'react'
import { Search, Loader2, CheckCircle2, AlertCircle, BarChart3, Square, Zap } from 'lucide-react'

interface DiscoveryStatus {
  status: string
  last_run?: string
  result?: {
    discovered?: number
    new_websites?: number
    skipped?: number
    failed?: number
  }
  error?: string
  started_at?: string
  completed_at?: string
  search_sources?: Record<string, number>
  recent_queries?: Array<{ query: string; count: number }>
}

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
}

interface Location {
  value: string
  label: string
}

interface Category {
  value: string
  label: string
}

export default function DiscoveryControl() {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null)
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [showStats, setShowStats] = useState(false)
  const [locations, setLocations] = useState<Location[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedLocations, setSelectedLocations] = useState<string[]>([])
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])

  useEffect(() => {
    loadStatus()
    loadAutomationStatus()
    loadLocations()
    loadCategories()
    // Refresh every 10 seconds
    const interval = setInterval(() => {
      loadStatus()
      loadAutomationStatus()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadLocations = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/locations`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        const data = await response.json()
        setLocations(data.locations || [])
      }
    } catch (error) {
      console.error('Error loading locations:', error)
    }
  }

  const loadCategories = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/categories`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        const data = await response.json()
        setCategories(data.categories || [])
      }
    } catch (error) {
      console.error('Error loading categories:', error)
    }
  }

  const loadStatus = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/status`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Error loading discovery status:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAutomationStatus = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/status`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        const data = await response.json()
        setAutomationStatus(data)
      }
    } catch (error) {
      console.error('Error loading automation status:', error)
    }
  }

  const triggerSearch = async () => {
    // Check if automation is enabled
    if (!automationStatus?.automation_enabled) {
      alert('Please enable automation (Master Switch) before running searches')
      return
    }
    
    // Check if at least one location is selected
    if (selectedLocations.length === 0) {
      alert('Please select at least one location before running searches')
      return
    }
    
    setSearching(true)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      // Build query params
      const params = new URLSearchParams()
      if (selectedLocations.length > 0) {
        params.append('location', selectedLocations.join(','))
      }
      if (selectedCategories.length > 0) {
        params.append('categories', selectedCategories.join(','))
      }
      
      const url = `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/search-now${params.toString() ? '?' + params.toString() : ''}`
      
      const response = await fetch(
        url,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        // Wait a moment then refresh status
        setTimeout(() => {
          loadStatus()
        }, 2000)
      } else {
        alert('Failed to start search')
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setSearching(false)
    }
  }

  const stopSearch = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/stop`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        setTimeout(() => {
          loadStatus()
        }, 1000)
      } else {
        alert('Failed to stop search')
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    }
  }

  const formatTime = (timeString?: string) => {
    if (!timeString) return 'Never'
    const date = new Date(timeString)
    // Show actual time instead of "ago" format
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // Only show "Search Now" button if automation is in manual mode
  const isManualMode = automationStatus?.email_trigger_mode === 'manual'
  const isAutomationOn = automationStatus?.automation_enabled

  return (
    <div className="bg-gradient-to-br from-white via-white to-olive-50/30 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-200/60 p-6 hover:shadow-xl transition-all duration-300">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-gradient-to-br from-olive-600 to-olive-700 rounded-xl shadow-md">
            <Search className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Website Discovery</h2>
            <p className="text-xs text-gray-500">Automated search & scraping</p>
          </div>
        </div>
        <button
          onClick={() => setShowStats(!showStats)}
          className="p-2 text-gray-600 hover:text-olive-600 hover:bg-olive-50 rounded-lg transition-all"
          title="Show discovery statistics"
        >
          <BarChart3 className="w-4 h-4" />
        </button>
      </div>

      {/* Status Display */}
      {loading ? (
        <div className="flex items-center justify-center space-x-2 py-8">
          <Loader2 className="w-5 h-5 animate-spin text-olive-600" />
          <span className="text-sm text-gray-600">Loading status...</span>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Current Status - Modern Card */}
          <div className={`relative overflow-hidden rounded-xl p-4 ${
            status?.status === 'running' 
              ? 'bg-gradient-to-r from-olive-50 to-green-50 border-2 border-olive-300' 
              : status?.status === 'completed'
              ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300'
              : status?.status === 'failed'
              ? 'bg-gradient-to-r from-red-50 to-rose-50 border-2 border-red-300'
              : 'bg-gray-50 border-2 border-gray-300'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {status?.status === 'running' ? (
                  <>
                    <div className="p-2 bg-olive-600 rounded-lg shadow-md">
                      <Loader2 className="w-5 h-5 text-white animate-spin" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">Searching Internet...</p>
                      <p className="text-xs text-gray-600 mt-0.5">
                        {status.started_at ? `Started: ${formatTime(status.started_at)}` : 'In progress'}
                      </p>
                    </div>
                  </>
                ) : status?.status === 'completed' ? (
                  <>
                    <div className="p-2 bg-green-500 rounded-lg shadow-md">
                      <CheckCircle2 className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">Last Search Completed</p>
                      <p className="text-xs text-gray-600 mt-0.5">
                        {status.completed_at ? formatTime(status.completed_at) : 'Unknown'}
                      </p>
                    </div>
                  </>
                ) : status?.status === 'failed' ? (
                  <>
                    <div className="p-2 bg-red-500 rounded-lg shadow-md">
                      <AlertCircle className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">Last Search Failed</p>
                      <p className="text-xs text-red-600 mt-0.5">{status.error || 'Unknown error'}</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="p-2 bg-gray-400 rounded-lg shadow-md">
                      <AlertCircle className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">Never Run</p>
                      <p className="text-xs text-gray-600 mt-0.5">No searches have been performed yet</p>
                    </div>
                  </>
                )}
              </div>
              {status?.status === 'running' && (
                <button
                  onClick={stopSearch}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-all text-sm font-medium flex items-center space-x-2 shadow-md hover:shadow-lg"
                  title="Stop current search"
                >
                  <Square className="w-4 h-4" />
                  <span>Stop</span>
                </button>
              )}
            </div>
          </div>

          {/* Statistics Panel (Toggle) - Modern Design */}
          {showStats && status && (
            <div className="bg-gradient-to-br from-white to-gray-50 rounded-xl p-4 border-2 border-gray-200 shadow-md space-y-4">
              <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                <BarChart3 className="w-4 h-4 mr-2 text-olive-600" />
                Last Search Results
              </h3>
              
              {status.result && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-white rounded-lg p-3 border border-gray-200 shadow-sm">
                    <p className="text-xs font-medium text-gray-500 mb-1">Discovered</p>
                    <p className="text-xl font-bold text-gray-900">
                      {status.result.discovered || 0}
                    </p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 border border-green-200 shadow-sm">
                    <p className="text-xs font-medium text-green-700 mb-1">New Websites</p>
                    <p className="text-xl font-bold text-green-600">
                      {status.result.new_websites || 0}
                    </p>
                  </div>
                  <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200 shadow-sm">
                    <p className="text-xs font-medium text-yellow-700 mb-1">Skipped</p>
                    <p className="text-xl font-bold text-yellow-600">
                      {status.result.skipped || 0}
                    </p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-3 border border-red-200 shadow-sm">
                    <p className="text-xs font-medium text-red-700 mb-1">Failed</p>
                    <p className="text-xl font-bold text-red-600">
                      {status.result.failed || 0}
                    </p>
                  </div>
                </div>
              )}
              
              {/* Search Source Breakdown */}
              {status.search_sources && Object.keys(status.search_sources).length > 0 && (
                <div className="border-t border-gray-200 pt-3 mt-3">
                  <h4 className="text-xs font-bold text-gray-700 mb-2">Search Sources</h4>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(status.search_sources).map(([source, count]) => (
                      <div key={source} className="bg-olive-50 border border-olive-200 rounded-lg px-3 py-1.5">
                        <span className="text-xs font-semibold text-olive-800 capitalize">
                          {source === 'dataforseo' ? 'DataForSEO (Google SERP)' : source === 'duckduckgo' ? 'DuckDuckGo' : source}
                        </span>
                        <span className="text-xs text-olive-600 ml-2">({count})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Recent Search Queries */}
              {status.recent_queries && status.recent_queries.length > 0 && (
                <div className="border-t border-gray-200 pt-3 mt-3">
                  <h4 className="text-xs font-bold text-gray-700 mb-2">Recent Search Queries</h4>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {status.recent_queries.map((item: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between text-xs bg-white rounded px-2 py-1 border border-gray-200">
                        <span className="text-gray-700 font-medium">{item.query}</span>
                        <span className="text-gray-500">({item.count} found)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Location and Category Selection - Modern Design */}
          <div className="space-y-4 border-t border-gray-200 pt-4 mt-4">
            <div>
              <label className="block text-sm font-bold text-gray-900 mb-2">
                Search Locations
              </label>
              <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto bg-white rounded-lg border-2 border-gray-200 p-3">
                {locations.map((loc) => (
                  <label key={loc.value} className="flex items-center space-x-2 cursor-pointer p-2 rounded-lg hover:bg-olive-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedLocations.includes(loc.value)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedLocations([...selectedLocations, loc.value])
                        } else {
                          setSelectedLocations(selectedLocations.filter(l => l !== loc.value))
                        }
                      }}
                      className="w-4 h-4 rounded border-gray-300 text-olive-600 focus:ring-2 focus:ring-olive-500"
                    />
                    <span className="text-sm text-gray-700 font-medium">{loc.label}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1.5">Select one or more locations</p>
            </div>
            
            <div>
              <label className="block text-sm font-bold text-gray-900 mb-2">
                Categories <span className="text-xs font-normal text-gray-500">(Optional)</span>
              </label>
              <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto bg-white rounded-lg border-2 border-gray-200 p-3">
                {categories.map((cat) => (
                  <label key={cat.value} className="flex items-center space-x-2 cursor-pointer p-2 rounded-lg hover:bg-olive-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(cat.value)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedCategories([...selectedCategories, cat.value])
                        } else {
                          setSelectedCategories(selectedCategories.filter(c => c !== cat.value))
                        }
                      }}
                      className="w-4 h-4 rounded border-gray-300 text-olive-600 focus:ring-2 focus:ring-olive-500"
                    />
                    <span className="text-sm text-gray-700 font-medium">{cat.label}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1.5">Leave empty to search all categories</p>
            </div>
          </div>

          {/* Automation Info - Modern Design */}
          {isAutomationOn && (
            <div className="bg-gradient-to-r from-olive-50 to-green-50 border-2 border-olive-200 rounded-xl p-4 mt-4">
              <div className="flex items-start space-x-2">
                <div className="p-1.5 bg-olive-600 rounded-lg">
                  <Zap className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-bold text-olive-900 mb-1">
                    Automatic Mode Active
                  </p>
                  <p className="text-xs text-olive-700">
                    Searching every {automationStatus?.search_interval_seconds ? Math.floor(automationStatus.search_interval_seconds / 60) : '15'} minutes. 
                    You can also trigger manual searches anytime.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Manual Search Button - Modern Design */}
          {isAutomationOn && (
            <div className="border-t border-gray-200 pt-4 mt-4">
              <button
                onClick={triggerSearch}
                disabled={searching || status?.status === 'running'}
                className="w-full px-6 py-3 bg-gradient-to-r from-olive-600 to-olive-700 text-white rounded-xl font-bold hover:from-olive-700 hover:to-olive-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center justify-center space-x-2 text-sm transform hover:scale-[1.02]"
              >
                {searching || status?.status === 'running' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Searching Internet...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    <span>Search Now (Manual Trigger)</span>
                  </>
                )}
              </button>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Manual search runs independently of automatic schedule
              </p>
            </div>
          )}
          {!isAutomationOn && (
            <div className="border-t border-gray-200 pt-4 mt-4">
              <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border-2 border-yellow-300 rounded-xl p-4">
                <p className="text-sm font-medium text-yellow-900 text-center">
                  ⚠️ Enable automation (Master Switch) to use manual search
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
