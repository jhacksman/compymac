'use client'

import { useState, useRef } from 'react'
import { Send, Mic, ChevronRight, User, Bot, Loader2, Wifi, WifiOff, BookOpen, Globe, CheckCircle2, Circle, Clock, AlertCircle, Plus, Bold, Italic, Underline, Strikethrough, Link2, ListOrdered, List, ListTodo, Code, Braces } from 'lucide-react'
import { useSessionStore, type Message, type ToolCall, type WebCitation, type ActivityItem } from '@/store/session'
import { cn } from '@/lib/utils'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { Citation } from '@/types/citation'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
  // Check if this is a web citation (locator.type === 'web_url')
  const isWebCitation = citation.locator?.type === 'web_url'
  
  const handleClick = () => {
    if (isWebCitation && citation.locator && 'url' in citation.locator) {
      // Open URL in new browser tab for web citations
      window.open(citation.locator.url, '_blank', 'noopener,noreferrer')
    }
    onClick(citation)
  }

  // Extract domain for web citations
  const displayTitle = (() => {
    if (isWebCitation && citation.locator && 'url' in citation.locator) {
      try {
        return new URL(citation.locator.url).hostname.replace('www.', '')
      } catch {
        return citation.doc_title
      }
    }
    return citation.doc_title
  })()

  return (
    <button
      onClick={handleClick}
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors",
        isWebCitation
          ? "bg-blue-500/20 text-blue-300 hover:bg-blue-500/30"
          : "bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
      )}
      title={isWebCitation && citation.locator && 'url' in citation.locator 
        ? `${citation.doc_title}\n${citation.locator.url}` 
        : citation.excerpt}
    >
      {isWebCitation ? <Globe className="w-3 h-3" /> : <BookOpen className="w-3 h-3" />}
      [{index + 1}] {displayTitle}
    </button>
  )
}

interface WebCitationChipProps {
  citation: WebCitation
  onClick: (citation: WebCitation) => void
}

function WebCitationChip({ citation, onClick }: WebCitationChipProps) {
  const handleClick = () => {
    // Open URL in new browser tab
    window.open(citation.url, '_blank', 'noopener,noreferrer')
    onClick(citation)
  }

  // Extract domain for display
  const domain = (() => {
    try {
      return new URL(citation.url).hostname.replace('www.', '')
    } catch {
      return citation.url
    }
  })()

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-1 px-2 py-0.5 
                 bg-blue-500/20 text-blue-300 rounded text-xs
                 hover:bg-blue-500/30 transition-colors"
      title={`${citation.title}\n${citation.url}`}
    >
      <Globe className="w-3 h-3" />
      [{citation.num}] {domain}
    </button>
  )
}

