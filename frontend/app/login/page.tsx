'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'
import { Globe, Users, ArrowRight, Lock } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedDashboard, setSelectedDashboard] = useState<'website' | 'social' | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDashboard) {
      setError('Please select a dashboard')
      return
    }
    
    setError('')
    setLoading(true)

    try {
      const result = await login(username, password)
      localStorage.setItem('auth_token', result.access_token)
      localStorage.setItem('outreach_type', selectedDashboard)
      
      // Navigate based on selected dashboard
      if (selectedDashboard === 'social') {
        router.push('/socials')
      } else {
        router.push('/dashboard')
      }
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/20 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-72 h-72 bg-olive-400/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
      </div>
      
      <div className="w-full max-w-5xl px-4 relative z-10 animate-fade-in">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-olive-600 to-olive-700 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <span className="text-white text-2xl font-bold">LC</span>
          </div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-olive-700 to-olive-600 bg-clip-text text-transparent mb-2">
            Liquid Canvas
          </h1>
          <p className="text-gray-600">Outreach Studio</p>
        </div>

        {/* Two Login Cards */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Website Outreach Dashboard Card */}
          <div
            onClick={() => setSelectedDashboard('website')}
            className={`glass rounded-2xl shadow-xl border-2 p-8 cursor-pointer transition-all duration-300 ${
              selectedDashboard === 'website'
                ? 'border-olive-500 shadow-2xl scale-105'
                : 'border-gray-200 hover:border-olive-300 hover:shadow-2xl'
            }`}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg">
                <Globe className="w-6 h-6 text-white" />
              </div>
              {selectedDashboard === 'website' && (
                <div className="w-6 h-6 bg-olive-500 rounded-full flex items-center justify-center">
                  <Lock className="w-4 h-4 text-white" />
                </div>
              )}
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Website Outreach Dashboard</h3>
            <p className="text-sm text-gray-600 mb-4">
              Discover websites, scrape emails, and send outreach emails to prospects
            </p>
            <div className="flex items-center text-olive-600 font-semibold text-sm">
              <span>Access Dashboard</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </div>
          </div>

          {/* Social Outreach Dashboard Card */}
          <div
            onClick={() => setSelectedDashboard('social')}
            className={`glass rounded-2xl shadow-xl border-2 p-8 cursor-pointer transition-all duration-300 ${
              selectedDashboard === 'social'
                ? 'border-olive-500 shadow-2xl scale-105'
                : 'border-gray-200 hover:border-olive-300 hover:shadow-2xl'
            }`}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <Users className="w-6 h-6 text-white" />
              </div>
              {selectedDashboard === 'social' && (
                <div className="w-6 h-6 bg-olive-500 rounded-full flex items-center justify-center">
                  <Lock className="w-4 h-4 text-white" />
                </div>
              )}
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Social Outreach Dashboard</h3>
            <p className="text-sm text-gray-600 mb-4">
              Discover social profiles and send messages on LinkedIn, Instagram, TikTok, Facebook
            </p>
            <div className="flex items-center text-olive-600 font-semibold text-sm">
              <span>Access Dashboard</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </div>
          </div>
        </div>

        {/* Login Form - Only shown after selecting a dashboard */}
        {selectedDashboard && (
          <div className="glass rounded-2xl shadow-xl border border-white/20 p-8 animate-slide-up">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Sign In</h2>
              <p className="text-sm text-gray-600">
                Enter your credentials to access the{' '}
                <span className="font-semibold text-olive-700">
                  {selectedDashboard === 'social' ? 'Social Outreach' : 'Website Outreach'} Dashboard
                </span>
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-2">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full px-4 py-3 bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-olive-500 transition-all duration-200"
                  placeholder="Enter your username"
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-gray-700 mb-2">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-olive-500 transition-all duration-200"
                  placeholder="Enter your password"
                />
              </div>
              {error && (
                <div className="p-4 bg-red-50 border-2 border-red-300 rounded-xl text-red-700 text-sm font-medium">
                  {error}
                </div>
              )}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setSelectedDashboard(null)}
                  className="text-sm text-gray-600 hover:text-gray-900 font-medium"
                >
                  ← Back to Dashboard Selection
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-3 bg-gradient-to-r from-olive-600 to-olive-700 text-white rounded-xl hover:shadow-xl hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg"
                >
                  {loading ? (
                    <span className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Signing in...</span>
                    </span>
                  ) : (
                    'Sign In'
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
        
        <div className="mt-6 text-center">
          <p className="text-xs text-gray-500">
            Powered by{' '}
            <a
              href="https://liquidcanvas.art"
              target="_blank"
              rel="noopener noreferrer"
              className="text-olive-600 font-semibold hover:underline"
            >
              liquidcanvas.art
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
