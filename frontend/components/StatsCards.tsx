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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.title}
            className={`${card.bgColor} rounded-xl shadow-md border-2 border-gray-200/60 p-4 hover:shadow-lg transition-shadow`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-1">{card.title}</p>
                <p className={`text-2xl font-bold ${card.textColor}`}>{card.value}</p>
              </div>
              <div className={`${card.color} p-3 rounded-lg`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

