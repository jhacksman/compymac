'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { HistorySidebar } from '@/components/layout/HistorySidebar'
import { ConversationPanel } from '@/components/layout/ConversationPanel'
import { AgentWorkspace } from '@/components/workspace/AgentWorkspace'
import { StatusBar } from '@/components/layout/StatusBar'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSessionStore } from '@/store/session'

export default function SessionPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params.sessionId as string
  
  const { 
    currentSessionId,
    setCurrentSession, 
    setTodos, 
    setTerminalOutput, 
    setBrowserState, 
    setBrowserControl,
    fetchSessions,
  } = useSessionStore()
  
  // Validate UUID format and set session on mount
  useEffect(() => {
    // UUID v4 regex pattern
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    
    if (!sessionId) {
      router.push('/')
      return
    }
    
    // Allow both UUID format and dev-session format for development
    const isValidUuid = uuidRegex.test(sessionId)
    const isDevSession = sessionId.startsWith('dev-session-')
    
    if (!isValidUuid && !isDevSession) {
      console.error('Invalid session ID format:', sessionId)
      router.push('/')
      return
    }
    
    // Set the session ID in the store
    setCurrentSession(sessionId)
    
    // Clear state for fresh session load
    setTodos([])
    setTerminalOutput([])
    setBrowserState('', '', null)
    setBrowserControl('user')
    
    // Fetch sessions list to populate sidebar
    fetchSessions()
  }, [sessionId, router, setCurrentSession, setTodos, setTerminalOutput, setBrowserState, setBrowserControl, fetchSessions])

  const {
    runCommand,
    browserNavigate,
    setBrowserControlMode,
    createTodo,
    updateTodo,
    pauseSession,
    resumeSession,
    approveTodo,
    rejectTodo,
    addTodoNote,
    editTodo,
    deleteTodo,
  } = useWebSocket(currentSessionId)

  return (
    <div className="h-screen flex flex-col bg-slate-950">
      <div className="flex-1 flex min-h-0">
        <HistorySidebar />
        <PanelGroup direction="horizontal" className="flex-1">
          <Panel defaultSize={40} minSize={30}>
            <ConversationPanel />
          </Panel>
          <PanelResizeHandle className="w-1 bg-slate-800 hover:bg-blue-500 transition-colors cursor-col-resize" />
          <Panel defaultSize={60} minSize={40}>
            <AgentWorkspace 
              onRunCommand={runCommand}
              onBrowserNavigate={browserNavigate}
              onSetBrowserControl={setBrowserControlMode}
              onCreateTodo={createTodo}
              onUpdateTodo={updateTodo}
              onPauseSession={pauseSession}
              onResumeSession={resumeSession}
              onApproveTodo={approveTodo}
              onRejectTodo={rejectTodo}
              onAddTodoNote={addTodoNote}
              onEditTodo={editTodo}
              onDeleteTodo={deleteTodo}
            />
          </Panel>
        </PanelGroup>
      </div>
      <StatusBar />
    </div>
  )
}
