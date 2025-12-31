'use client'

import { useState, useRef, useEffect } from 'react'
import { Terminal, Maximize2, Minimize2 } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

interface TerminalPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
  onRunCommand?: (command: string, execDir?: string) => void
}

export function TerminalPanel({ isMaximized, onMaximize, onRunCommand }: TerminalPanelProps) {
  const { terminalOutput, terminalControl } = useSessionStore()
  const [inputValue, setInputValue] = useState('')
  const terminalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [terminalOutput])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      if (onRunCommand) {
        onRunCommand(inputValue.trim())
      }
      setInputValue('')
    }
  }

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium text-white">CLI</span>
        </div>
        <div className="flex items-center gap-1">
          {terminalControl === 'agent' && (
            <span className="text-xs text-green-400 mr-2">AI Running</span>
          )}
          <button 
            onClick={onMaximize}
            className="p-1 text-slate-400 hover:text-white transition-colors"
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div 
        ref={terminalRef}
        className="flex-1 p-3 font-mono text-sm overflow-y-auto bg-slate-950"
      >
        {terminalOutput.map((line, i) => (
          <div key={i} className="text-green-400 leading-relaxed">
            {line}
          </div>
        ))}
      </div>

      {isMaximized && (
        <div className="px-3 py-2 border-t border-slate-700 bg-slate-900">
          <div className="flex items-center gap-2">
            <span className="text-green-400 font-mono text-sm">$</span>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter command..."
              className="flex-1 bg-transparent text-green-400 font-mono text-sm outline-none placeholder-slate-600"
            />
          </div>
        </div>
      )}
    </div>
  )
}
