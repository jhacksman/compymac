'use client'

import { useState } from 'react'
import { 
  CheckSquare, 
  Circle, 
  Loader2, 
  Maximize2, 
  Minimize2, 
  Plus, 
  HelpCircle, 
  CheckCircle2,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Edit3,
  Trash2,
  Pause,
  Play,
  AlertCircle,
  Clock
} from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

// Status types matching harness: pending -> in_progress -> claimed -> verified
type TodoStatus = 'pending' | 'in_progress' | 'claimed' | 'verified'
type ReviewStatus = 'not_requested' | 'pending_audit' | 'auditing' | 'approved' | 'changes_requested' | 'overridden' | 'escalated'

interface Todo {
  id: string
  content: string
  status: TodoStatus
  created_at?: string
  review_status?: ReviewStatus
  explanation?: string
  audit_attempts?: number
  revision_attempts?: number
  auditor_feedback?: string
  human_notes?: Array<{ timestamp: string; type: string; content?: string; reason?: string; feedback?: string }>
}

interface TodosPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
  onCreateTodo?: (content: string) => void
  onUpdateTodo?: (id: string, status: TodoStatus) => void
  onApproveTodo?: (id: string, reason: string) => void
  onRejectTodo?: (id: string, reason: string, feedback: string) => void
  onAddNote?: (id: string, note: string) => void
  onEditTodo?: (id: string, content: string) => void
  onDeleteTodo?: (id: string) => void
  onPauseSession?: (reason: string) => void
  onResumeSession?: (feedback: string) => void
  isPaused?: boolean
  pauseReason?: string
}

