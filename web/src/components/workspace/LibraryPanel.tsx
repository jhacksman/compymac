'use client'

import { useState, useEffect, useRef } from 'react'
import { BookOpen, Upload, FileText, Search, Trash2, ChevronLeft, ChevronRight, Image, FileType, Info, Loader2, Copy, Check } from 'lucide-react'
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
  chunks?: DocumentChunk[]
  metadata?: Record<string, unknown>
}

interface DocumentChunk {
  id: string
  content: string
  metadata?: {
    page_num?: number
    chunk_index?: number
    [key: string]: unknown
  }
}

type ViewTab = 'original' | 'ocr' | 'metadata'

interface LibraryPanelProps {
  isMaximized?: boolean
}

export function LibraryPanel({ isMaximized }: LibraryPanelProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [activeTab, setActiveTab] = useState<ViewTab>('original')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [copied, setCopied] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
        await selectDocument(data.id)
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

  const selectDocument = async (docId: string) => {
    setIsLoading(true)
    setCurrentPage(1)
    try {
      const response = await fetch(`${API_BASE}/api/documents/${docId}`)
      const data = await response.json()
      setSelectedDoc(data)
    } catch (error) {
      console.error('Failed to fetch document:', error)
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
      }
    } catch (error) {
      console.error('Failed to delete document:', error)
    }
  }

  const getPageText = (pageNum: number): string => {
    if (!selectedDoc?.chunks) return ''
    
    // Find chunks for this page - chunks contain all pages with markers
    const allContent = selectedDoc.chunks.map(c => c.content).join('\n')
    const pageMarker = `--- Page ${pageNum} ---`
    const nextPageMarker = `--- Page ${pageNum + 1} ---`
    
    const startIdx = allContent.indexOf(pageMarker)
    if (startIdx === -1) return 'No text extracted for this page'
    
    const contentStart = startIdx + pageMarker.length
    const endIdx = allContent.indexOf(nextPageMarker, contentStart)
    const pageContent = endIdx > contentStart 
      ? allContent.slice(contentStart, endIdx)
      : allContent.slice(contentStart)
    
    return pageContent.trim() || 'No text extracted for this page'
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
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
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Document Library</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
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
        {/* Document List Sidebar */}
        <div className="w-56 border-r border-slate-700 flex flex-col">
          <div className="p-2 border-b border-slate-700">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter documents..."
              className="w-full bg-slate-700 rounded px-2 py-1 text-xs text-slate-300 outline-none focus:ring-1 focus:ring-purple-500"
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            {documents.length === 0 ? (
              <div className="p-4 text-center text-slate-500 text-xs">
                No documents yet.
              </div>
            ) : (
              documents
                .filter(doc => !searchQuery || doc.filename.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => selectDocument(doc.id)}
                    className={cn(
                      "p-2 border-b border-slate-700/50 cursor-pointer hover:bg-slate-800/50 transition-colors",
                      selectedDoc?.id === doc.id && "bg-slate-800"
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <FileText className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-white truncate">{doc.filename}</p>
                        <p className="text-xs text-slate-500">
                          {doc.page_count} pages | {formatFileSize(doc.file_size_bytes)}
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

        {/* Document Viewer */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedDoc ? (
            <>
              {/* Page Navigation */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700 bg-slate-800/50">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage <= 1}
                    className="p-1 text-slate-400 hover:text-white disabled:opacity-30"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-xs text-slate-300">
                    Page {currentPage} of {selectedDoc.page_count}
                  </span>
                  <button
                    onClick={() => setCurrentPage(p => Math.min(selectedDoc.page_count, p + 1))}
                    disabled={currentPage >= selectedDoc.page_count}
                    className="p-1 text-slate-400 hover:text-white disabled:opacity-30"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
                <span className="text-xs text-slate-500 truncate max-w-[200px]">
                  {selectedDoc.filename}
                </span>
              </div>

              {/* View Tabs */}
              <div className="flex border-b border-slate-700">
                <button
                  onClick={() => setActiveTab('original')}
                  className={cn(
                    "flex items-center gap-1 px-3 py-2 text-xs font-medium transition-colors",
                    activeTab === 'original'
                      ? "text-purple-400 border-b-2 border-purple-400"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  <Image className="w-3 h-3" />
                  Original
                </button>
                <button
                  onClick={() => setActiveTab('ocr')}
                  className={cn(
                    "flex items-center gap-1 px-3 py-2 text-xs font-medium transition-colors",
                    activeTab === 'ocr'
                      ? "text-purple-400 border-b-2 border-purple-400"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  <FileType className="w-3 h-3" />
                  OCR Text
                </button>
                <button
                  onClick={() => setActiveTab('metadata')}
                  className={cn(
                    "flex items-center gap-1 px-3 py-2 text-xs font-medium transition-colors",
                    activeTab === 'metadata'
                      ? "text-purple-400 border-b-2 border-purple-400"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  <Info className="w-3 h-3" />
                  Metadata
                </button>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-auto">
                {isLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                  </div>
                ) : (
                  <>
                    {/* Original Page View */}
                    {activeTab === 'original' && (
                      <div className="flex items-center justify-center p-4 h-full bg-slate-950">
                        <img
                          src={`${API_BASE}/api/documents/${selectedDoc.id}/pages/${currentPage}.png`}
                          alt={`Page ${currentPage}`}
                          className="max-w-full max-h-full object-contain shadow-lg rounded"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement
                            target.style.display = 'none'
                            const parent = target.parentElement
                            if (parent) {
                              parent.innerHTML = '<div class="text-slate-500 text-sm">Failed to load page image</div>'
                            }
                          }}
                        />
                      </div>
                    )}

                    {/* OCR Text View */}
                    {activeTab === 'ocr' && (
                      <div className="p-4">
                        <div className="flex justify-end mb-2">
                          <button
                            onClick={() => copyToClipboard(getPageText(currentPage))}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-white"
                          >
                            {copied ? (
                              <Check className="w-3 h-3 text-green-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                            {copied ? 'Copied!' : 'Copy'}
                          </button>
                        </div>
                        <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-800 p-4 rounded">
                          {getPageText(currentPage)}
                        </pre>
                      </div>
                    )}

                    {/* Metadata View */}
                    {activeTab === 'metadata' && (
                      <div className="p-4 space-y-4">
                        <div className="bg-slate-800 rounded p-3">
                          <h4 className="text-xs font-medium text-slate-400 mb-2">Document Info</h4>
                          <div className="space-y-1 text-sm">
                            <p className="text-slate-300"><span className="text-slate-500">Filename:</span> {selectedDoc.filename}</p>
                            <p className="text-slate-300"><span className="text-slate-500">Pages:</span> {selectedDoc.page_count}</p>
                            <p className="text-slate-300"><span className="text-slate-500">Size:</span> {formatFileSize(selectedDoc.file_size_bytes)}</p>
                            <p className="text-slate-300"><span className="text-slate-500">Uploaded:</span> {formatDate(selectedDoc.created_at)}</p>
                            <p className="text-slate-300"><span className="text-slate-500">Status:</span> {selectedDoc.status}</p>
                            <p className="text-slate-300"><span className="text-slate-500">Chunks:</span> {selectedDoc.chunk_count}</p>
                          </div>
                        </div>
                        
                        {selectedDoc.metadata && (
                          <div className="bg-slate-800 rounded p-3">
                            <h4 className="text-xs font-medium text-slate-400 mb-2">Processing Info</h4>
                            <div className="space-y-1 text-sm">
                              {selectedDoc.metadata.classification && (
                                <>
                                  <p className="text-slate-300">
                                    <span className="text-slate-500">Type:</span>{' '}
                                    {(selectedDoc.metadata.classification as Record<string, unknown>).doc_type as string}
                                  </p>
                                  <p className="text-slate-300">
                                    <span className="text-slate-500">Text Pages:</span>{' '}
                                    {((selectedDoc.metadata.classification as Record<string, unknown>).text_pages as number[])?.length || 0}
                                  </p>
                                  <p className="text-slate-300">
                                    <span className="text-slate-500">OCR Required Pages:</span>{' '}
                                    {((selectedDoc.metadata.classification as Record<string, unknown>).ocr_required_pages as number[])?.length || 0}
                                  </p>
                                </>
                              )}
                              {selectedDoc.metadata.vision_ocr_pages !== undefined && (
                                <p className="text-slate-300">
                                  <span className="text-slate-500">Vision OCR Pages:</span>{' '}
                                  {selectedDoc.metadata.vision_ocr_pages as number}
                                </p>
                              )}
                              {selectedDoc.metadata.tesseract_ocr_used !== undefined && (
                                <p className="text-slate-300">
                                  <span className="text-slate-500">Tesseract OCR:</span>{' '}
                                  {selectedDoc.metadata.tesseract_ocr_used ? 'Yes' : 'No'}
                                </p>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Select a document to view</p>
                <p className="text-xs mt-1">Or upload a PDF to test OCR</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
