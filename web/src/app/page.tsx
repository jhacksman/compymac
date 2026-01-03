'use client'

import { useEffect, useState } from 'react'
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { HistorySidebar } from '@/components/layout/HistorySidebar'
import { ConversationPanel } from '@/components/layout/ConversationPanel'
import { AgentWorkspace } from '@/components/workspace/AgentWorkspace'
import { StatusBar } from '@/components/layout/StatusBar'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSessionStore } from '@/store/session'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const { setTodos, setTerminalOutput, setBrowserState, setBrowserControl, setCurrentSession } = useSessionStore()
  
  // Create session on mount
  useEffect(() => {
    const createSession = async () => {
      try {
        const response = await fetch('http://localhost:8000/sessions', {
          method: 'POST',
        })
        const data = await response.json()
        setSessionId(data.id)
        // Also set in Zustand store so ConversationPanel's WebSocket connects
        setCurrentSession(data.id)
        // Clear initial mock data
        setTodos([])
        setTerminalOutput([])
        setBrowserState('', '', null)
        setBrowserControl('user')
      } catch (error) {
        console.error('Failed to create session:', error)
        // Use a fallback session ID for development
        const fallbackId = 'dev-session-' + Date.now()
        setSessionId(fallbackId)
        setCurrentSession(fallbackId)
      }
    }
    createSession()
  }, [setTodos, setTerminalOutput, setBrowserState, setBrowserControl, setCurrentSession])

  const {
    runCommand,
    browserNavigate,
    setBrowserControlMode,
    createTodo,
    updateTodo,
    // Human intervention handlers
    pauseSession,
    resumeSession,
    approveTodo,
    rejectTodo,
    addTodoNote,
    editTodo,
    deleteTodo,
  } = useWebSocket(sessionId)

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
