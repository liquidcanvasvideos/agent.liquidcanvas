'use client'

import { useState, useEffect } from 'react'
import { Activity, CheckCircle, AlertCircle, Info, Loader2, Clock } from 'lucide-react'

interface ActivityItem {
  id: number
  activity_type: string
  message: string
  status: string
  website_id?: number
  job_id?: number
  metadata?: any
  created_at: string
}

interface ActivityFeedProps {
  limit?: number
  autoRefresh?: boolean
}

export default function ActivityFeed({ limit = 50, autoRefresh = true }: ActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)

  const loadActivities = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // Increased to 10 seconds
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/activity?limit=${limit}`,
        {
          signal: controller.signal
        }
      )
      clearTimeout(timeoutId);
      if (response.ok) {
        const data = await response.json()
        setActivities(data.activities || [])
      } else {
        // Don't clear activities if we have some, just don't update
        if (activities.length === 0) {
          setActivities([])
        }
      }
    } catch (error: any) {
      // Only log if it's not an abort (timeout is expected sometimes)
      if (error.name !== 'AbortError') {
        console.warn('Error loading activities:', error.message)
      }
      // Keep existing activities if we have them
      if (activities.length === 0) {
        setActivities([])
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadActivities()
    if (autoRefresh) {
      const interval = setInterval(loadActivities, 3000)
      return () => clearInterval(interval)
    }
  }, [limit, autoRefresh])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />
      default:
        return <Info className="w-4 h-4 text-olive-600" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-green-50 border-green-200'
      case 'error':
        return 'bg-red-50 border-red-200'
      case 'warning':
        return 'bg-yellow-50 border-yellow-200'
      default:
        return 'bg-blue-50 border-blue-200'
    }
  }

  const formatTime = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)
    
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/50 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-olive-600 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Activity Feed</h2>
        </div>
        {autoRefresh && (
          <div className="flex items-center space-x-2 text-xs text-gray-500">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>Live</span>
          </div>
        )}
      </div>

      {loading && activities.length === 0 ? (
        <div className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-olive-600 mx-auto mb-2" />
          <p className="text-gray-500">Loading activities...</p>
        </div>
      ) : activities.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Activity className="w-12 h-12 mx-auto mb-3 text-gray-400" />
          <p>No activities yet. Start scraping to see activity here.</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className={`p-4 rounded-lg border ${getStatusColor(activity.status)} transition-all hover:shadow-md`}
            >
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 mt-0.5">
                  {getStatusIcon(activity.status)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                      {activity.activity_type}
                    </span>
                    <div className="flex items-center space-x-1 text-xs text-gray-500">
                      <Clock className="w-3 h-3" />
                      <span>{formatTime(activity.created_at)}</span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-900 mt-1">{activity.message}</p>
                  {activity.metadata && Object.keys(activity.metadata).length > 0 && (
                    <div className="mt-2 text-xs text-gray-600">
                      {JSON.stringify(activity.metadata, null, 2)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
