'use client'

import { useEffect, useState } from 'react'
import { Activity as ActivityIcon } from 'lucide-react'

interface Activity {
  id: string
  type: string
  message: string
  timestamp: string
}

interface ActivityFeedProps {
  limit?: number
  autoRefresh?: boolean
}

export default function ActivityFeed({ limit = 20, autoRefresh = false }: ActivityFeedProps) {
  const [activities, setActivities] = useState<Activity[]>([])

  useEffect(() => {
    // For now, generate mock activities from jobs
    // In production, this should fetch from a real activity endpoint
    const loadActivities = () => {
      // Mock activities - replace with real API call
      const mockActivities: Activity[] = [
        {
          id: '1',
          type: 'info',
          message: 'System initialized',
          timestamp: new Date().toISOString(),
        },
      ]
      setActivities(mockActivities)
    }

    loadActivities()
    if (autoRefresh) {
      const interval = setInterval(loadActivities, 10000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center space-x-2 mb-4">
        <ActivityIcon className="w-5 h-5 text-olive-600" />
        <h2 className="text-lg font-bold text-gray-900">Activity Feed</h2>
      </div>
      {activities.length === 0 ? (
        <p className="text-gray-500 text-sm">No recent activity</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="w-2 h-2 bg-olive-600 rounded-full mt-2"></div>
              <div className="flex-1">
                <p className="text-sm text-gray-900">{activity.message}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(activity.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

