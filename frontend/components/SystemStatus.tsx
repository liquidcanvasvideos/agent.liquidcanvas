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
    <div className="glass rounded-xl shadow-lg border border-white/20 p-2 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <div className="relative">
              <div className="w-3 h-3 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full animate-pulse shadow-lg shadow-green-500/50"></div>
              <div className="absolute inset-0 w-3 h-3 bg-green-400 rounded-full animate-ping opacity-75"></div>
            </div>
            <span className="text-sm font-bold text-gray-700">System Online</span>
          </div>
          {runningJobs.length > 0 && (
            <div className="flex items-center space-x-2 px-3 py-1 bg-gradient-to-r from-yellow-50 to-amber-50 rounded-lg border border-yellow-200">
              <Clock className="w-4 h-4 text-yellow-600 animate-spin" />
              <span className="text-sm font-semibold text-yellow-700">{runningJobs.length} running</span>
            </div>
          )}
          {completedJobs.length > 0 && (
            <div className="flex items-center space-x-2 px-3 py-1 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm font-semibold text-green-700">{completedJobs.length} completed</span>
            </div>
          )}
          {failedJobs.length > 0 && (
            <div className="flex items-center space-x-2 px-3 py-1 bg-gradient-to-r from-red-50 to-pink-50 rounded-lg border border-red-200">
              <XCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm font-semibold text-red-700">{failedJobs.length} failed</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

