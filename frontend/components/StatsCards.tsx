'use client'

import { Users, Mail, Send, Globe, TrendingUp, ArrowUpRight } from 'lucide-react'
import type { Stats } from '@/lib/api'

interface StatsCardsProps {
  stats: Stats
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Leads Collected',
      value: stats.leads_collected.toLocaleString(),
      icon: Users,
      gradient: 'from-olive-600 to-olive-500',
      bgGradient: 'from-olive-50 to-white',
      change: stats.recent_activity.leads_last_24h,
      changeLabel: 'last 24h',
    },
    {
      title: 'Emails Extracted',
      value: stats.emails_extracted.toLocaleString(),
      icon: Mail,
      gradient: 'from-green-500 to-emerald-500',
      bgGradient: 'from-green-50 to-emerald-50',
      subtitle: `${stats.phones_extracted} phones, ${stats.social_links_extracted} social`,
    },
    {
      title: 'Outreach Sent',
      value: stats.outreach_sent.toLocaleString(),
      icon: Send,
      gradient: 'from-black to-olive-700',
      bgGradient: 'from-gray-50 to-white',
      change: stats.recent_activity.emails_sent_last_24h,
      changeLabel: 'last 24h',
      subtitle: `${stats.outreach_pending} pending, ${stats.outreach_failed} failed`,
    },
    {
      title: 'Websites Scraped',
      value: stats.websites_scraped.toLocaleString(),
      icon: Globe,
      gradient: 'from-orange-500 to-red-500',
      bgGradient: 'from-orange-50 to-red-50',
      change: stats.recent_activity.websites_scraped_last_24h,
      changeLabel: 'last 24h',
      subtitle: `${stats.websites_pending} pending, ${stats.websites_failed} failed`,
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.title}
            className={`bg-gradient-to-br ${card.bgGradient} rounded-xl shadow-lg border border-white/50 p-6 hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className={`p-3 rounded-xl bg-gradient-to-br ${card.gradient} shadow-md`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
              {card.change !== undefined && card.change > 0 && (
                <div className="flex items-center space-x-1 text-green-600 bg-green-50 rounded-full px-2 py-1">
                  <ArrowUpRight className="w-3 h-3" />
                  <span className="text-xs font-semibold">+{card.change}</span>
                </div>
              )}
            </div>
            
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">{card.title}</p>
              <p className={`text-4xl font-bold bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                {card.value}
              </p>
              
              {card.subtitle && (
                <p className="text-xs text-gray-500 mt-2">{card.subtitle}</p>
              )}
              
              {card.change !== undefined && card.changeLabel && (
                <div className="flex items-center mt-3 text-xs text-gray-600">
                  <TrendingUp className="w-3 h-3 mr-1" />
                  <span>{card.changeLabel}</span>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
