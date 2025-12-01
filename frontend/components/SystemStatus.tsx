'use client'

import { CheckCircle, XCircle, Clock } from 'lucide-react'
import type { Job } from '@/lib/api'

interface SystemStatusProps {
  jobs: Job[]
  loading: boolean
}

export default function SystemStatus({ jobs, loading }: SystemStatusProps) {
  // Safe array filtering with defensive checks
  // Prevents crashes if jobs is undefined or not an array
  const runningJobs = Array.isArray(jobs) 
    ? jobs.filter(j => j && typeof j === 'object' && j.status === 'running')
    : []
  const completedJobs = Array.isArray(jobs)
    ? jobs.filter(j => j && typeof j === 'object' && j.status === 'completed')
    : []
  const failedJobs = Array.isArray(jobs)
    ? jobs.filter(j => j && typeof j === 'object' && j.status === 'failed')
    : []

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow-md border-2 border-gray-200/60 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-gray-700">System Online</span>
          </div>
          {runningJobs.length > 0 && (
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-yellow-600" />
              <span className="text-sm text-gray-600">{runningJobs.length} running</span>
            </div>
          )}
          {completedJobs.length > 0 && (
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm text-gray-600">{completedJobs.length} completed</span>
            </div>
          )}
          {failedJobs.length > 0 && (
            <div className="flex items-center space-x-2">
              <XCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-gray-600">{failedJobs.length} failed</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

