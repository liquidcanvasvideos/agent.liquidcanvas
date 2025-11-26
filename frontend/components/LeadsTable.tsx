'use client'

import { useState, useEffect } from 'react'
import { getLeads, type Lead, type LeadsResponse } from '@/lib/api'
import { Mail, Phone, Globe, Filter } from 'lucide-react'

interface LeadsTableProps {
  /** If true, only show leads that have emails and hide the email filter */
  emailsOnly?: boolean
}

export default function LeadsTable({ emailsOnly = false }: LeadsTableProps) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [limit] = useState(50)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState<string>('')
  const [hasEmail, setHasEmail] = useState<boolean | undefined>(
    emailsOnly ? true : undefined
  )

  const categories = [
    'interior_decor',
    'art_gallery',
    'home_tech',
    'mom_blogs',
    'nft_tech',
    'editorial_media',
    'holiday_family',
  ]

  useEffect(() => {
    loadLeads()
  }, [skip, category, hasEmail])

  const loadLeads = async () => {
    setLoading(true)
    try {
      const data: LeadsResponse = await getLeads(skip, limit, category || undefined, hasEmail)
      setLeads(data.leads)
      setTotal(data.total)
    } catch (error) {
      console.error('Error loading leads:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Filters */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-4">
          <Filter className="w-5 h-5 text-gray-500" />
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value)
              setSkip(0)
            }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </option>
            ))}
          </select>
          {!emailsOnly && (
            <select
              value={hasEmail === undefined ? '' : hasEmail.toString()}
              onChange={(e) => {
                const value = e.target.value
                setHasEmail(value === '' ? undefined : value === 'true')
                setSkip(0)
              }}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All Leads</option>
              <option value="true">Has Email</option>
              <option value="false">No Email</option>
            </select>
          )}
          <div className="ml-auto text-sm text-gray-600">
            Total: {total.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Contact
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Website
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Category
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Info
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Date
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                  No leads found
                </td>
              </tr>
            ) : (
              leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {lead.name || 'Unknown'}
                    </div>
                    {lead.email && (
                      <div className="text-sm text-gray-500 flex items-center mt-1">
                        <Mail className="w-3 h-3 mr-1" />
                        {lead.email}
                      </div>
                    )}
                    {lead.phone_number && (
                      <div className="text-sm text-gray-500 flex items-center mt-1">
                        <Phone className="w-3 h-3 mr-1" />
                        {lead.phone_number}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900">
                      {lead.website_title || 'Unknown'}
                    </div>
                    {lead.website_url && (
                      <a
                        href={lead.website_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary-600 hover:text-primary-800 flex items-center mt-1"
                      >
                        <Globe className="w-3 h-3 mr-1" />
                        {lead.website_url}
                      </a>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                      {lead.website_category?.replace('_', ' ') || 'unknown'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {lead.social_platform && (
                      <div className="text-sm text-gray-500">
                        <span className="font-medium">{lead.social_platform}:</span>{' '}
                        {lead.social_url ? (
                          <a
                            href={lead.social_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary-600 hover:text-primary-800"
                          >
                            View
                          </a>
                        ) : (
                          'N/A'
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(lead.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
        <div className="text-sm text-gray-700">
          Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} leads
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setSkip(Math.max(0, skip - limit))}
            disabled={skip === 0}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={() => setSkip(skip + limit)}
            disabled={skip + limit >= total}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}

