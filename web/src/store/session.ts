import { create } from 'zustand'
import type { Citation, LibraryJumpRequest } from '@/types/citation'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  citations?: Citation[]
}

export interface ToolCall {
  id: string
  name: string
  status: 'running' | 'completed' | 'failed'
  arguments?: Record<string, unknown>
  result?: string
}

export interface Session {
  id: string
  title: string
  status: 'running' | 'paused' | 'completed' | 'failed' | 'interrupted'
  createdAt: Date
  updatedAt: Date
  taskDescription?: string
  stepCount?: number
  toolCallsCount?: number
  errorMessage?: string
}

export interface Todo {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'claimed' | 'verified'
}

export type WorkspacePanel = 'browser' | 'cli' | 'todos' | 'knowledge'
export type AutonomyLevel = 'high' | 'medium' | 'low'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface SessionState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
  isLoadingSessions: boolean
  
  browserUrl: string
  browserTitle: string
  browserScreenshotUrl: string | null
  browserControl: 'user' | 'agent'
  
  terminalOutput: string[]
  terminalControl: 'user' | 'agent'
  
  todos: Todo[]
  
  // Phase 5: Citation Linking
  pendingCitationJump: LibraryJumpRequest | null
  
  maximizedPanel: WorkspacePanel | null
  historySidebarCollapsed: boolean
  autonomyLevel: AutonomyLevel
  agentGoal: string
  agentStatus: 'active' | 'paused' | 'idle' | 'planning' | 'executing' | 'working' | 'error'
  
  setCurrentSession: (sessionId: string | null) => void
  addMessage: (message: Message) => void
  setStreamingContent: (content: string) => void
  setIsStreaming: (isStreaming: boolean) => void
  setBrowserState: (url: string, title: string, screenshotUrl: string | null) => void
  setBrowserControl: (control: 'user' | 'agent') => void
  addTerminalOutput: (output: string) => void
  setTerminalOutput: (output: string[]) => void
  setTerminalControl: (control: 'user' | 'agent') => void
  setTodos: (todos: Todo[]) => void
  setMaximizedPanel: (panel: WorkspacePanel | null) => void
  toggleHistorySidebar: () => void
  setAutonomyLevel: (level: AutonomyLevel) => void
  setAgentGoal: (goal: string) => void
  setAgentStatus: (status: 'active' | 'paused' | 'idle' | 'planning' | 'executing' | 'working' | 'error') => void
  createSession: (title: string) => void
  
  // Gap 4: Session Continuity - new methods
  fetchSessions: () => Promise<void>
  resumeSession: (sessionId: string) => Promise<boolean>
  saveSession: (sessionId: string, taskDescription?: string) => Promise<boolean>
  deleteSession: (sessionId: string) => Promise<boolean>
  setSessions: (sessions: Session[]) => void
  
  // Phase 5: Citation Linking
  openCitation: (citation: Citation) => void
  clearPendingCitationJump: () => void
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  streamingContent: '',
  isStreaming: false,
  isLoadingSessions: false,
  
  browserUrl: '',
  browserTitle: '',
  browserScreenshotUrl: null,
  browserControl: 'agent',
  
  terminalOutput: [],
  terminalControl: 'agent',
  
  todos: [],
  
  // Phase 5: Citation Linking
  pendingCitationJump: null,
  
  maximizedPanel: null,
  historySidebarCollapsed: false,
  autonomyLevel: 'high',
  agentGoal: '',
  agentStatus: 'idle',
  
  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setStreamingContent: (content) => set({ streamingContent: content }),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setBrowserState: (url, title, screenshotUrl) => set({ browserUrl: url, browserTitle: title, browserScreenshotUrl: screenshotUrl }),
  setBrowserControl: (control) => set({ browserControl: control }),
  addTerminalOutput: (output) => set((state) => ({ terminalOutput: [...state.terminalOutput, output] })),
  setTerminalOutput: (output) => set({ terminalOutput: output }),
  setTerminalControl: (control) => set({ terminalControl: control }),
  setTodos: (todos) => set({ todos }),
  setMaximizedPanel: (panel) => set({ maximizedPanel: panel }),
  toggleHistorySidebar: () => set((state) => ({ historySidebarCollapsed: !state.historySidebarCollapsed })),
  setAutonomyLevel: (level) => set({ autonomyLevel: level }),
  setAgentGoal: (goal) => set({ agentGoal: goal }),
  setAgentStatus: (status) => set({ agentStatus: status }),
  
  createSession: (title) => set((state) => ({
    sessions: [
      { id: Date.now().toString(), title, status: 'running', createdAt: new Date(), updatedAt: new Date() },
      ...state.sessions,
    ],
    currentSessionId: Date.now().toString(),
  })),
  
  setSessions: (sessions) => set({ sessions }),
  
  // Gap 4: Session Continuity - Fetch sessions from API
  fetchSessions: async () => {
    set({ isLoadingSessions: true })
    try {
      const response = await fetch(`${API_BASE}/api/sessions`)
      if (!response.ok) {
        console.error('Failed to fetch sessions:', response.statusText)
        set({ isLoadingSessions: false })
        return
      }
      const data = await response.json()
      const sessions: Session[] = data.sessions.map((s: {
        id: string
        title: string
        status: string
        created_at: string
        updated_at: string
        task_description?: string
        step_count?: number
        tool_calls_count?: number
        error_message?: string
      }) => ({
        id: s.id,
        title: s.title || s.task_description || `Session ${s.id.slice(0, 8)}`,
        status: s.status as Session['status'],
        createdAt: new Date(s.created_at),
        updatedAt: new Date(s.updated_at),
        taskDescription: s.task_description,
        stepCount: s.step_count,
        toolCallsCount: s.tool_calls_count,
        errorMessage: s.error_message,
      }))
      set({ sessions, isLoadingSessions: false })
    } catch (error) {
      console.error('Error fetching sessions:', error)
      set({ isLoadingSessions: false })
    }
  },
  
  // Gap 4: Session Continuity - Resume a paused/interrupted session
  resumeSession: async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/resume`, {
        method: 'POST',
      })
      if (!response.ok) {
        console.error('Failed to resume session:', response.statusText)
        return false
      }
      const data = await response.json()
      if (data.error) {
        console.error('Resume error:', data.error)
        return false
      }
      
      // Update the session in the list
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, status: 'running' as const } : s
        ),
        currentSessionId: sessionId,
      }))
      
      // Refresh the session list to get updated state
      await get().fetchSessions()
      return true
    } catch (error) {
      console.error('Error resuming session:', error)
      return false
    }
  },
  
  // Gap 4: Session Continuity - Save current session state
  saveSession: async (sessionId: string, taskDescription?: string) => {
    try {
      const url = new URL(`${API_BASE}/api/sessions/${sessionId}/save`)
      if (taskDescription) {
        url.searchParams.set('task_description', taskDescription)
      }
      const response = await fetch(url.toString(), {
        method: 'POST',
      })
      if (!response.ok) {
        console.error('Failed to save session:', response.statusText)
        return false
      }
      const data = await response.json()
      if (data.error) {
        console.error('Save error:', data.error)
        return false
      }
      
      // Refresh the session list
      await get().fetchSessions()
      return true
    } catch (error) {
      console.error('Error saving session:', error)
      return false
    }
  },
  
  // Gap 4: Session Continuity - Delete a session
  deleteSession: async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        console.error('Failed to delete session:', response.statusText)
        return false
      }
      
      // Remove from local state
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId,
      }))
      return true
    } catch (error) {
      console.error('Error deleting session:', error)
      return false
    }
  },
  
  // Phase 5: Citation Linking - Open a citation in the library panel
  openCitation: (citation: Citation) => {
    const jumpRequest: LibraryJumpRequest = {
      docId: citation.doc_id,
      locator: citation.locator,
      citation,
    }
    set({ pendingCitationJump: jumpRequest })
  },
  
  clearPendingCitationJump: () => set({ pendingCitationJump: null }),
}))
