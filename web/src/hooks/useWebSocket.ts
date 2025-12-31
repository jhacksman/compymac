'use client'

import { useEffect, useRef, useCallback, useState } from 'react'
import { useSessionStore } from '@/store/session'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'ws://localhost:8000'

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
  }
  events?: Array<{
    type: string
    message: {
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
  const { addMessage, setIsStreaming } = useSessionStore()

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

        if (data.type === 'event' && data.event?.type === 'message_complete') {
          const msg = data.event.message
          if (msg) {
            addMessage({
              id: msg.id,
              role: msg.role,
              content: msg.content,
              timestamp: new Date(msg.timestamp),
            })
          }
          setIsStreaming(false)
        } else if (data.type === 'backfill' && data.events) {
          // Handle backfill of existing messages
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
  }, [sessionId, addMessage, setIsStreaming])

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

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected,
    isConnecting,
    sendMessage,
    connect,
    disconnect,
  }
}
