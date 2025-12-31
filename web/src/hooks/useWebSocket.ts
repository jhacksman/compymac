'use client'

import { useEffect, useRef, useCallback, useState } from 'react'
import { useSessionStore, type Todo } from '@/store/session'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'ws://localhost:8000'

interface TerminalEntry {
  id: string
  command: string
  output: string
  timestamp: string
  exit_code: number
}

interface BrowserState {
  url: string
  title: string
  screenshot_url: string | null
  elements: Array<{
    element_id: string
    tag: string
    text: string
  }>
}

interface WebSocketMessage {
  type: string
  event?: {
    type: string
    message?: {
      id: string
      role: 'user' | 'assistant'
      content: string
      timestamp: string
    }
    todos?: Array<{
      id: string
      content: string
      status: 'pending' | 'in_progress' | 'completed'
    }>
    lines?: TerminalEntry[]
    new_entry?: TerminalEntry
    url?: string
    title?: string
    screenshot_url?: string | null
    elements?: BrowserState['elements']
    control?: 'user' | 'agent'
  }
  events?: Array<{
    type: string
    message?: {
      id: string
      role: 'user' | 'assistant'
      content: string
      timestamp: string
    }
  }>
  error?: string
  code?: string
  message?: string
}

export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const { 
    addMessage, 
    setIsStreaming, 
    setTodos, 
    setBrowserState, 
    setBrowserControl,
    setTerminalOutput,
  } = useSessionStore()

  const connect = useCallback(() => {
    if (!sessionId || wsRef.current?.readyState === WebSocket.OPEN) return

    setIsConnecting(true)
    const ws = new WebSocket(`${API_URL}/ws/${sessionId}`)

    ws.onopen = () => {
      setIsConnected(true)
      setIsConnecting(false)
      ws.send(JSON.stringify({ type: 'subscribe' }))
    }

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data)

        if (data.type === 'event' && data.event) {
          const evt = data.event
          
          if (evt.type === 'message_complete' && evt.message) {
            addMessage({
              id: evt.message.id,
              role: evt.message.role,
              content: evt.message.content,
              timestamp: new Date(evt.message.timestamp),
            })
            setIsStreaming(false)
          } else if (evt.type === 'todos_updated' && evt.todos) {
            const todos: Todo[] = evt.todos.map(t => ({
              id: t.id,
              content: t.content,
              status: t.status,
            }))
            setTodos(todos)
          } else if (evt.type === 'terminal_output' && evt.lines) {
            const output = evt.lines.map(entry => 
              `$ ${entry.command}\n${entry.output}`
            )
            setTerminalOutput(output)
          } else if (evt.type === 'browser_state') {
            setBrowserState(
              evt.url || '',
              evt.title || '',
              evt.screenshot_url || null
            )
          } else if (evt.type === 'browser_control' && evt.control) {
            setBrowserControl(evt.control)
          }
        } else if (data.type === 'backfill' && data.events) {
          data.events.forEach((evt) => {
            if (evt.type === 'message_complete' && evt.message) {
              addMessage({
                id: evt.message.id,
                role: evt.message.role,
                content: evt.message.content,
                timestamp: new Date(evt.message.timestamp),
              })
            }
          })
        } else if (data.type === 'error') {
          console.error('WebSocket error:', data.message)
          setIsStreaming(false)
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      setIsConnecting(false)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setIsConnected(false)
      setIsConnecting(false)
    }

    wsRef.current = ws
  }, [sessionId, addMessage, setIsStreaming, setTodos, setBrowserState, setBrowserControl, setTerminalOutput])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setIsStreaming(true)
      wsRef.current.send(JSON.stringify({
        type: 'send_message',
        content,
      }))
    }
  }, [setIsStreaming])

  const runCommand = useCallback((command: string, execDir?: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'run_command',
        command,
        exec_dir: execDir || '/home/ubuntu',
      }))
    }
  }, [])

  const browserNavigate = useCallback((url: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'browser_navigate',
        url,
      }))
    }
  }, [])

  const browserClick = useCallback((elementId?: string, coordinates?: [number, number]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'browser_click',
        element_id: elementId,
        coordinates,
      }))
    }
  }, [])

  const browserType = useCallback((elementId: string, text: string, pressEnter?: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'browser_type',
        element_id: elementId,
        text,
        press_enter: pressEnter,
      }))
    }
  }, [])

  const setBrowserControlMode = useCallback((control: 'user' | 'agent') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'browser_control',
        control,
      }))
    }
  }, [])

  const createTodo = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'todo_create',
        content,
      }))
    }
  }, [])

  const updateTodo = useCallback((id: string, status: 'pending' | 'in_progress' | 'completed') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'todo_update',
        id,
        status,
      }))
    }
  }, [])

  useEffect(() => {
    if (!sessionId) return
    
    // Use a flag to track if we should connect
    let shouldConnect = true
    
    // Defer connection to avoid synchronous setState in effect
    const timeoutId = setTimeout(() => {
      if (shouldConnect) {
        connect()
      }
    }, 0)
    
    return () => {
      shouldConnect = false
      clearTimeout(timeoutId)
      disconnect()
    }
  }, [sessionId, connect, disconnect])

  return {
    isConnected,
    isConnecting,
    sendMessage,
    runCommand,
    browserNavigate,
    browserClick,
    browserType,
    setBrowserControlMode,
    createTodo,
    updateTodo,
    connect,
    disconnect,
  }
}