export function TodosPanel({ 
  isMaximized, 
  onMaximize, 
  onCreateTodo, 
  onUpdateTodo,
  onApproveTodo,
  onRejectTodo,
  onAddNote,
  onEditTodo,
  onDeleteTodo,
  onPauseSession,
  onResumeSession,
  isPaused,
  pauseReason
}: TodosPanelProps) {
  const { todos } = useSessionStore()
  const [newTodoContent, setNewTodoContent] = useState('')
  const [selectedTodo, setSelectedTodo] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectFeedback, setRejectFeedback] = useState('')
  const [noteContent, setNoteContent] = useState('')
  const [editContent, setEditContent] = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [showNoteModal, setShowNoteModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)

  // Group todos by status: in_progress/claimed are "current", pending are "upcoming", verified are "completed"
  const currentTasks = (todos as Todo[]).filter(t => t.status === 'in_progress' || t.status === 'claimed').slice(0, isMaximized ? undefined : 3)
  const upcomingTasks = (todos as Todo[]).filter(t => t.status === 'pending').slice(isMaximized ? 0 : 3)
  const completedTasks = (todos as Todo[]).filter(t => t.status === 'verified')

  // Get review status badge
  const getReviewBadge = (todo: Todo) => {
    if (!todo.review_status || todo.review_status === 'not_requested') return null
    const badges: Record<ReviewStatus, { color: string; text: string }> = {
      'not_requested': { color: '', text: '' },
      'pending_audit': { color: 'bg-yellow-500/20 text-yellow-400', text: 'Pending Audit' },
      'auditing': { color: 'bg-blue-500/20 text-blue-400', text: 'Auditing...' },
      'approved': { color: 'bg-green-500/20 text-green-400', text: 'Approved' },
      'changes_requested': { color: 'bg-orange-500/20 text-orange-400', text: 'Changes Requested' },
      'overridden': { color: 'bg-purple-500/20 text-purple-400', text: 'Human Override' },
      'escalated': { color: 'bg-red-500/20 text-red-400', text: 'Escalated' },
    }
    const badge = badges[todo.review_status]
    if (!badge || !badge.text) return null
    return (
      <span className={cn("text-xs px-1.5 py-0.5 rounded", badge.color)}>
        {badge.text}
      </span>
    )
  }

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-white">Todos</span>
          {isPaused && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 flex items-center gap-1">
              <Pause className="w-3 h-3" /> Paused
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onPauseSession && onResumeSession && (
            <button 
              onClick={() => isPaused ? onResumeSession('') : onPauseSession('User requested pause')}
              className={cn(
                "p-1 transition-colors rounded",
                isPaused ? "text-green-400 hover:text-green-300 hover:bg-green-500/10" : "text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/10"
              )}
              title={isPaused ? "Resume session" : "Pause session"}
            >
              {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            </button>
          )}
          <button 
            onClick={onMaximize}
            className="p-1 text-slate-400 hover:text-white transition-colors"
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
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
                    className="flex flex-col gap-1 hover:bg-slate-800/50 rounded p-2 -m-1 border border-transparent hover:border-slate-700"
                  >
                    <div className="flex items-start gap-2">
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
                        <div className="flex items-center gap-2 mt-0.5">
                          {todo.status === 'in_progress' && (
                            <span className="text-xs text-blue-400">In Progress</span>
                          )}
                          {todo.status === 'claimed' && (
                            <span className="text-xs text-yellow-400">Claimed (awaiting verification)</span>
                          )}
                          {getReviewBadge(todo)}
                        </div>
                        {todo.explanation && isMaximized && (
                          <p className="text-xs text-slate-400 mt-1 italic">
                            &quot;{todo.explanation.slice(0, 100)}{todo.explanation.length > 100 ? '...' : ''}&quot;
                          </p>
                        )}
                        {todo.auditor_feedback && (
                          <p className="text-xs text-orange-400 mt-1">
                            <AlertCircle className="w-3 h-3 inline mr-1" />
                            {todo.auditor_feedback}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* Human intervention controls for claimed todos */}
                    {todo.status === 'claimed' && (
                      <div className="flex items-center gap-1 ml-6 mt-1">
                        {onApproveTodo && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              onApproveTodo(todo.id, 'Human approved')
                            }}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/20 text-green-400 hover:bg-green-500/30 rounded transition-colors"
                            title="Approve this todo (human override)"
                          >
                            <ThumbsUp className="w-3 h-3" /> Approve
                          </button>
                        )}
                        {onRejectTodo && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedTodo(todo.id)
                              setShowRejectModal(true)
                            }}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded transition-colors"
                            title="Reject and send back to agent"
                          >
                            <ThumbsDown className="w-3 h-3" /> Reject
                          </button>
                        )}
                        {onAddNote && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedTodo(todo.id)
                              setShowNoteModal(true)
                            }}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-500/20 text-slate-400 hover:bg-slate-500/30 rounded transition-colors"
                            title="Add a note"
                          >
                            <MessageSquare className="w-3 h-3" /> Note
                          </button>
                        )}
                      </div>
                    )}
                    
                    {/* Edit/Delete controls (shown when maximized) */}
                    {isMaximized && (
                      <div className="flex items-center gap-1 ml-6 mt-1">
                        {onEditTodo && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedTodo(todo.id)
                              setEditContent(todo.content)
                              setShowEditModal(true)
                            }}
                            className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                            title="Edit todo"
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                        )}
                        {onDeleteTodo && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              if (confirm('Delete this todo?')) {
                                onDeleteTodo(todo.id)
                              }
                            }}
                            className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                            title="Delete todo"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                        {todo.audit_attempts !== undefined && todo.audit_attempts > 0 && (
                          <span className="text-xs text-slate-500 ml-2">
                            <Clock className="w-3 h-3 inline mr-1" />
                            {todo.audit_attempts} audit attempt(s)
                          </span>
                        )}
                      </div>
                    )}
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

      {/* Reject Modal */}
      {showRejectModal && selectedTodo && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-4 w-96 max-w-[90vw] border border-slate-700">
            <h3 className="text-lg font-medium text-white mb-3">Reject Todo</h3>
            <p className="text-sm text-slate-400 mb-3">
              Provide feedback for the agent to address before re-claiming this todo.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Reason</label>
                <input
                  type="text"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Why is this being rejected?"
                  className="w-full bg-slate-900 rounded px-3 py-2 text-sm text-slate-200 outline-none focus:ring-1 focus:ring-red-500 placeholder-slate-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Feedback for Agent</label>
                <textarea
                  value={rejectFeedback}
                  onChange={(e) => setRejectFeedback(e.target.value)}
                  placeholder="What should the agent do differently?"
                  rows={3}
                  className="w-full bg-slate-900 rounded px-3 py-2 text-sm text-slate-200 outline-none focus:ring-1 focus:ring-red-500 placeholder-slate-500 resize-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => {
                  setShowRejectModal(false)
                  setSelectedTodo(null)
                  setRejectReason('')
                  setRejectFeedback('')
                }}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (onRejectTodo && selectedTodo && (rejectReason || rejectFeedback)) {
                    onRejectTodo(selectedTodo, rejectReason, rejectFeedback)
                    setShowRejectModal(false)
                    setSelectedTodo(null)
                    setRejectReason('')
                    setRejectFeedback('')
                  }
                }}
                disabled={!rejectReason && !rejectFeedback}
                className="px-3 py-1.5 text-sm bg-red-500 hover:bg-red-600 disabled:bg-red-500/50 disabled:cursor-not-allowed text-white rounded transition-colors"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Note Modal */}
      {showNoteModal && selectedTodo && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-4 w-96 max-w-[90vw] border border-slate-700">
            <h3 className="text-lg font-medium text-white mb-3">Add Note</h3>
            <p className="text-sm text-slate-400 mb-3">
              Add a note to this todo for reference.
            </p>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder="Enter your note..."
              rows={4}
              className="w-full bg-slate-900 rounded px-3 py-2 text-sm text-slate-200 outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500 resize-none"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => {
                  setShowNoteModal(false)
                  setSelectedTodo(null)
                  setNoteContent('')
                }}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (onAddNote && selectedTodo && noteContent) {
                    onAddNote(selectedTodo, noteContent)
                    setShowNoteModal(false)
                    setSelectedTodo(null)
                    setNoteContent('')
                  }
                }}
                disabled={!noteContent}
                className="px-3 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 disabled:bg-blue-500/50 disabled:cursor-not-allowed text-white rounded transition-colors"
              >
                Add Note
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Todo Modal */}
      {showEditModal && selectedTodo && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-4 w-96 max-w-[90vw] border border-slate-700">
            <h3 className="text-lg font-medium text-white mb-3">Edit Todo</h3>
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              placeholder="Todo content..."
              rows={3}
              className="w-full bg-slate-900 rounded px-3 py-2 text-sm text-slate-200 outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500 resize-none"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => {
                  setShowEditModal(false)
                  setSelectedTodo(null)
                  setEditContent('')
                }}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (onEditTodo && selectedTodo && editContent) {
                    onEditTodo(selectedTodo, editContent)
                    setShowEditModal(false)
                    setSelectedTodo(null)
                    setEditContent('')
                  }
                }}
                disabled={!editContent}
                className="px-3 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 disabled:bg-blue-500/50 disabled:cursor-not-allowed text-white rounded transition-colors"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
