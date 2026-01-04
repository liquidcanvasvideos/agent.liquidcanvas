'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import SocialProfilesTable from '@/components/SocialProfilesTable'
import SocialDiscovery from '@/components/SocialDiscovery'
import SocialPipeline from '@/components/SocialPipeline'
import SocialOverview from '@/components/SocialOverview'
import SocialDraftsTable from '@/components/SocialDraftsTable'
import SocialSentTable from '@/components/SocialSentTable'
import Sidebar from '@/components/Sidebar'
import SystemStatus from '@/components/SystemStatus'
import { 
  LayoutDashboard, 
  Search, 
  MessageSquare, 
  RefreshCw, 
  Send,
  Users,
  FileText,
  Mail,
  LogOut as LogOutIcon
} from 'lucide-react'
import { listJobs } from '@/lib/api'
import type { Job } from '@/lib/api'

export default function SocialPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<
    'overview' | 'pipeline' | 'discover' | 'profiles' | 'drafts' | 'sent'
  >('overview')
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState(false)

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (!token) {
      router.push('/login')
      return
    }
  }, [router])

  const loadData = async () => {
    try {
      const jobsData = await listJobs(0, 20).catch(err => {
        console.warn('Failed to get jobs:', err.message)
        return []
      })
      const jobsArray = Array.isArray(jobsData) ? jobsData : []
      setJobs(jobsArray)
      setConnectionError(false)
    } catch (error: any) {
      console.error('Error loading data:', error)
      const isConnectionError = 
        error.message?.includes('Failed to fetch') || 
        error.message?.includes('ERR_CONNECTION_REFUSED') ||
        error.message?.includes('NetworkError')
      
      if (isConnectionError) {
        setConnectionError(true)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const refreshData = () => {
    loadData()
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('jobsCompleted'))
    }
  }

  const socialTabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'pipeline', label: 'Pipeline', icon: LayoutDashboard },
    { id: 'discover', label: 'Discover', icon: Search },
    { id: 'profiles', label: 'Profiles', icon: Users },
    { id: 'drafts', label: 'Drafts', icon: FileText },
    { id: 'sent', label: 'Sent', icon: Mail },
  ]

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/20">
        <div className="text-center animate-fade-in">
          <div className="inline-block relative">
            <div className="w-16 h-16 rounded-full border-4 border-liquid-200"></div>
            <div className="absolute top-0 left-0 w-16 h-16 rounded-full border-4 border-t-liquid-500 border-r-purple-500 animate-spin"></div>
          </div>
          <div className="mt-6">
            <h2 className="text-2xl font-bold liquid-gradient-text mb-2">Liquid Canvas</h2>
            <div className="text-lg font-semibold text-gray-700">Loading your studio...</div>
            <div className="text-sm text-gray-500 mt-2">Connecting to backend</div>
          </div>
        </div>
      </div>
    )
  }

  // Wrapper function to handle type compatibility with Sidebar component
  const handleTabChange = (tab: string) => {
    setActiveTab(tab as 'overview' | 'pipeline' | 'discover' | 'profiles' | 'drafts' | 'sent')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-liquid-50 to-white flex">
      {/* Left Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={handleTabChange} tabs={socialTabs} />

      {/* Main Content Area */}
      <div className="flex-1 lg:ml-64 flex flex-col">
        {/* Top Header */}
        <header className="glass border-b border-gray-200/50 sticky top-0 z-30 shadow-sm backdrop-blur-xl">
          <div className="px-3 sm:px-4 py-2 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-olive-700">
                {socialTabs.find(t => t.id === activeTab)?.label || 'Social Outreach'}
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">Liquid Canvas Social Outreach Studio</p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={refreshData}
                className="flex items-center space-x-1 px-2 py-1 glass hover:bg-white/80 text-gray-700 rounded-lg transition-all duration-200 text-xs font-medium hover:shadow-md"
                title="Refresh all data"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Refresh</span>
              </button>
              <button
                onClick={() => {
                  localStorage.removeItem('auth_token')
                  router.push('/login')
                }}
                className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg transition-all duration-200 text-xs font-medium shadow-md hover:bg-olive-700"
              >
                <LogOutIcon className="w-3 h-3" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </header>

        {/* Connection Error Banner */}
        {connectionError && (
          <div className="px-3 sm:px-4 py-2">
            <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-2 shadow-sm">
              <div className="flex items-center">
                <div>
                  <p className="text-xs font-medium text-red-800">
                    Backend not connected
                  </p>
                  <p className="text-xs text-red-600 mt-0.5">
                    Unable to connect to API server. Please ensure the backend is running.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* System Status Bar */}
        <div className="px-3 sm:px-4 py-2">
          <SystemStatus jobs={jobs} loading={loading} />
        </div>

        {/* Main Content */}
        <main className="flex-1 px-3 sm:px-4 py-3 overflow-y-auto">
          <div className="max-w-7xl mx-auto">
            {activeTab === 'overview' && <SocialOverview />}
            {activeTab === 'pipeline' && <SocialPipeline />}
            {activeTab === 'discover' && <SocialDiscovery />}
            {activeTab === 'profiles' && <SocialProfilesTable />}
            {activeTab === 'drafts' && <SocialDraftsTable />}
            {activeTab === 'sent' && <SocialSentTable />}
          </div>
        </main>
      </div>
    </div>
  )
}

