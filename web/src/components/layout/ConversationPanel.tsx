'use client'

import { useState } from 'react'
import { Send, Mic, ChevronRight, User, Bot, Loader2, Wifi, WifiOff, BookOpen } from 'lucide-react'
import { useSessionStore, type Message, type ToolCall } from '@/store/session'
import { cn } from '@/lib/utils'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { Citation } from '@/types/citation'

function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <ChevronRight className="w-3 h-3" />
      <span>{toolCall.name}</span>
      {toolCall.status === 'running' && (
        <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
      )}
      {toolCall.status === 'completed' && (
        <span className="text-green-400">Done</span>
      )}
    </div>
  )
}

interface CitationChipProps {
  citation: Citation
  index: number
  onClick: (citation: Citation) => void
}

function CitationChip({ citation, index, onClick }: CitationChipProps) {
  return (
    <button
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1 px-2 py-0.5 
                 bg-purple-500/20 text-purple-300 rounded text-xs
                 hover:bg-purple-500/30 transition-colors"
      title={citation.excerpt}
    >
      <BookOpen className="w-3 h-3" />
      [{index + 1}] {citation.doc_title}
    </button>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const { openCitation } = useSessionStore()

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <div className={cn(
        "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
        isUser ? "bg-slate-700" : "bg-gradient-to-br from-blue-500 to-purple-600"
      )}>
        {isUser ? (
          <User className="w-4 h-4 text-slate-300" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      <div className={cn(
        "flex-1 max-w-[80%]",
        isUser ? "text-right" : "text-left"
      )}>
        <div className="text-xs text-slate-500 mb-1">
          {isUser ? 'User' : 'AI'}
        </div>
        <div className={cn(
          "rounded-2xl px-4 py-3 inline-block text-left",
          isUser 
            ? "bg-blue-600 text-white" 
            : "bg-slate-800 text-slate-200"
        )}>
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1 text-left">
            {message.citations.map((citation, i) => (
              <CitationChip
                key={citation.chunk_id}
                citation={citation}
                index={i}
                onClick={openCitation}
              />
            ))}
          </div>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1 text-left">
            {message.toolCalls.map((tc) => (
              <ToolCallItem key={tc.id} toolCall={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ConversationPanel() {
  const [inputValue, setInputValue] = useState('')
  const { messages, agentGoal, agentStatus, currentSessionId, streamingContent, isStreaming } = useSessionStore()
  const { isConnected, isConnecting, sendMessage } = useWebSocket(currentSessionId)

  const handleSend = () => {
    if (!inputValue.trim() || !isConnected) return
    sendMessage(inputValue)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-slate-950 min-w-0">
      <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Omni-Agent:</h2>
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-sm font-medium",
              agentStatus === 'active' ? "text-green-400" : 
              agentStatus === 'paused' ? "text-yellow-400" : "text-slate-400"
            )}>
              {agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)}
            </span>
            {agentStatus === 'active' && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 text-slate-400">
          <div className="flex items-center gap-2">
            <span className="text-sm">Goal:</span>
            <span className="text-sm text-white bg-slate-800 px-3 py-1 rounded-full">
              {agentGoal}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {isConnected ? (
              <Wifi className="w-4 h-4 text-green-400" />
            ) : isConnecting ? (
              <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
            ) : (
              <WifiOff className="w-4 h-4 text-red-400" />
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isStreaming && streamingContent && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-xs text-slate-500 mb-1">AI</div>
              <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-3 inline-block">
                <p className="text-sm leading-relaxed">{streamingContent}</p>
                <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1" />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="px-6 py-4 border-t border-slate-800">
        <div className="flex items-center gap-3 bg-slate-800 rounded-2xl px-4 py-3">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm"
          />
          <div className="flex items-center gap-2">
            <button className="p-2 text-slate-400 hover:text-white transition-colors">
              <span className="text-xs font-medium">Tx</span>
            </button>
            <button className="p-2 text-slate-400 hover:text-white transition-colors">
              <Mic className="w-4 h-4" />
            </button>
            <div className="h-6 w-px bg-slate-700" />
            <button className="px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors">
              Radius
            </button>
            <button
              onClick={handleSend}
              disabled={!inputValue.trim()}
              className={cn(
                "p-2 rounded-full transition-colors",
                inputValue.trim()
                  ? "bg-blue-600 text-white hover:bg-blue-500"
                  : "bg-slate-700 text-slate-500"
              )}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
