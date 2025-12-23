"use client"

import { useEffect, useState } from "react"
import { useSession, signOut } from "next-auth/react"
import { useRouter } from "next/navigation"

interface Session {
  id: string
  title: string
  created_at: string
  last_active: string
}

interface Message {
  role: string
  content: string
  created_at: string
}

export default function HomePage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [ws, setWs] = useState<WebSocket | null>(null)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

  // Load sessions
  useEffect(() => {
    if (session?.accessToken) {
      loadSessions()
    }
  }, [session])

  // WebSocket connection
  useEffect(() => {
    if (currentSessionId && session?.accessToken) {
      connectWebSocket(currentSessionId, session.accessToken)
    }
    return () => {
      ws?.close()
    }
  }, [currentSessionId, session?.accessToken])

  const loadSessions = async () => {
    const response = await fetch(`${apiUrl}/api/sessions`, {
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
      },
    })
    const data = await response.json()
    setSessions(data)
  }

  const createNewSession = async () => {
    const response = await fetch(`${apiUrl}/api/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
      },
    })
    const newSession = await response.json()
    setSessions([newSession, ...sessions])
    setCurrentSessionId(newSession.id)
  }

  const connectWebSocket = (sessionId: string, token: string) => {
    const wsUrl = `ws://localhost:8000/ws/${sessionId}?token=${token}`
    const websocket = new WebSocket(wsUrl)

    websocket.onopen = () => {
      console.log("WebSocket connected")
    }

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === "history") {
        setMessages(data.messages)
      } else if (data.type === "message") {
        setMessages((prev) => [
          ...prev,
          {
            role: data.role,
            content: data.content,
            created_at: data.created_at,
          },
        ])
      }
    }

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error)
    }

    websocket.onclose = () => {
      console.log("WebSocket closed")
    }

    setWs(websocket)
  }

  const sendMessage = () => {
    if (!input.trim() || !ws) return

    ws.send(
      JSON.stringify({
        type: "message",
        content: input,
      })
    )
    setInput("")
  }

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold">CompyMac</h1>
          <p className="text-sm text-gray-400">{session?.user?.email}</p>
        </div>

        <button
          onClick={createNewSession}
          className="m-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md text-sm font-medium"
        >
          + New Chat
        </button>

        <div className="flex-1 overflow-y-auto">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setCurrentSessionId(s.id)}
              className={`w-full px-4 py-3 text-left hover:bg-gray-800 ${
                currentSessionId === s.id ? "bg-gray-800" : ""
              }`}
            >
              <div className="text-sm font-medium truncate">{s.title}</div>
              <div className="text-xs text-gray-400">
                {new Date(s.last_active).toLocaleDateString()}
              </div>
            </button>
          ))}
        </div>

        <button
          onClick={() => signOut()}
          className="p-4 border-t border-gray-700 text-sm text-gray-400 hover:text-white"
        >
          Sign Out
        </button>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {currentSessionId ? (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-2xl px-4 py-2 rounded-lg ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-gray-200 text-gray-900"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
            </div>

            {/* Input */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                  placeholder="Type a message..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={sendMessage}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a chat or create a new one to get started
          </div>
        )}
      </div>
    </div>
  )
}
