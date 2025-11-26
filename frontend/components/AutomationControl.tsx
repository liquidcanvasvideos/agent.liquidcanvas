'use client'

import { useState, useEffect } from 'react'
import { Power, Mail, Settings, Search } from 'lucide-react'

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
  settings: Record<string, any>
}

export default function AutomationControl() {
  const [status, setStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    loadStatus()
    // Refresh every 5 seconds
    const interval = setInterval(loadStatus, 5000)
    return () => clearInterval(interval)
  }, [])

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
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 flex items-center">
          <Power className="w-5 h-5 mr-2" />
          Automation Control
        </h2>
      </div>

      {/* Master Switch */}
      <div className="border-t pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Master Switch</h3>
            <p className="text-sm text-gray-600 mt-1">
              Turn on to start automatic website discovery, scraping, and contact extraction
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={status.automation_enabled}
              onChange={(e) => toggleAutomation(e.target.checked)}
              disabled={updating}
              className="sr-only peer"
            />
            <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-primary-600"></div>
            <span className="ml-3 text-sm font-medium text-gray-700">
              {status.automation_enabled ? 'ON' : 'OFF'}
            </span>
          </label>
        </div>

        {status.automation_enabled && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <div className="w-2 h-2 bg-green-500 rounded-full mt-2 animate-pulse"></div>
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-green-800">Automation Active</p>
                <p className="text-xs text-green-700 mt-1">
                  The system is actively searching, scraping websites, and extracting contacts.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Email Trigger Mode */}
      <div className="border-t pt-6">
        <div className="flex items-center mb-4">
          <Mail className="w-5 h-5 mr-2 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">Email Sending Mode</h3>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Choose how emails are sent to contacts
        </p>

        <div className="space-y-3">
          <label className={`flex items-center p-4 border-2 rounded-lg cursor-pointer transition-all ${
            status.email_trigger_mode === 'automatic'
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-200 hover:border-gray-300'
          }`}>
            <input
              type="radio"
              name="emailMode"
              value="automatic"
              checked={status.email_trigger_mode === 'automatic'}
              onChange={() => setEmailMode('automatic')}
              disabled={updating}
              className="mr-3"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">Automatic</div>
              <div className="text-sm text-gray-600">
                Emails are sent automatically when contacts are found and emails are generated
              </div>
            </div>
          </label>

          <label className={`flex items-center p-4 border-2 rounded-lg cursor-pointer transition-all ${
            status.email_trigger_mode === 'manual'
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-200 hover:border-gray-300'
          }`}>
            <input
              type="radio"
              name="emailMode"
              value="manual"
              checked={status.email_trigger_mode === 'manual'}
              onChange={() => setEmailMode('manual')}
              disabled={updating}
              className="mr-3"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">Manual</div>
              <div className="text-sm text-gray-600">
                Emails are generated but you must manually approve and send them
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Search Interval Control */}
      <div className="border-t pt-6">
        <div className="flex items-center mb-4">
          <Search className="w-5 h-5 mr-2 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">Search Frequency</h3>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          How often to search the internet for new websites (minimum 10 seconds)
        </p>

        <div className="space-y-3">
          <div className="flex items-center space-x-4">
            <input
              type="number"
              min="10"
              step="10"
              value={status.search_interval_seconds || 3600}
              onChange={async (e) => {
                const seconds = parseInt(e.target.value) || 10
                if (seconds >= 10) {
                  setUpdating(true)
                  try {
                    const response = await fetch(
                      `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/search-interval`,
                      {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
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
              }}
              disabled={updating || !status.automation_enabled}
              className="w-32 px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900"
            />
            <span className="text-sm text-gray-700">seconds</span>
            <div className="flex-1">
              <div className="text-xs text-gray-500">
                {status.search_interval_seconds < 60 
                  ? `Searches every ${status.search_interval_seconds} seconds (${Math.round(3600/status.search_interval_seconds)} times per hour)`
                  : status.search_interval_seconds < 3600
                  ? `Searches every ${Math.round(status.search_interval_seconds/60)} minutes`
                  : `Searches every ${Math.round(status.search_interval_seconds/3600)} hours`
                }
              </div>
            </div>
          </div>

          {/* Quick presets */}
          <div className="flex flex-wrap gap-2">
            {[10, 30, 60, 300, 3600, 86400].map((seconds) => (
              <button
                key={seconds}
                onClick={async () => {
                  setUpdating(true)
                  try {
                    const response = await fetch(
                      `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/search-interval`,
                      {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ interval_seconds: seconds })
                      }
                    )
                    if (response.ok) {
                      await loadStatus()
                    }
                  } catch (error: any) {
                    alert(`Error: ${error.message}`)
                  } finally {
                    setUpdating(false)
                  }
                }}
                disabled={updating || !status.automation_enabled}
                className={`px-3 py-1 text-xs rounded-md border ${
                  status.search_interval_seconds === seconds
                    ? 'bg-primary-100 border-primary-500 text-primary-800'
                    : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'
                }`}
              >
                {seconds < 60 
                  ? `${seconds}s`
                  : seconds < 3600
                  ? `${seconds/60}m`
                  : `${seconds/3600}h`
                }
              </button>
            ))}
          </div>

          {status.search_interval_seconds <= 30 && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-xs text-yellow-800">
                <strong>⚠️ Warning:</strong> Very frequent searches (every 10-30 seconds) may hit rate limits 
                and could be flagged by search engines. Use with caution.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Status Info */}
      <div className="border-t pt-4">
        <div className="text-xs text-gray-500 space-y-1">
          <p>
            <strong>Current Status:</strong> Automation is {status.automation_enabled ? 'enabled' : 'disabled'}
          </p>
          <p>
            <strong>Email Mode:</strong> {status.email_trigger_mode === 'automatic' ? 'Automatic sending' : 'Manual approval required'}
          </p>
          <p>
            <strong>Search Interval:</strong> Every {status.search_interval_seconds} seconds
          </p>
        </div>
      </div>
    </div>
  )
}

