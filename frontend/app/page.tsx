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
import WebsitesTable from '@/components/WebsitesTable'
import SystemStatus from '@/components/SystemStatus'
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
    // Refresh every 10 seconds for real-time updates
    const interval = setInterval(loadData, 10000)
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
      if (jobsData) setJobs(jobsData)
      
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
    <div className="min-h-screen bg-white">
      {/* Modern Header */}
      <header className="bg-white/80 backdrop-blur-lg shadow-sm border-b border-gray-200/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-black">
                Art Outreach Automation
              </h1>
              <p className="text-gray-600 mt-0.5 text-xs">
                Automated outreach system
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => {
                  localStorage.removeItem('auth_token')
                  router.push('/login')
                }}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-olive-600 hover:bg-olive-700 text-white rounded-md transition-colors text-sm"
              >
                <LogOutIcon className="w-3.5 h-3.5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-3">
        <SystemStatus jobs={jobs} loading={loading} />
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
        <div className="bg-white/80 backdrop-blur-md rounded-xl shadow-md border-2 border-gray-200/60 p-2">
          <nav className="flex space-x-2 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`
                    flex items-center space-x-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all whitespace-nowrap
                    ${
                      activeTab === tab.id
                        ? 'bg-gradient-to-r from-olive-600 to-olive-700 text-white shadow-lg transform scale-105'
                        : 'text-gray-700 hover:bg-olive-50 hover:text-olive-700'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {stats ? <StatsCards stats={stats} /> : (
              <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
                <p className="text-gray-500">Stats unavailable. Check backend connection.</p>
              </div>
            )}
            <AutomationControl />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {jobs.length > 0 ? <JobStatusPanel jobs={jobs} /> : (
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
                  <p className="text-gray-500">No jobs found.</p>
                </div>
              )}
            </div>
            <ActivityFeed limit={20} autoRefresh={true} />
          </div>
        )}

        {activeTab === 'websites' && <WebsitesTable />}

        {activeTab === 'leads' && <LeadsTable />}

        {activeTab === 'scraped_emails' && <LeadsTable emailsOnly />}

        {activeTab === 'emails' && <EmailsTable />}

        {activeTab === 'jobs' && jobs.length > 0 && <JobStatusPanel jobs={jobs} expanded />}

        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
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
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
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
  )
}
