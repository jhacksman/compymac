'use client'

import { useState } from 'react'
import { Globe, RefreshCw, ChevronLeft, ChevronRight, Maximize2, Minimize2, User, Bot, Monitor, Camera, ExternalLink, X } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

interface BrowserPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
  onNavigate?: (url: string) => void
  onSetControl?: (control: 'user' | 'agent') => void
}

export function BrowserPanel({ isMaximized, onMaximize, onNavigate, onSetControl }: BrowserPanelProps) {
  const { 
    browserUrl, 
    browserTitle, 
    browserScreenshotUrl, 
    browserControl,
    browserViewMode,
    livePreviewUrl,
    exposedPorts,
    setBrowserViewMode,
    closePort,
  } = useSessionStore()
  const [urlInput, setUrlInput] = useState(browserUrl)

  const handleNavigate = () => {
    if (onNavigate && urlInput.trim()) {
      let url = urlInput.trim()
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url
      }
      onNavigate(url)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleNavigate()
    }
  }

  const toggleControl = () => {
    if (onSetControl) {
      onSetControl(browserControl === 'user' ? 'agent' : 'user')
    }
  }

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium text-white">Browser</span>
          {exposedPorts.length > 0 && (
            <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
              {exposedPorts.length} port{exposedPorts.length > 1 ? 's' : ''} exposed
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {exposedPorts.length > 0 && (
            <div className="flex items-center gap-0.5 mr-2">
              <button
                onClick={() => setBrowserViewMode('screenshot')}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-l text-xs font-medium transition-colors",
                  browserViewMode === 'screenshot'
                    ? "bg-purple-500/20 text-purple-400"
                    : "bg-slate-700 text-slate-400 hover:text-white"
                )}
                title="Screenshot mode"
              >
                <Camera className="w-3 h-3" />
              </button>
              <button
                onClick={() => setBrowserViewMode('live')}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-r text-xs font-medium transition-colors",
                  browserViewMode === 'live'
                    ? "bg-green-500/20 text-green-400"
                    : "bg-slate-700 text-slate-400 hover:text-white"
                )}
                title="Live preview mode"
              >
                <Monitor className="w-3 h-3" />
              </button>
            </div>
          )}
          <button
            onClick={toggleControl}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
              browserControl === 'agent' 
                ? "bg-green-500/20 text-green-400" 
                : "bg-blue-500/20 text-blue-400"
            )}
          >
            {browserControl === 'agent' ? (
              <>
                <Bot className="w-3 h-3" />
                AI Control
              </>
            ) : (
              <>
                <User className="w-3 h-3" />
                User Control
              </>
            )}
          </button>
          <button 
            onClick={onMaximize}
            className="p-1 text-slate-400 hover:text-white transition-colors"
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {isMaximized && (
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-850 border-b border-slate-700">
          <button className="p-1 text-slate-400 hover:text-white">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button className="p-1 text-slate-400 hover:text-white">
            <ChevronRight className="w-4 h-4" />
          </button>
          <button className="p-1 text-slate-400 hover:text-white" onClick={handleNavigate}>
            <RefreshCw className="w-4 h-4" />
          </button>
          <input
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter URL..."
            className="flex-1 bg-slate-700 rounded px-3 py-1 text-xs text-slate-300 outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      )}

      <div className="flex-1 p-3 overflow-hidden">
        <div className="w-full h-full bg-white rounded-lg overflow-hidden">
          <div className="h-8 bg-slate-100 border-b flex items-center px-3 gap-2">
            <div className="flex gap-1">
              <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
              <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
            </div>
            {!isMaximized && (
              <span className="text-xs text-slate-500 truncate ml-2">
                {browserViewMode === 'live' && livePreviewUrl 
                  ? livePreviewUrl 
                  : browserUrl || 'No page loaded'}
              </span>
            )}
            {browserViewMode === 'live' && livePreviewUrl && (
              <a
                href={livePreviewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto text-slate-400 hover:text-blue-500 transition-colors"
                title="Open in new tab"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
          <div className="flex-1 bg-white overflow-auto" style={{ height: 'calc(100% - 2rem)' }}>
            {browserViewMode === 'live' && livePreviewUrl ? (
              <iframe
                src={livePreviewUrl}
                title="Live Preview"
                className="w-full h-full border-0"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
              />
            ) : browserScreenshotUrl ? (
              <img 
                src={`http://localhost:8000${browserScreenshotUrl}`} 
                alt={browserTitle || 'Browser screenshot'} 
                className="w-full h-auto"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">
                <div className="text-center">
                  <Globe className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No page loaded</p>
                  <p className="text-xs mt-1">Enter a URL above to navigate</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {exposedPorts.length > 0 && (
        <div className="px-3 py-2 bg-slate-800 border-t border-slate-700">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-400">Exposed ports:</span>
            {exposedPorts.map((port) => (
              <div
                key={port.port}
                className="flex items-center gap-1 px-2 py-0.5 bg-slate-700 rounded text-xs"
              >
                <button
                  onClick={() => {
                    setBrowserViewMode('live')
                    useSessionStore.getState().setLivePreviewUrl(port.url)
                  }}
                  className="text-green-400 hover:text-green-300"
                >
                  :{port.port}
                </button>
                <a
                  href={port.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 hover:text-blue-400"
                  title={port.url}
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
                <button
                  onClick={() => closePort(port.port)}
                  className="text-slate-400 hover:text-red-400"
                  title="Close port"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
