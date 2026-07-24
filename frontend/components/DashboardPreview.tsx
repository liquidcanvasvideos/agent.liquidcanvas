'use client'

import Image from 'next/image'
import { 
  Globe, 
  Users, 
  Mail, 
  CheckCircle, 
  Clock, 
  TrendingUp,
  Search,
  Shield,
  FileText,
  Send,
  Activity
} from 'lucide-react'
import { useState } from 'react'

export default function DashboardPreview() {
  const [useScreenshot, setUseScreenshot] = useState(false)
  
  // Try to load screenshot, fallback to mockup if not available
  const hasScreenshot = false // Set to true when screenshot is added
  
  if (hasScreenshot) {
    return (
      <div className="w-full relative rounded-2xl overflow-hidden shadow-2xl border-4 border-white">
        <Image
          src="/dashboard-screenshot.png"
          alt="Liquid Canvas Dashboard Preview"
          width={1200}
          height={800}
          className="w-full h-auto"
          priority
        />
        {/* Overlay gradient for better integration */}
        <div className="absolute inset-0 bg-gradient-to-t from-gray-900/20 to-transparent pointer-events-none"></div>
      </div>
    )
  }
  
  // Fallback to realistic mockup
  return (
    <div className="w-full bg-gray-900 rounded-2xl overflow-hidden shadow-2xl border-4 border-white">
      {/* Dashboard Header */}
      <div className="bg-gray-800 px-6 py-4 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-olive-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">LC</span>
          </div>
          <span className="text-white font-semibold">Liquid Canvas</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
          <span className="text-gray-400 text-sm">System Online</span>
        </div>
      </div>

      {/* Dashboard Content */}
      <div className="bg-gray-900 p-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <Globe className="w-5 h-5 text-blue-400" />
              <span className="text-xs text-gray-400">Total</span>
            </div>
            <div className="text-2xl font-bold text-white">127</div>
            <div className="text-xs text-gray-400 mt-1">Prospects</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <Mail className="w-5 h-5 text-green-400" />
              <span className="text-xs text-gray-400">With Email</span>
            </div>
            <div className="text-2xl font-bold text-white">59</div>
            <div className="text-xs text-gray-400 mt-1">Leads</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle className="w-5 h-5 text-purple-400" />
              <span className="text-xs text-gray-400">Sent</span>
            </div>
            <div className="text-2xl font-bold text-white">42</div>
            <div className="text-xs text-gray-400 mt-1">Emails</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <Clock className="w-5 h-5 text-orange-400" />
              <span className="text-xs text-gray-400">Pending</span>
            </div>
            <div className="text-2xl font-bold text-white">17</div>
            <div className="text-xs text-gray-400 mt-1">Awaiting</div>
          </div>
        </div>

        {/* Pipeline Cards */}
        <div className="grid grid-cols-5 gap-3 mb-6">
          <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/20 rounded-lg p-4 border border-blue-500/30">
            <Search className="w-6 h-6 text-blue-400 mb-2" />
            <div className="text-lg font-bold text-white">Discovery</div>
            <div className="text-2xl font-bold text-blue-400 mt-1">24</div>
          </div>
          <div className="bg-gradient-to-br from-purple-500/20 to-purple-600/20 rounded-lg p-4 border border-purple-500/30">
            <Activity className="w-6 h-6 text-purple-400 mb-2" />
            <div className="text-lg font-bold text-white">Scraping</div>
            <div className="text-2xl font-bold text-purple-400 mt-1">18</div>
          </div>
          <div className="bg-gradient-to-br from-green-500/20 to-green-600/20 rounded-lg p-4 border border-green-500/30">
            <Shield className="w-6 h-6 text-green-400 mb-2" />
            <div className="text-lg font-bold text-white">Verification</div>
            <div className="text-2xl font-bold text-green-400 mt-1">12</div>
          </div>
          <div className="bg-gradient-to-br from-yellow-500/20 to-yellow-600/20 rounded-lg p-4 border border-yellow-500/30">
            <FileText className="w-6 h-6 text-yellow-400 mb-2" />
            <div className="text-lg font-bold text-white">Drafting</div>
            <div className="text-2xl font-bold text-yellow-400 mt-1">8</div>
          </div>
          <div className="bg-gradient-to-br from-olive-500/20 to-olive-600/20 rounded-lg p-4 border border-olive-500/30">
            <Send className="w-6 h-6 text-olive-400 mb-2" />
            <div className="text-lg font-bold text-white">Sending</div>
            <div className="text-2xl font-bold text-olive-400 mt-1">5</div>
          </div>
        </div>

        {/* Table Preview */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
            <h3 className="text-white font-semibold">Recent Leads</h3>
            <div className="flex gap-2">
              <div className="px-3 py-1 bg-olive-600 text-white rounded text-xs font-semibold">
                Filter
              </div>
              <div className="px-3 py-1 bg-gray-700 text-gray-300 rounded text-xs">
                Export
              </div>
            </div>
          </div>
          <div className="divide-y divide-gray-700">
            {[
              { domain: 'artgallery.com', category: 'Art Dealer', email: 'contact@artgallery.com', status: 'Verified' },
              { domain: 'museum.org', category: 'Museum', email: 'info@museum.org', status: 'Pending' },
              { domain: 'gallery.co', category: 'Gallery', email: 'hello@gallery.co', status: 'Verified' },
              { domain: 'artstudio.com', category: 'Studio', email: 'studio@artstudio.com', status: 'Drafted' },
            ].map((row, i) => (
              <div key={i} className="px-4 py-3 flex items-center justify-between hover:bg-gray-750 transition-colors">
                <div className="flex items-center gap-4 flex-1">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-olive-500 to-olive-600 flex items-center justify-center text-white font-bold text-sm">
                    {row.domain[0].toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <div className="text-white font-medium">{row.domain}</div>
                    <div className="text-gray-400 text-sm">{row.category}</div>
                  </div>
                  <div className="text-gray-300 text-sm">{row.email}</div>
                  <div className={`px-2 py-1 rounded text-xs font-semibold ${
                    row.status === 'Verified' ? 'bg-green-500/20 text-green-400' :
                    row.status === 'Pending' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {row.status}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

