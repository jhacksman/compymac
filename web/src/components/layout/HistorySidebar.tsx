'use client'

import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Plus, Clock, Play, Trash2, Loader2 } from 'lucide-react'
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

function getStatusColor(status: string): string {
  switch (status) {
    case 'running': return 'bg-green-500'
    case 'paused': return 'bg-yellow-500'
    case 'interrupted': return 'bg-orange-500'
    case 'failed': return 'bg-red-500'
    case 'completed': return 'bg-blue-500'
    default: return 'bg-slate-500'
  }
}

function canResume(status: string): boolean {
  return status === 'paused' || status === 'interrupted'
}

export function HistorySidebar() {
  const { 
    sessions, 
    currentSessionId, 
    setCurrentSession, 
    historySidebarCollapsed, 
    toggleHistorySidebar,
    createSession,
    fetchSessions,
    resumeSession,
    deleteSession,
    isLoadingSessions,
  } = useSessionStore()
  
  const [resumingId, setResumingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  
  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])
  
  const handleResume = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    setResumingId(sessionId)
    await resumeSession(sessionId)
    setResumingId(null)
  }
  
  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    if (!confirm('Delete this session?')) return
    setDeletingId(sessionId)
    await deleteSession(sessionId)
    setDeletingId(null)
  }

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
        {isLoadingSessions ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="px-4 py-8 text-center text-slate-500 text-sm">
            No sessions yet
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => setCurrentSession(session.id)}
              className={cn(
                "w-full px-4 py-3 text-left transition-colors cursor-pointer group",
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
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span className="text-xs text-slate-500">
                        {formatTimeAgo(session.updatedAt)}
                      </span>
                    </div>
                    <span className="text-xs text-slate-600 capitalize">
                      {session.status}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {canResume(session.status) && (
                    <button
                      onClick={(e) => handleResume(e, session.id)}
                      disabled={resumingId === session.id}
                      className="p-1 rounded hover:bg-slate-700 text-green-400 hover:text-green-300 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Resume session"
                    >
                      {resumingId === session.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                  <button
                    onClick={(e) => handleDelete(e, session.id)}
                    disabled={deletingId === session.id}
                    className="p-1 rounded hover:bg-slate-700 text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete session"
                  >
                    {deletingId === session.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <div className={cn(
                    "w-2 h-2 rounded-full ml-1",
                    getStatusColor(session.status)
                  )} />
                </div>
              </div>
            </div>
          ))
        )}
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
