'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/session'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const router = useRouter()
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { fetchSessions } = useSessionStore()

  // Create a new session and redirect to its permalink
  useEffect(() => {
    const createAndRedirect = async () => {
      if (isCreating) return
      setIsCreating(true)
      
      try {
        const response = await fetch(`${API_BASE}/sessions`, {
          method: 'POST',
        })
        
        if (!response.ok) {
          throw new Error(`Failed to create session: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Redirect to the session permalink
        router.push(`/chat/${data.id}`)
      } catch (err) {
        console.error('Failed to create session:', err)
        setError(err instanceof Error ? err.message : 'Failed to create session')
        
        // Fallback: create a dev session ID and redirect
        const fallbackId = `dev-session-${Date.now()}`
        router.push(`/chat/${fallbackId}`)
      }
    }
    
    createAndRedirect()
  }, [router, isCreating])

  // Fetch sessions in background for sidebar
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  if (error) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-950 text-white">
        <div className="text-center">
          <p className="text-red-400 mb-2">Error: {error}</p>
          <p className="text-slate-400">Redirecting to fallback session...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex items-center justify-center bg-slate-950 text-white">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-slate-400">Creating new session...</p>
      </div>
    </div>
  )
}
