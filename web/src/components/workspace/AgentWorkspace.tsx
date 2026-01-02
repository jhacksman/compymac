'use client'

import { useState } from 'react'
import { Settings, Globe, Terminal, CheckSquare, Share2, BookOpen } from 'lucide-react'
import { BrowserPanel } from './BrowserPanel'
import { TerminalPanel } from './TerminalPanel'
import { TodosPanel } from './TodosPanel'
import { KnowledgeGraphPanel } from './KnowledgeGraphPanel'
import { LibraryPanel } from './LibraryPanel'
import { cn } from '@/lib/utils'

type TabId = 'browser' | 'cli' | 'todos' | 'knowledge' | 'library'

interface Tab {
  id: TabId
  label: string
  icon: React.ReactNode
}

const tabs: Tab[] = [
  { id: 'browser', label: 'Browser', icon: <Globe className="w-4 h-4" /> },
  { id: 'cli', label: 'CLI', icon: <Terminal className="w-4 h-4" /> },
  { id: 'todos', label: 'Todos', icon: <CheckSquare className="w-4 h-4" /> },
  { id: 'knowledge', label: 'Knowledge Graph', icon: <Share2 className="w-4 h-4" /> },
  { id: 'library', label: 'Library', icon: <BookOpen className="w-4 h-4" /> },
]

interface AgentWorkspaceProps {
  onRunCommand?: (command: string, execDir?: string) => void
  onBrowserNavigate?: (url: string) => void
  onSetBrowserControl?: (control: 'user' | 'agent') => void
  onCreateTodo?: (content: string) => void
  onUpdateTodo?: (id: string, status: 'pending' | 'in_progress' | 'completed') => void
  // Human intervention handlers
  onPauseSession?: (reason: string) => void
  onResumeSession?: (feedback: string) => void
  onApproveTodo?: (id: string, reason: string) => void
  onRejectTodo?: (id: string, reason: string, feedback: string) => void
  onAddTodoNote?: (id: string, note: string) => void
  onEditTodo?: (id: string, content: string) => void
  onDeleteTodo?: (id: string) => void
}

export function AgentWorkspace({
  onRunCommand,
  onBrowserNavigate,
  onSetBrowserControl,
  onCreateTodo,
  onUpdateTodo,
  onPauseSession,
  onResumeSession,
  onApproveTodo,
  onRejectTodo,
  onAddTodoNote,
  onEditTodo,
  onDeleteTodo,
}: AgentWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabId>('browser')

  return (
    <div className="flex flex-col h-full bg-slate-950">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-slate-700 text-white border-b-2 border-blue-500"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
        <button className="p-2 text-slate-400 hover:text-white transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 p-4 min-h-0">
        {activeTab === 'browser' && (
          <BrowserPanel 
            isMaximized 
            onNavigate={onBrowserNavigate}
            onSetControl={onSetBrowserControl}
          />
        )}
        {activeTab === 'cli' && (
          <TerminalPanel 
            isMaximized 
            onRunCommand={onRunCommand}
          />
        )}
        {activeTab === 'todos' && (
          <TodosPanel 
            isMaximized 
            onCreateTodo={onCreateTodo}
            onUpdateTodo={onUpdateTodo}
            onApproveTodo={onApproveTodo}
            onRejectTodo={onRejectTodo}
            onAddNote={onAddTodoNote}
            onEditTodo={onEditTodo}
            onDeleteTodo={onDeleteTodo}
            onPauseSession={onPauseSession}
            onResumeSession={onResumeSession}
          />
        )}
        {activeTab === 'knowledge' && <KnowledgeGraphPanel isMaximized />}
        {activeTab === 'library' && <LibraryPanel isMaximized />}
      </div>
    </div>
  )
}
