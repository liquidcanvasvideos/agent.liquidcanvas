'use client'

import { useState } from 'react'
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
}

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  tabs: Tab[]
}

export default function Sidebar({ activeTab, onTabChange, tabs }: SidebarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
        fixed left-0 top-0 h-full w-64 bg-white border-r border-gray-200 shadow-lg z-40 flex flex-col
        transform transition-transform duration-300 ease-in-out
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
      {/* Logo/Header Section */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-xl font-bold text-black">
          Art Outreach
        </h1>
        <p className="text-gray-600 text-xs mt-1">
          Automation System
        </p>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        <div className="space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => {
                  onTabChange(tab.id)
                  setMobileMenuOpen(false) // Close mobile menu when tab is selected
                }}
                className={`
                  w-full flex items-center space-x-3 px-4 py-3 rounded-lg font-medium text-sm transition-all
                  ${
                    isActive
                      ? 'bg-gradient-to-r from-olive-600 to-olive-700 text-white shadow-md'
                      : 'text-gray-700 hover:bg-olive-50 hover:text-olive-700'
                  }
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-gray-500'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </nav>

      {/* Footer Section */}
      <div className="p-4 border-t border-gray-200">
        <div className="text-xs text-gray-500 text-center">
          <p>Version 2.0</p>
          <p className="mt-1">Snov.io Integration</p>
        </div>
      </div>
    </aside>
  )
}

