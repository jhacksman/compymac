'use client'

import { Settings } from 'lucide-react'
import { useSessionStore, type WorkspacePanel } from '@/store/session'
import { BrowserPanel } from './BrowserPanel'
import { TerminalPanel } from './TerminalPanel'
import { TodosPanel } from './TodosPanel'
import { KnowledgeGraphPanel } from './KnowledgeGraphPanel'

export function AgentWorkspace() {
  const { maximizedPanel, setMaximizedPanel } = useSessionStore()

  const handleMaximize = (panel: WorkspacePanel) => {
    if (maximizedPanel === panel) {
      setMaximizedPanel(null)
    } else {
      setMaximizedPanel(panel)
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && maximizedPanel) {
      setMaximizedPanel(null)
    }
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', handleKeyDown)
  }

  if (maximizedPanel) {
    return (
      <div className="flex flex-col h-full bg-slate-950 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Agent Workspace</h2>
          <button className="p-2 text-slate-400 hover:text-white transition-colors">
            <Settings className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 min-h-0">
          {maximizedPanel === 'browser' && (
            <BrowserPanel isMaximized onMaximize={() => handleMaximize('browser')} />
          )}
          {maximizedPanel === 'cli' && (
            <TerminalPanel isMaximized onMaximize={() => handleMaximize('cli')} />
          )}
          {maximizedPanel === 'todos' && (
            <TodosPanel isMaximized onMaximize={() => handleMaximize('todos')} />
          )}
          {maximizedPanel === 'knowledge' && (
            <KnowledgeGraphPanel isMaximized onMaximize={() => handleMaximize('knowledge')} />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-slate-950 p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Agent Workspace</h2>
        <button className="p-2 text-slate-400 hover:text-white transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 grid grid-cols-2 grid-rows-2 gap-3 min-h-0">
        <div className="min-h-0 cursor-pointer" onClick={() => handleMaximize('browser')}>
          <BrowserPanel onMaximize={() => handleMaximize('browser')} />
        </div>
        <div className="min-h-0 cursor-pointer" onClick={() => handleMaximize('todos')}>
          <TodosPanel onMaximize={() => handleMaximize('todos')} />
        </div>
        <div className="min-h-0 cursor-pointer" onClick={() => handleMaximize('cli')}>
          <TerminalPanel onMaximize={() => handleMaximize('cli')} />
        </div>
        <div className="min-h-0 cursor-pointer" onClick={() => handleMaximize('knowledge')}>
          <KnowledgeGraphPanel onMaximize={() => handleMaximize('knowledge')} />
        </div>
      </div>
    </div>
  )
}
