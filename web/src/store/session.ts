import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
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
  status: 'running' | 'paused' | 'completed' | 'failed'
  createdAt: Date
  updatedAt: Date
}

export interface Todo {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'claimed' | 'verified'
}

export type WorkspacePanel = 'browser' | 'cli' | 'todos' | 'knowledge'
export type AutonomyLevel = 'high' | 'medium' | 'low'

interface SessionState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
  
  browserUrl: string
  browserTitle: string
  browserScreenshotUrl: string | null
  browserControl: 'user' | 'agent'
  
  terminalOutput: string[]
  terminalControl: 'user' | 'agent'
  
  todos: Todo[]
  
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
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [
    { id: '1', title: 'Project Alpha Research', status: 'running', createdAt: new Date(Date.now() - 60000), updatedAt: new Date() },
    { id: '2', title: 'Code Refactoring Session', status: 'completed', createdAt: new Date(Date.now() - 120000), updatedAt: new Date(Date.now() - 60000) },
    { id: '3', title: 'Market Analysis Q4', status: 'completed', createdAt: new Date(Date.now() - 180000), updatedAt: new Date(Date.now() - 120000) },
  ],
  currentSessionId: '1',
  messages: [
    {
      id: '1',
      role: 'user',
      content: 'Research the latest trends in decentralized finance and draft a summary for the Q3 report. Also, check my todos.',
      timestamp: new Date(Date.now() - 30000),
    },
    {
      id: '2',
      role: 'assistant',
      content: "Certainly. I've started researching DeFi trends. A browser tab is open with my findings. I'm also drafting the summary and have updated your task list.",
      timestamp: new Date(Date.now() - 20000),
      toolCalls: [
        { id: 't1', name: 'Browsing: Coindesk, Bloomberg...', status: 'completed' },
        { id: 't2', name: 'Drafting Summary', status: 'running' },
        { id: 't3', name: 'Updating Todos', status: 'completed' },
      ],
    },
  ],
  streamingContent: '',
  isStreaming: false,
  
  browserUrl: 'https://bloomberg.com/defi-trends-2025',
  browserTitle: 'Top 10 DeFi Trends for 2025 - Bloomberg',
  browserScreenshotUrl: null,
  browserControl: 'agent',
  
  terminalOutput: [
    'Analyzing data streams...',
    '> Fetching API data from source X...',
    '> Processing natural language summary...',
    '> Updating task database: OK',
    '> _',
  ],
  terminalControl: 'agent',
  
  todos: [
    { id: '1', content: 'Research DeFi Trends', status: 'in_progress' },
    { id: '2', content: 'Draft Q3 Summary', status: 'in_progress' },
    { id: '3', content: 'Review Draft with User', status: 'pending' },
    { id: '4', content: 'Schedule Team Meeting', status: 'pending' },
  ],
  
  maximizedPanel: null,
  historySidebarCollapsed: false,
  autonomyLevel: 'high',
  agentGoal: 'Create Q3 Report',
  agentStatus: 'active',
  
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
  })),
}))
