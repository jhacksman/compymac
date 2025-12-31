'use client'

import { Globe, RefreshCw, ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

interface BrowserPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
}

export function BrowserPanel({ isMaximized, onMaximize }: BrowserPanelProps) {
  const { browserUrl, browserTitle, browserControl } = useSessionStore()

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium text-white">Browser</span>
        </div>
        <div className="flex items-center gap-1">
          {browserControl === 'agent' && (
            <span className="text-xs text-green-400 mr-2">AI Navigating</span>
          )}
          <button 
            onClick={onMaximize}
            className="p-1 text-slate-400 hover:text-white transition-colors"
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {isMaximized && (
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-850 border-b border-slate-700">
          <button className="p-1 text-slate-400 hover:text-white">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button className="p-1 text-slate-400 hover:text-white">
            <ChevronRight className="w-4 h-4" />
          </button>
          <button className="p-1 text-slate-400 hover:text-white">
            <RefreshCw className="w-4 h-4" />
          </button>
          <div className="flex-1 bg-slate-700 rounded px-3 py-1">
            <span className="text-xs text-slate-300 truncate">{browserUrl}</span>
          </div>
        </div>
      )}

      <div className="flex-1 p-3 overflow-hidden">
        <div className="w-full h-full bg-white rounded-lg overflow-hidden">
          <div className="h-8 bg-slate-100 border-b flex items-center px-3 gap-2">
            <div className="flex gap-1">
              <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
              <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
            </div>
            {!isMaximized && (
              <span className="text-xs text-slate-500 truncate ml-2">{browserUrl}</span>
            )}
          </div>
          <div className="p-4 bg-white">
            <div className="text-xs text-slate-400 mb-2">Bloomberg</div>
            <h3 className="text-lg font-bold text-slate-900 mb-4">{browserTitle}</h3>
            <div className="space-y-3">
              <div className="h-32 bg-gradient-to-r from-blue-100 to-purple-100 rounded-lg flex items-end p-4">
                <div className="flex items-end gap-2 h-full w-full">
                  {[40, 60, 45, 80, 55, 70, 90, 65, 75, 85].map((h, i) => (
                    <div
                      key={i}
                      className="flex-1 bg-gradient-to-t from-blue-500 to-purple-500 rounded-t"
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </div>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Top 10 DeFi Trends for 2025: showcasing notable patterns around stablecoins and yields, each resonating the vibrant crypto landscape...
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
