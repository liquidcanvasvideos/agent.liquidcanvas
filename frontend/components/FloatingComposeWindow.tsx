'use client'

import { type ReactNode } from 'react'
import { Minus, Square, X } from 'lucide-react'

interface FloatingComposeWindowProps {
  title: string
  subtitle?: string
  minimized: boolean
  maximized: boolean
  onMinimize: () => void
  onMaximize: () => void
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}

export default function FloatingComposeWindow({
  title,
  subtitle,
  minimized,
  maximized,
  onMinimize,
  onMaximize,
  onClose,
  children,
  footer,
}: FloatingComposeWindowProps) {
  const containerClass = maximized
    ? 'fixed inset-4 z-50 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden flex flex-col'
    : 'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white rounded-xl shadow-2xl border border-gray-200 w-[720px] max-w-[calc(100vw-2rem)] h-[78vh] max-h-[calc(100vh-2rem)] overflow-hidden flex flex-col'

  return (
    <div className={containerClass}>
      <div className="flex items-center justify-between px-3 py-2 border-b bg-gradient-to-r from-liquid-50/50 to-purple-50/30">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-gray-900 truncate">{title}</div>
          {subtitle ? <div className="text-[11px] text-gray-600 truncate">{subtitle}</div> : null}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onMinimize}
            className="p-1.5 rounded-md hover:bg-white/80 text-gray-600"
            title={minimized ? 'Restore' : 'Minimize'}
          >
            <Minus className="w-4 h-4" />
          </button>
          <button
            onClick={onMaximize}
            className="p-1.5 rounded-md hover:bg-white/80 text-gray-600"
            title={maximized ? 'Restore' : 'Expand'}
          >
            <Square className="w-4 h-4" />
          </button>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-white/80 text-gray-600" title="Close">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {minimized ? null : (
        <>
          <div className="flex-1 min-h-0">{children}</div>
          {footer ? <div className="border-t px-3 py-2">{footer}</div> : null}
        </>
      )}
    </div>
  )
}
