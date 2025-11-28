'use client'

import { BookOpen, ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function GuidePage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => router.push('/')}
          className="flex items-center space-x-2 text-olive-600 hover:text-olive-700 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </button>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="flex items-center space-x-3 mb-6">
            <BookOpen className="w-8 h-8 text-olive-600" />
            <h1 className="text-3xl font-bold text-gray-900">User Guide</h1>
          </div>

          <div className="prose prose-sm max-w-none">
            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Getting Started</h2>
            <p className="text-gray-700 mb-4">
              Welcome to the Art Outreach Automation system. This guide will help you understand how to use the platform to discover websites, extract contact information, and automate your outreach.
            </p>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Overview Tab</h2>
            <p className="text-gray-700 mb-4">
              The Overview tab provides a comprehensive dashboard with:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 space-y-2">
              <li>Statistics cards showing total prospects, emails found, sent emails, and job status</li>
              <li>Automation controls to enable/disable the master switch and automatic scraper</li>
              <li>Discovery controls to manually trigger website discovery</li>
              <li>Recent job status and activity feed</li>
            </ul>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Website Discovery</h2>
            <p className="text-gray-700 mb-4">
              To discover new websites:
            </p>
            <ol className="list-decimal list-inside text-gray-700 mb-4 space-y-2">
              <li>Go to the Overview tab</li>
              <li>Enter keywords related to your niche (e.g., &quot;home decor blog&quot;, &quot;parenting website&quot;)</li>
              <li>Select a location (USA, Canada, UK/London, Germany, France, or Europe)</li>
              <li>Click &quot;Start Discovery&quot; to begin the search</li>
            </ol>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Leads & Emails</h2>
            <p className="text-gray-700 mb-4">
              The Leads tab shows all discovered prospects. The Scraped Emails tab filters to show only prospects with email addresses. You can:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 space-y-2">
              <li>View prospect details including domain, email, status, and score</li>
              <li>Compose emails for prospects with contact information</li>
              <li>Filter and paginate through results</li>
            </ul>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Jobs</h2>
            <p className="text-gray-700 mb-4">
              The Jobs tab shows all background jobs including:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 space-y-2">
              <li>Discovery jobs - finding new websites</li>
              <li>Enrichment jobs - finding email addresses</li>
              <li>Scoring jobs - calculating prospect scores</li>
              <li>Send jobs - sending outreach emails</li>
              <li>Follow-up jobs - sending follow-up emails</li>
            </ul>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Automation</h2>
            <p className="text-gray-700 mb-4">
              Enable automation to run discovery jobs automatically at set intervals. The master switch must be enabled before you can enable automatic scraping.
            </p>

            <h2 className="text-2xl font-bold text-gray-900 mt-8 mb-4">Need Help?</h2>
            <p className="text-gray-700 mb-4">
              If you encounter any issues or have questions, please check the backend logs or contact support.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

