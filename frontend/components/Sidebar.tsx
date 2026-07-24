'use client'

import { useState, useEffect } from 'react'
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
      <div className="p-4 border-b border-gray-200/50 bg-gradient-to-br from-white to-olive-50/30">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-olive-600 flex items-center justify-center shadow-lg hover-glow transition-all">
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
          {/* CRITICAL: Ensure Drafts tab is always present - add it if missing */}
          {!tabs.some(t => t.id === 'drafts') && (
            <button
              onClick={() => {
                onTabChange('drafts')
                setMobileMenuOpen(false)
              }}
              className={`
                w-full flex items-center space-x-2 px-3 py-2.5 rounded-lg font-medium text-xs transition-all duration-200
                ${activeTab === 'drafts'
                  ? 'bg-olive-600 text-white shadow-md hover-glow'
                  : 'text-gray-700 hover:bg-olive-50 hover:text-olive-700 hover:shadow-sm'
                }
              `}
            >
              <span className="w-4 h-4 flex items-center justify-center">📄</span>
              <span>Drafts</span>
            </button>
          )}
          {Array.isArray(tabs) && tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            
            // Debug logging for Drafts tab
            if (tab.id === 'drafts') {
              console.log('🔍 Rendering Drafts tab:', { 
                id: tab.id, 
                label: tab.label, 
                icon: typeof Icon !== 'undefined' ? '✅' : '❌',
                iconType: typeof Icon,
                isActive,
                tabsLength: tabs.length
              })
            }
            
            // CRITICAL: Never skip Drafts tab - always render it even if icon is missing
            if (!Icon && tab.id !== 'drafts') {
              console.error(`❌ Icon missing for tab: ${tab.id}`)
              return null
            }
            
            // For Drafts tab, use fallback if icon is missing
            if (!Icon && tab.id === 'drafts') {
              console.warn('⚠️ FileText icon missing for Drafts tab, using fallback')
            }
            
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
                  w-full flex items-center space-x-2 px-3 py-2.5 rounded-lg font-medium text-xs transition-all duration-200
                  ${
                    isActive
                      ? 'bg-olive-600 text-white shadow-md hover-glow'
                      : 'text-gray-700 hover:bg-olive-50 hover:text-olive-700 hover:shadow-sm'
                  }
                `}
              >
                {Icon ? (
                  <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-white' : 'text-gray-500 group-hover:text-olive-600'}`} />
                ) : (
                  <span className={`w-4 h-4 flex items-center justify-center ${isActive ? 'text-white' : 'text-gray-500'}`}>📄</span>
                )}
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

