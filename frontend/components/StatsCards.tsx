'use client'

import { Users, Mail, CheckCircle, Clock, TrendingUp, AlertCircle } from 'lucide-react'
import type { Stats } from '@/lib/api'

interface StatsCardsProps {
  stats: Stats
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Total Prospects',
      value: stats.total_prospects,
      icon: Users,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
      textColor: 'text-blue-700',
    },
    {
      title: 'With Email',
      value: stats.prospects_with_email,
      icon: Mail,
      color: 'bg-green-500',
      bgColor: 'bg-green-50',
      textColor: 'text-green-700',
    },
    {
      title: 'Sent',
      value: stats.prospects_sent,
      icon: CheckCircle,
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
      textColor: 'text-purple-700',
    },
    {
      title: 'Pending',
      value: stats.prospects_pending,
      icon: Clock,
      color: 'bg-orange-500',
      bgColor: 'bg-orange-50',
      textColor: 'text-orange-700',
    },
    {
      title: 'Replied',
      value: stats.prospects_replied,
      icon: TrendingUp,
      color: 'bg-olive-600',
      bgColor: 'bg-olive-50',
      textColor: 'text-olive-700',
    },
    {
      title: 'Jobs Running',
      value: stats.jobs_running,
      icon: AlertCircle,
      color: 'bg-yellow-500',
      bgColor: 'bg-yellow-50',
      textColor: 'text-yellow-700',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {cards.map((card, index) => {
        const Icon = card.icon
        return (
          <div
            key={card.title}
            className="glass rounded-xl shadow-lg border border-white/20 p-3 hover:shadow-xl hover:scale-102 transition-all duration-300 animate-slide-up"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-600 mb-1">{card.title}</p>
                <p className={`text-lg font-bold text-olive-700`}>{card.value}</p>
              </div>
              <div className={`p-2 rounded-lg shadow-md bg-olive-600`}>
                <Icon className="w-4 h-4 text-white" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

