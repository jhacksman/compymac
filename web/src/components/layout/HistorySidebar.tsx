'use client'

import { ChevronLeft, ChevronRight, Plus, Clock } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function HistorySidebar() {
  const { 
    sessions, 
    currentSessionId, 
    setCurrentSession, 
    historySidebarCollapsed, 
    toggleHistorySidebar,
    createSession 
  } = useSessionStore()

  if (historySidebarCollapsed) {
    return (
      <div className="w-12 bg-slate-900 border-r border-slate-700 flex flex-col items-center py-4">
        <button
          onClick={toggleHistorySidebar}
          className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
        <div className="mt-4 flex flex-col gap-2">
          {sessions.slice(0, 5).map((session) => (
            <button
              key={session.id}
              onClick={() => setCurrentSession(session.id)}
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium transition-colors",
                currentSessionId === session.id
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700"
              )}
            >
              {session.title.charAt(0)}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-700 flex flex-col">
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">C</span>
          </div>
          <span className="text-white font-semibold">History</span>
        </div>
        <button
          onClick={toggleHistorySidebar}
          className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => setCurrentSession(session.id)}
            className={cn(
              "w-full px-4 py-3 text-left transition-colors",
              currentSessionId === session.id
                ? "bg-slate-800 border-l-2 border-blue-500"
                : "hover:bg-slate-800/50"
            )}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-sm font-medium truncate",
                  currentSessionId === session.id ? "text-white" : "text-slate-300"
                )}>
                  {session.title}
                </p>
                <div className="flex items-center gap-1 mt-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span className="text-xs text-slate-500">
                    {formatTimeAgo(session.updatedAt)}
                  </span>
                </div>
              </div>
              <div className={cn(
                "w-2 h-2 rounded-full mt-1.5",
                session.status === 'running' ? "bg-green-500" :
                session.status === 'paused' ? "bg-yellow-500" :
                session.status === 'failed' ? "bg-red-500" : "bg-slate-500"
              )} />
            </div>
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-slate-700">
        <button
          onClick={() => createSession('New Session')}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">New Session</span>
        </button>
      </div>
    </div>
  )
}
