'use client'

import { useState } from 'react'
import { Power, Zap } from 'lucide-react'

export default function AutomationControl() {
  const [masterSwitch, setMasterSwitch] = useState(false)
  const [automaticScraper, setAutomaticScraper] = useState(false)

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4">Automation Control</h2>
      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-3">
            <Power className="w-5 h-5 text-gray-600" />
            <div>
              <p className="font-semibold text-gray-900">Master Switch</p>
              <p className="text-sm text-gray-600">Enable/disable all automation</p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={masterSwitch}
              onChange={(e) => setMasterSwitch(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-olive-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-olive-600"></div>
          </label>
        </div>

        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-3">
            <Zap className="w-5 h-5 text-gray-600" />
            <div>
              <p className="font-semibold text-gray-900">Automatic Scraper</p>
              <p className="text-sm text-gray-600">Run discovery jobs automatically</p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={automaticScraper && masterSwitch}
              disabled={!masterSwitch}
              onChange={(e) => setAutomaticScraper(e.target.checked)}
              className="sr-only peer"
            />
            <div className={`w-11 h-6 rounded-full peer ${
              masterSwitch 
                ? 'bg-gray-200 peer-checked:bg-olive-600' 
                : 'bg-gray-100 cursor-not-allowed'
            }`}></div>
          </label>
        </div>
      </div>
    </div>
  )
}

