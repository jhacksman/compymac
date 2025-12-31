'use client'

import { useState } from 'react'
import { CheckSquare, Circle, Loader2, Maximize2, Minimize2, Plus, HelpCircle, CheckCircle2 } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

// Status types matching harness: pending -> in_progress -> claimed -> verified
type TodoStatus = 'pending' | 'in_progress' | 'claimed' | 'verified'

interface TodosPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
  onCreateTodo?: (content: string) => void
  onUpdateTodo?: (id: string, status: TodoStatus) => void
}

export function TodosPanel({ isMaximized, onMaximize, onCreateTodo, onUpdateTodo }: TodosPanelProps) {
  const { todos } = useSessionStore()
  const [newTodoContent, setNewTodoContent] = useState('')

  // Group todos by status: in_progress/claimed are "current", pending are "upcoming", verified are "completed"
  const currentTasks = todos.filter(t => t.status === 'in_progress' || t.status === 'claimed').slice(0, isMaximized ? undefined : 3)
  const upcomingTasks = todos.filter(t => t.status === 'pending').slice(isMaximized ? 0 : 3)
  const completedTasks = todos.filter(t => t.status === 'verified')

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

      {isMaximized && (
        <div className="px-3 py-2 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newTodoContent}
              onChange={(e) => setNewTodoContent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newTodoContent.trim() && onCreateTodo) {
                  onCreateTodo(newTodoContent.trim())
                  setNewTodoContent('')
                }
              }}
              placeholder="Add a new todo..."
              className="flex-1 bg-slate-800 rounded px-3 py-2 text-sm text-slate-200 outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500"
            />
            <button
              onClick={() => {
                if (newTodoContent.trim() && onCreateTodo) {
                  onCreateTodo(newTodoContent.trim())
                  setNewTodoContent('')
                }
              }}
              className="p-2 bg-blue-500 hover:bg-blue-600 rounded text-white transition-colors"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 p-3 overflow-y-auto">
        {todos.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-400">
            <div className="text-center">
              <CheckSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No todos yet</p>
              <p className="text-xs mt-1">Add a todo above to get started</p>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-4">
              <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                Current Tasks
              </h4>
              <div className="space-y-2">
                {currentTasks.map((todo) => (
                  <div 
                    key={todo.id} 
                    className="flex items-start gap-2 cursor-pointer hover:bg-slate-800/50 rounded p-1 -m-1"
                    onClick={() => {
                      if (onUpdateTodo) {
                        // Status flow: pending -> in_progress -> claimed -> verified
                        const nextStatus: TodoStatus = todo.status === 'pending' ? 'in_progress' : 
                                          todo.status === 'in_progress' ? 'claimed' : 
                                          todo.status === 'claimed' ? 'verified' : 'pending'
                        onUpdateTodo(todo.id, nextStatus)
                      }
                    }}
                  >
                    {todo.status === 'in_progress' ? (
                      <Loader2 className="w-4 h-4 text-blue-400 animate-spin mt-0.5" />
                    ) : todo.status === 'claimed' ? (
                      <HelpCircle className="w-4 h-4 text-yellow-400 mt-0.5" />
                    ) : todo.status === 'verified' ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5" />
                    ) : (
                      <Circle className="w-4 h-4 text-slate-500 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-sm",
                        todo.status === 'verified' ? "text-slate-500 line-through" : "text-slate-200"
                      )}>
                        {todo.content}
                      </p>
                      {todo.status === 'in_progress' && (
                        <span className="text-xs text-blue-400">In Progress</span>
                      )}
                      {todo.status === 'claimed' && (
                        <span className="text-xs text-yellow-400">Claimed (awaiting verification)</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {(isMaximized || upcomingTasks.length > 0) && upcomingTasks.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                  Upcoming
                </h4>
                <div className="space-y-2">
                  {upcomingTasks.map((todo) => (
                    <div 
                      key={todo.id} 
                      className="flex items-center gap-2 cursor-pointer hover:bg-slate-800/50 rounded p-1 -m-1"
                      onClick={() => {
                        if (onUpdateTodo) {
                          onUpdateTodo(todo.id, 'in_progress')
                        }
                      }}
                    >
                      <Circle className="w-4 h-4 text-slate-600" />
                      <p className="text-sm text-slate-400">{todo.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {isMaximized && completedTasks.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                  Completed
                </h4>
                <div className="space-y-2">
                  {completedTasks.map((todo) => (
                    <div 
                      key={todo.id} 
                      className="flex items-center gap-2"
                    >
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                      <p className="text-sm text-slate-500 line-through">{todo.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
