'use client'

import { CheckSquare, Circle, Loader2, Maximize2, Minimize2 } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

interface TodosPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
}

export function TodosPanel({ isMaximized, onMaximize }: TodosPanelProps) {
  const { todos } = useSessionStore()

  const currentTasks = todos.filter(t => t.status === 'in_progress' || t.status === 'pending').slice(0, isMaximized ? undefined : 3)
  const upcomingTasks = todos.filter(t => t.status === 'pending').slice(isMaximized ? 0 : 1)

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-white">Todos</span>
        </div>
        <button 
          onClick={onMaximize}
          className="p-1 text-slate-400 hover:text-white transition-colors"
        >
          {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex-1 p-3 overflow-y-auto">
        <div className="mb-4">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
            Current Tasks
          </h4>
          <div className="space-y-2">
            {currentTasks.map((todo) => (
              <div key={todo.id} className="flex items-start gap-2">
                {todo.status === 'in_progress' ? (
                  <Loader2 className="w-4 h-4 text-blue-400 animate-spin mt-0.5" />
                ) : todo.status === 'completed' ? (
                  <CheckSquare className="w-4 h-4 text-green-400 mt-0.5" />
                ) : (
                  <Circle className="w-4 h-4 text-slate-500 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm",
                    todo.status === 'completed' ? "text-slate-500 line-through" : "text-slate-200"
                  )}>
                    {todo.content}
                  </p>
                  {todo.status === 'in_progress' && (
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-xs text-slate-500">In Progress - 45%</span>
                      <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full w-[45%] bg-blue-500 rounded-full" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {(isMaximized || upcomingTasks.length > 0) && (
          <div>
            <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
              Upcoming
            </h4>
            <div className="space-y-2">
              {upcomingTasks.map((todo) => (
                <div key={todo.id} className="flex items-center gap-2">
                  <Circle className="w-4 h-4 text-slate-600" />
                  <p className="text-sm text-slate-400">{todo.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