function ActivityStatusIcon({ status }: { status: ActivityItem['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-4 h-4 text-green-400" />
    case 'in_progress':
      return <Clock className="w-4 h-4 text-blue-400 animate-pulse" />
    case 'failed':
      return <AlertCircle className="w-4 h-4 text-red-400" />
    default:
      return <Circle className="w-4 h-4 text-slate-500" />
  }
}

function ActivityMessage({ message }: { message: Message }) {
  const { activityData, activityType } = message

  const getActivityIcon = () => {
    switch (activityType) {
      case 'plan': return '📋'
      case 'search': return '🔍'
      case 'browse': return '🌐'
      case 'code': return '💻'
      case 'progress': return '⏳'
      case 'complete': return '✅'
      default: return '📌'
    }
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0 text-sm">
        {getActivityIcon()}
      </div>
      <div className="flex-1">
        <div className="text-xs text-slate-500 mb-1">Activity</div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-3">
          {activityData?.title && (
            <div className="text-sm font-medium text-slate-200 mb-2">
              {activityData.title}
            </div>
          )}
          {activityData?.items && activityData.items.length > 0 && (
            <div className="space-y-1.5">
              {activityData.items.map((item) => (
                <div key={item.id} className="flex items-center gap-2 text-sm">
                  <ActivityStatusIcon status={item.status} />
                  <span className={cn(
                    item.status === 'completed' ? 'text-slate-400 line-through' :
                    item.status === 'in_progress' ? 'text-white' :
                    item.status === 'failed' ? 'text-red-300' :
                    'text-slate-300'
                  )}>
                    {item.label}
                  </span>
                  {item.detail && (
                    <span className="text-slate-500 text-xs">({item.detail})</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {activityData?.progress !== undefined && (
            <div className="mt-2">
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${activityData.progress}%` }}
                />
              </div>
              <div className="text-xs text-slate-500 mt-1 text-right">
                {activityData.progress}%
              </div>
            </div>
          )}
          {!activityData?.items && !activityData?.progress && message.content && (
            <div className="text-sm text-slate-300">{message.content}</div>
          )}
        </div>
      </div>
    </div>
  )
}

interface FormattingAction {
  icon: React.ReactNode
  label: string
  prefix: string
  suffix: string
  block?: boolean
}

const formattingActions: FormattingAction[] = [
  { icon: <Bold className="w-4 h-4" />, label: 'Bold', prefix: '**', suffix: '**' },
  { icon: <Italic className="w-4 h-4" />, label: 'Italic', prefix: '*', suffix: '*' },
  { icon: <Underline className="w-4 h-4" />, label: 'Underline', prefix: '<u>', suffix: '</u>' },
  { icon: <Strikethrough className="w-4 h-4" />, label: 'Strikethrough', prefix: '~~', suffix: '~~' },
  { icon: <Link2 className="w-4 h-4" />, label: 'Link', prefix: '[', suffix: '](url)' },
  { icon: <ListOrdered className="w-4 h-4" />, label: 'Numbered List', prefix: '1. ', suffix: '', block: true },
  { icon: <List className="w-4 h-4" />, label: 'Bullet List', prefix: '- ', suffix: '', block: true },
  { icon: <ListTodo className="w-4 h-4" />, label: 'Task List', prefix: '- [ ] ', suffix: '', block: true },
  { icon: <Code className="w-4 h-4" />, label: 'Inline Code', prefix: '`', suffix: '`' },
  { icon: <Braces className="w-4 h-4" />, label: 'Code Block', prefix: '```\n', suffix: '\n```', block: true },
]

function FormattingToolbar({ 
  textareaRef, 
  inputValue, 
  setInputValue 
}: { 
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  inputValue: string
  setInputValue: (value: string) => void
}) {
  const applyFormatting = (action: FormattingAction) => {
    const textarea = textareaRef.current
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selectedText = inputValue.substring(start, end)
    
    let newText: string
    let newCursorPos: number

    if (action.block && start === end) {
      const beforeCursor = inputValue.substring(0, start)
      const afterCursor = inputValue.substring(end)
      const needsNewlineBefore = beforeCursor.length > 0 && !beforeCursor.endsWith('\n')
      const prefix = needsNewlineBefore ? '\n' + action.prefix : action.prefix
      newText = beforeCursor + prefix + action.suffix + afterCursor
      newCursorPos = start + prefix.length
    } else if (selectedText) {
      newText = inputValue.substring(0, start) + action.prefix + selectedText + action.suffix + inputValue.substring(end)
      newCursorPos = start + action.prefix.length + selectedText.length + action.suffix.length
    } else {
      newText = inputValue.substring(0, start) + action.prefix + action.suffix + inputValue.substring(end)
      newCursorPos = start + action.prefix.length
    }

    setInputValue(newText)
    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(newCursorPos, newCursorPos)
    }, 0)
  }

  return (
    <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-slate-700">
      {formattingActions.slice(0, 4).map((action, i) => (
        <button
          key={i}
          onClick={() => applyFormatting(action)}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title={action.label}
        >
          {action.icon}
        </button>
      ))}
      <div className="w-px h-4 bg-slate-600 mx-1" />
      {formattingActions.slice(4, 5).map((action, i) => (
        <button
          key={i}
          onClick={() => applyFormatting(action)}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title={action.label}
        >
          {action.icon}
        </button>
      ))}
      <div className="w-px h-4 bg-slate-600 mx-1" />
      {formattingActions.slice(5, 8).map((action, i) => (
        <button
          key={i}
          onClick={() => applyFormatting(action)}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title={action.label}
        >
          {action.icon}
        </button>
      ))}
      <div className="w-px h-4 bg-slate-600 mx-1" />
      {formattingActions.slice(8).map((action, i) => (
        <button
          key={i}
          onClick={() => applyFormatting(action)}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title={action.label}
        >
          {action.icon}
        </button>
      ))}
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const isActivity = message.role === 'activity'
  const { openCitation } = useSessionStore()

  if (isActivity) {
    return <ActivityMessage message={message} />
  }

  const shouldRenderMarkdown = !isUser && (message.format === 'markdown' || message.format === undefined)

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
          {shouldRenderMarkdown ? (
            <div className="prose prose-sm prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:text-blue-300 prose-code:bg-slate-900 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700 prose-a:text-blue-400 prose-strong:text-white prose-table:text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm leading-relaxed">{message.content}</p>
          )}
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
        {message.webCitations && message.webCitations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1 text-left">
            {message.webCitations.map((webCitation) => (
              <WebCitationChip
                key={`web-${webCitation.num}`}
                citation={webCitation}
                onClick={() => {}}
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
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { messages, agentGoal, agentStatus, currentSessionId, streamingContent, isStreaming } = useSessionStore()
  const { isConnected, isConnecting, sendMessage } = useWebSocket(currentSessionId)

  const handleSend = () => {
    if (!inputValue.trim() || !isConnected) return
    sendMessage(inputValue)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setIsUploading(true)
    try {
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch('http://localhost:8000/library/upload', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          console.error('Failed to upload file:', file.name)
        }
      }
    } catch (error) {
      console.error('Error uploading files:', error)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
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
                <div className="prose prose-sm prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:text-blue-300 prose-code:bg-slate-900 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700 prose-a:text-blue-400 prose-strong:text-white prose-table:text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {streamingContent}
                  </ReactMarkdown>
                </div>
                <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1" />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="px-6 py-4 border-t border-slate-800">
        <div className="bg-slate-800 rounded-2xl overflow-hidden">
          <FormattingToolbar 
            textareaRef={textareaRef} 
            inputValue={inputValue} 
            setInputValue={setInputValue} 
          />
          <div className="flex items-start gap-3 px-4 py-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".epub,.pdf"
              multiple
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
                isUploading 
                  ? "bg-slate-700 text-slate-500" 
                  : "bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-white"
              )}
              title="Upload EPUB or PDF to library"
            >
              {isUploading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Plus className="w-5 h-5" />
              )}
            </button>
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm resize-none min-h-[20px] max-h-[120px] overflow-y-auto"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = Math.min(target.scrollHeight, 120) + 'px'
              }}
            />
            <div className="flex items-center gap-2">
              <button className="p-2 text-slate-400 hover:text-white transition-colors">
                <Mic className="w-4 h-4" />
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
    </div>
  )
}
