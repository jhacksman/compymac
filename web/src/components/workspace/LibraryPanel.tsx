'use client'

import { useState, useEffect, useRef } from 'react'
import { BookOpen, Upload, FileText, Search, Trash2, Eye, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

interface Document {
  id: string
  filename: string
  title: string
  page_count: number
  status: 'processing' | 'ready' | 'error'
  created_at: number
  file_size_bytes: number
  chunk_count: number
  error: string | null
}

interface DocumentChunk {
  id: string
  document_id: string
  content: string
  page_num: number
  chunk_index: number
}

interface LibraryPanelProps {
  isMaximized?: boolean
}

export function LibraryPanel({ isMaximized }: LibraryPanelProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [docContent, setDocContent] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<DocumentChunk[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch documents on mount
  useEffect(() => {
    fetchDocuments()
  }, [])

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/library`)
      const data = await response.json()
      setDocuments(data.documents || [])
    } catch (error) {
      console.error('Failed to fetch documents:', error)
    }
  }

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE}/api/documents/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      if (data.id) {
        await fetchDocuments()
        setSelectedDoc(data)
        await fetchDocumentContent(data.id)
      }
    } catch (error) {
      console.error('Failed to upload document:', error)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const fetchDocumentContent = async (docId: string) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/documents/${docId}`)
      const data = await response.json()
      if (data.chunks) {
        const content = data.chunks
          .sort((a: DocumentChunk, b: DocumentChunk) => a.page_num - b.page_num || a.chunk_index - b.chunk_index)
          .map((chunk: DocumentChunk) => `--- Page ${chunk.page_num} ---\n${chunk.content}`)
          .join('\n\n')
        setDocContent(content)
      } else if (data.content) {
        setDocContent(data.content)
      } else {
        setDocContent('No content available')
      }
    } catch (error) {
      console.error('Failed to fetch document content:', error)
      setDocContent('Failed to load document content')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/library/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await response.json()
      setSearchResults(data.results || [])
    } catch (error) {
      console.error('Failed to search:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (docId: string) => {
    try {
      await fetch(`${API_BASE}/api/library/${docId}`, { method: 'DELETE' })
      await fetchDocuments()
      if (selectedDoc?.id === docId) {
        setSelectedDoc(null)
        setDocContent('')
      }
    } catch (error) {
      console.error('Failed to delete document:', error)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString()
  }

  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Document Library</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.epub"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors disabled:opacity-50"
          >
            {isUploading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Upload className="w-3 h-3" />
            )}
            Upload PDF
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Document List */}
        <div className="w-64 border-r border-slate-700 flex flex-col">
          <div className="p-2 border-b border-slate-700">
            <div className="flex gap-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search documents..."
                className="flex-1 bg-slate-700 rounded px-2 py-1 text-xs text-slate-300 outline-none focus:ring-1 focus:ring-purple-500"
              />
              <button
                onClick={handleSearch}
                className="p-1 text-slate-400 hover:text-white"
              >
                <Search className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {documents.length === 0 ? (
              <div className="p-4 text-center text-slate-500 text-sm">
                No documents yet. Upload a PDF to get started.
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => {
                    setSelectedDoc(doc)
                    fetchDocumentContent(doc.id)
                  }}
                  className={cn(
                    "p-2 border-b border-slate-700/50 cursor-pointer hover:bg-slate-800/50 transition-colors",
                    selectedDoc?.id === doc.id && "bg-slate-800"
                  )}
                >
                  <div className="flex items-start gap-2">
                    <FileText className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-500">
                        {doc.page_count} pages | {formatFileSize(doc.file_size_bytes)}
                      </p>
                      <p className="text-xs text-slate-500">
                        {doc.chunk_count} chunks | {doc.status}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(doc.id)
                      }}
                      className="p-1 text-slate-500 hover:text-red-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Document Content */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedDoc ? (
            <>
              <div className="p-3 border-b border-slate-700 bg-slate-800/50">
                <h3 className="text-sm font-medium text-white">{selectedDoc.filename}</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Uploaded: {formatDate(selectedDoc.created_at)} | 
                  Pages: {selectedDoc.page_count} | 
                  Chunks: {selectedDoc.chunk_count}
                </p>
              </div>
              <div className="flex-1 p-3 overflow-y-auto">
                {isLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                  </div>
                ) : (
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono">
                    {docContent}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <Eye className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Select a document to view</p>
                <p className="text-xs mt-1">Or upload a PDF to test OCR</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="border-t border-slate-700 max-h-48 overflow-y-auto">
          <div className="p-2 bg-slate-800/50 text-xs text-slate-400">
            Search Results ({searchResults.length})
          </div>
          {searchResults.map((result, idx) => (
            <div key={idx} className="p-2 border-b border-slate-700/50 text-sm text-slate-300">
              <span className="text-purple-400">Page {result.page_num}:</span> {result.content.slice(0, 200)}...
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
