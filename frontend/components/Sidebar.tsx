'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { 
  LayoutDashboard, 
  Globe, 
  Users, 
  Mail, 
  Settings, 
  Activity,
  AtSign,
  BookOpen,
  Menu,
  X
} from 'lucide-react'
import { LucideIcon } from 'lucide-react'

interface Tab {
  id: string
  label: string
  icon: LucideIcon
  route?: string
}

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  tabs: Tab[]
}

export default function Sidebar({ activeTab, onTabChange, tabs }: SidebarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const router = useRouter()

  return (
    <>
      {/* Mobile Menu Button */}
      <button
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-md shadow-md border border-gray-200"
      >
        {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed left-0 top-0 h-full w-64 glass border-r border-gray-200/50 shadow-xl z-40 flex flex-col
        transform transition-transform duration-300 ease-in-out
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
      {/* Logo/Header Section */}
      <div className="p-3 border-b border-gray-200/50 bg-gradient-to-br from-white to-gray-50">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-olive-600 flex items-center justify-center shadow-lg">
            <span className="text-white text-sm font-bold">LC</span>
          </div>
          <div>
            <h1 className="text-sm font-bold text-olive-700">
              Liquid Canvas
            </h1>
            <p className="text-gray-500 text-xs mt-0.5 font-medium">
              Outreach Studio
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        <div className="space-y-1">
          {Array.isArray(tabs) && tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => {
                  // If tab has a route, navigate to it
                  if (tab.route) {
                    router.push(tab.route)
                  } else {
                    // Otherwise, use the normal tab change
                    onTabChange(tab.id)
                  }
                  setMobileMenuOpen(false) // Close mobile menu when tab is selected
                }}
                className={`
                  w-full flex items-center space-x-2 px-2 py-2 rounded-lg font-medium text-xs transition-all duration-200
                  ${
                    isActive
                      ? 'bg-olive-600 text-white shadow-md hover-glow'
                      : 'text-gray-700 hover:bg-olive-50 hover:text-olive-700 hover:shadow-sm'
                  }
                `}
              >
                <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-white' : 'text-gray-500 group-hover:text-olive-600'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </nav>

      {/* Footer Section */}
      <div className="p-2 border-t border-gray-200/50 bg-gradient-to-t from-gray-50/50 to-transparent">
        <div className="text-xs text-center">
          <p className="text-gray-600 font-medium">Powered by</p>
          <a 
            href="https://liquidcanvas.art" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-olive-700 font-bold text-xs mt-1 inline-block hover:scale-105 transition-transform"
          >
            liquidcanvas.art
          </a>
        </div>
      </div>
    </aside>
    </>
  )
}

