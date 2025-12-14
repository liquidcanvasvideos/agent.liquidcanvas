'use client'
// Version: 3.1 - Discovery feature removed - FORCE REDEPLOY

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import StatsCards from '@/components/StatsCards'
import LeadsTable from '@/components/LeadsTable'
import EmailsTable from '@/components/EmailsTable'
import JobStatusPanel from '@/components/JobStatusPanel'
import ActivityFeed from '@/components/ActivityFeed'
import AutomationControl from '@/components/AutomationControl'
import ManualScrape from '@/components/ManualScrape'
import WebsitesTable from '@/components/WebsitesTable'
import SystemStatus from '@/components/SystemStatus'
import Sidebar from '@/components/Sidebar'
import { getStats, listJobs } from '@/lib/api'
import type { Stats, Job } from '@/lib/api'
import { 
  LayoutDashboard, 
  Globe, 
  Users, 
  Mail, 
  Settings, 
  Activity,
  AtSign,
  LogOut as LogOutIcon,
  BookOpen
} from 'lucide-react'

export default function Dashboard() {
  const router = useRouter()
  const [stats, setStats] = useState<Stats | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState(false)
  const [activeTab, setActiveTab] = useState<
    'overview' | 'leads' | 'scraped_emails' | 'emails' | 'jobs' | 'websites' | 'settings' | 'guide'
  >('overview')

  useEffect(() => {
    // Check if user is authenticated
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (!token) {
      router.push('/login')
      return
    }

    loadData()
    // Refresh every 30 seconds (debounced to prevent loops) - increased from 10s
    const interval = setInterval(() => {
      loadData()
    }, 30000)
    return () => clearInterval(interval)
  }, [router])

  const loadData = async () => {
    try {
      const [statsData, jobsData] = await Promise.all([
        getStats().catch(err => {
          console.warn('Failed to get stats:', err.message)
          return null
        }),
        listJobs(0, 20).catch(err => {
          console.warn('Failed to get jobs:', err.message)
          return []
        }),
      ])
      
      if (statsData) setStats(statsData)
      // Ensure jobsData is always an array
      if (jobsData) {
        setJobs(Array.isArray(jobsData) ? jobsData : [])
      } else {
        setJobs([])
      }
      
      const backendResponding = statsData !== null || jobsData.length > 0
      setConnectionError(!backendResponding)
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

  const refreshData = () => {
    loadData()
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'websites', label: 'Websites', icon: Globe },
    { id: 'leads', label: 'Leads', icon: Users },
    { id: 'scraped_emails', label: 'Scraped Emails', icon: AtSign },
    { id: 'emails', label: 'Outreach Emails', icon: Mail },
    { id: 'jobs', label: 'Jobs', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
    { id: 'guide', label: 'Guide', icon: BookOpen },
  ]

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-olive-600 border-t-transparent mb-4"></div>
          <div className="text-xl font-semibold text-gray-900">Loading dashboard...</div>
          <div className="text-sm text-gray-600 mt-2">Connecting to backend...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} tabs={tabs} />

      {/* Main Content Area */}
      <div className="flex-1 lg:ml-64 flex flex-col">
        {/* Top Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
          <div className="px-4 sm:px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {tabs.find(t => t.id === activeTab)?.label || 'Dashboard'}
              </h2>
            </div>
              <button
                onClick={() => {
                  localStorage.removeItem('auth_token')
                  router.push('/login')
                }}
              className="flex items-center space-x-2 px-4 py-2 bg-olive-600 hover:bg-olive-700 text-white rounded-md transition-colors text-sm"
              >
              <LogOutIcon className="w-4 h-4" />
                <span>Logout</span>
              </button>
        </div>
      </header>

      {/* Connection Error Banner */}
      {connectionError && (
          <div className="px-4 sm:px-6 py-4">
          <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-4 shadow-sm">
            <div className="flex items-center">
              <div>
                <p className="text-sm font-medium text-red-800">
                  Backend not connected
                </p>
                <p className="text-xs text-red-600 mt-1">
                  Unable to connect to API server. Please ensure the backend is running.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* System Status Bar */}
        <div className="px-4 sm:px-6 py-3">
        <SystemStatus jobs={jobs} loading={loading} />
      </div>

      {/* Main Content */}
        <main className="flex-1 px-4 sm:px-6 py-4 overflow-y-auto">
        {activeTab === 'overview' && (
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Stats Cards - Full Width */}
            <div className="lg:col-span-12">
              {stats ? <StatsCards stats={stats} /> : (
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
                  <p className="text-gray-500">Stats unavailable. Check backend connection.</p>
                </div>
              )}
            </div>

            {/* Left Column - Automation & Manual Scrape */}
            <div className="lg:col-span-7 space-y-6">
              <AutomationControl />
              <ManualScrape />
            </div>

            {/* Right Column - Jobs & Activity */}
            <div className="lg:col-span-5 space-y-6">
              {jobs.length > 0 ? (
                <JobStatusPanel jobs={jobs} />
              ) : (
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
                  <p className="text-gray-500">No jobs found.</p>
                </div>
              )}
              <ActivityFeed limit={15} autoRefresh={true} />
            </div>
          </div>
        )}

        {activeTab === 'websites' && (
          <div className="max-w-7xl mx-auto">
            <WebsitesTable />
          </div>
        )}

        {activeTab === 'leads' && (
          <div className="max-w-7xl mx-auto">
            <LeadsTable />
          </div>
        )}

        {activeTab === 'scraped_emails' && (
          <div className="max-w-7xl mx-auto">
            <LeadsTable emailsOnly />
          </div>
        )}

        {activeTab === 'emails' && (
          <div className="max-w-7xl mx-auto">
            <EmailsTable />
          </div>
        )}

        {activeTab === 'jobs' && jobs.length > 0 && (
          <div className="max-w-7xl mx-auto">
            <JobStatusPanel jobs={jobs} expanded />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center py-8">
              <Settings className="w-12 h-12 text-olive-600 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-gray-900 mb-2">System Settings</h2>
              <p className="text-gray-600 mb-6">Configure and test all API integrations</p>
              <Link
                href="/settings"
                className="inline-flex items-center px-6 py-3 bg-olive-600 text-white rounded-md hover:bg-olive-700 transition-colors font-semibold"
              >
                <Settings className="w-5 h-5 mr-2" />
                Open Settings Page
              </Link>
            </div>
          </div>
        )}

        {activeTab === 'guide' && (
          <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">User Guide</h2>
              <p className="text-gray-600">Complete documentation on how to use the Art Outreach Automation</p>
            </div>
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 mb-4">
                For the complete user guide, please visit the dedicated guide page.
              </p>
              <a
                href="/guide"
                className="inline-flex items-center px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 transition-colors"
              >
                <BookOpen className="w-4 h-4 mr-2" />
                Open Full Guide
              </a>
            </div>
          </div>
        )}
      </main>
      </div>
    </div>
  )
}
