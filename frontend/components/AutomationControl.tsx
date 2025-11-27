'use client'

import { useState, useEffect } from 'react'
import { Power, Mail, Settings, Search, MapPin, Zap } from 'lucide-react'

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
  settings: Record<string, any>
}

interface Location {
  value: string
  label: string
}

interface Category {
  value: string
  label: string
}

export default function AutomationControl() {
  const [status, setStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [locations, setLocations] = useState<Location[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedLocations, setSelectedLocations] = useState<string[]>([])
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [automaticScraperEnabled, setAutomaticScraperEnabled] = useState<boolean>(false)
  const [isSavingLocations, setIsSavingLocations] = useState(false)
  const [lastLocationUpdate, setLastLocationUpdate] = useState<number>(0)

  useEffect(() => {
    loadStatus()
    loadLocations()
    loadCategories()
    // Refresh every 5 seconds
    const interval = setInterval(loadStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (status?.settings) {
      setAutomaticScraperEnabled(status.settings.automatic_scraper_enabled || false)
      
      // Only update locations from status if:
      // 1. We're not currently saving locations
      // 2. It's been more than 2 seconds since the last user update
      // 3. The status actually has locations (not empty)
      const now = Date.now()
      const timeSinceLastUpdate = now - lastLocationUpdate
      
      if (!isSavingLocations && timeSinceLastUpdate > 2000) {
        if (status.settings.search_location) {
          const locations = typeof status.settings.search_location === 'string'
            ? status.settings.search_location.split(',').filter(l => l.trim())
            : status.settings.search_location
          const newLocations = Array.isArray(locations) ? locations : [locations]
          
          // Only update if different from current selection
          const currentStr = selectedLocations.sort().join(',')
          const newStr = newLocations.sort().join(',')
          if (currentStr !== newStr) {
            setSelectedLocations(newLocations)
          }
        } else if (selectedLocations.length > 0 && timeSinceLastUpdate > 5000) {
          // Only clear if it's been a while and status says empty
          setSelectedLocations([])
        }
      }
      
      if (status.settings.search_categories) {
        setSelectedCategories(
          typeof status.settings.search_categories === 'string'
            ? status.settings.search_categories.split(',').filter(c => c.trim())
            : status.settings.search_categories
        )
      }
    }
  }, [status, isSavingLocations, lastLocationUpdate])

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
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/status`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Error loading automation status:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleAutomation = async (enabled: boolean) => {
    setUpdating(true)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/toggle`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ enabled })
        }
      )
      if (response.ok) {
        await loadStatus()
      } else {
        const error = await response.json()
        alert(`Failed to toggle automation: ${error.detail || 'Unknown error'}`)
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setUpdating(false)
    }
  }

  const toggleAutomaticScraper = async (enabled: boolean) => {
    if (enabled && selectedLocations.length === 0) {
      alert('Please select at least one location before enabling automatic scraper')
      return
    }
    
    setUpdating(true)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      // Save locations first if enabling
      if (enabled && selectedLocations.length > 0) {
        await saveLocations()
      }
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/automatic-scraper/toggle`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ enabled })
        }
      )
      if (response.ok) {
        await loadStatus()
      } else {
        const error = await response.json()
        alert(`Failed to toggle automatic scraper: ${error.detail || 'Unknown error'}`)
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setUpdating(false)
    }
  }

  const saveLocations = async (locationsToSave: string[]) => {
    setIsSavingLocations(true)
    setLastLocationUpdate(Date.now())
    
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) {
        setIsSavingLocations(false)
        return
      }
      
      // Save locations via settings API
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/locations`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ locations: locationsToSave })
        }
      )
      if (response.ok) {
        // Reload status to get updated settings from backend
        await loadStatus()
      } else {
        console.error('Failed to save locations')
        // Revert on error
        const errorData = await response.json().catch(() => ({}))
        console.error('Error details:', errorData)
      }
    } catch (error) {
      console.error('Error saving locations:', error)
    } finally {
      // Wait a bit before allowing status updates to overwrite
      setTimeout(() => {
        setIsSavingLocations(false)
      }, 1500)
    }
  }

  const setEmailMode = async (mode: 'automatic' | 'manual') => {
    setUpdating(true)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      if (!token) return
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/email-trigger-mode`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ mode })
        }
      )
      if (response.ok) {
        await loadStatus()
      } else {
        const error = await response.json()
        alert(`Failed to set email mode: ${error.detail || 'Unknown error'}`)
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setUpdating(false)
    }
  }

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
        await loadStatus()
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

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-10 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <p className="text-red-600">Failed to load automation status</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
        <Settings className="w-5 h-5 mr-2" />
        Automation Settings
      </h2>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Master Switch */}
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-xl p-5 border-2 border-gray-200 shadow-md hover:shadow-lg transition-all">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <Power className="w-5 h-5 text-gray-600" />
              <h3 className="text-sm font-semibold text-gray-900">Master Switch</h3>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={status.automation_enabled}
                onChange={(e) => toggleAutomation(e.target.checked)}
                disabled={updating}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-olive-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-olive-600"></div>
            </label>
          </div>
          <p className="text-xs text-gray-600">
            Enable to activate all automation features
          </p>
        </div>

        {/* Automatic Scraper Switch */}
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-xl p-5 border-2 border-gray-200 shadow-md hover:shadow-lg transition-all">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <Zap className="w-5 h-5 text-gray-600" />
              <h3 className="text-sm font-semibold text-gray-900">Automatic Scraper</h3>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={automaticScraperEnabled}
                onChange={(e) => toggleAutomaticScraper(e.target.checked)}
                disabled={updating || !status.automation_enabled || selectedLocations.length === 0}
                className="sr-only peer"
              />
              <div className={`w-11 h-6 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all ${
                !status.automation_enabled || selectedLocations.length === 0
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-gray-200 peer-checked:bg-olive-600'
              }`}></div>
            </label>
          </div>
          <p className="text-xs text-gray-600">
            Runs searches automatically at set intervals
          </p>
          {selectedLocations.length === 0 && status.automation_enabled && (
            <p className="text-xs text-yellow-600 mt-1">
              Select at least one location first
            </p>
          )}
        </div>

        {/* Location Selection - Multiple */}
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-xl p-5 border-2 border-gray-200 shadow-md hover:shadow-lg transition-all">
          <div className="flex items-center space-x-2 mb-2">
            <MapPin className="w-5 h-5 text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">Search Locations</h3>
          </div>
          <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-md p-2 bg-white">
            {locations.map((loc) => (
              <label key={loc.value} className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedLocations.includes(loc.value)}
                  onChange={async (e) => {
                    let newLocations: string[]
                    if (e.target.checked) {
                      newLocations = [...selectedLocations, loc.value]
                    } else {
                      newLocations = selectedLocations.filter(l => l !== loc.value)
                    }
                    
                    // Update state immediately for responsive UI
                    setSelectedLocations(newLocations)
                    setLastLocationUpdate(Date.now())
                    
                    // Save to backend (even if empty, to clear selection)
                    await saveLocations(newLocations)
                  }}
                  disabled={!status.automation_enabled || updating || isSavingLocations}
                  className="rounded border-gray-300 text-olive-600 focus:ring-olive-500 disabled:opacity-50"
                />
                <span className="text-xs text-gray-700">{loc.label}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Select one or more locations (required for automatic scraper)
          </p>
        </div>

        {/* Email Sending Mode */}
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-xl p-5 border-2 border-gray-200 shadow-md hover:shadow-lg transition-all">
          <div className="flex items-center space-x-2 mb-2">
            <Mail className="w-5 h-5 text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">Email Sending</h3>
          </div>
          <div className="space-y-2">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                name="emailMode"
                value="automatic"
                checked={status.email_trigger_mode === 'automatic'}
                onChange={() => setEmailMode('automatic')}
                disabled={updating}
                className="text-olive-600 focus:ring-olive-500"
              />
              <span className="text-xs text-gray-700">Automatic</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                name="emailMode"
                value="manual"
                checked={status.email_trigger_mode === 'manual'}
                onChange={() => setEmailMode('manual')}
                disabled={updating}
                className="text-olive-600 focus:ring-olive-500"
              />
              <span className="text-xs text-gray-700">Manual</span>
            </label>
          </div>
        </div>

      </div>
    </div>
  )
}
