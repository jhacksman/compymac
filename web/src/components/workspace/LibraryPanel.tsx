'use client'

import { useState, useEffect, useRef } from 'react'
import { BookOpen, Upload, FileText, Trash2, ChevronLeft, ChevronRight, Image, FileType, Info, Loader2, Copy, Check, Folder, FolderOpen, ChevronDown, ChevronRight as ChevronRightIcon, BookMarked, FolderUp } from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface NavigationEntry {
  id: string
  title: string
  level: number
  target: {
    type: 'pdf_page' | 'epub_href'
    page?: number
    href?: string
  }
  children?: NavigationEntry[]
}

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
  library_path: string
  doc_format: 'pdf' | 'epub'
  navigation: NavigationEntry[]
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

// Tree node types for the library tree
interface TreeNode {
  id: string
  name: string
  type: 'folder' | 'document' | 'chapter'
  children?: TreeNode[]
  document?: Document
  navEntry?: NavigationEntry
}

type ViewTab = 'original' | 'ocr' | 'metadata'

interface EpubChapter {
  href: string
  title: string
  html: string
  css: string
  chapter_index: number
  total_chapters: number
  has_prev: boolean
  has_next: boolean
}

interface LibraryPanelProps {
  isMaximized?: boolean
}

// Build tree structure from flat document list
function buildLibraryTree(documents: Document[]): TreeNode[] {
  const root: TreeNode[] = []
  const folderMap = new Map<string, TreeNode>()

  for (const doc of documents) {
    const pathParts = doc.library_path.split('/').filter(p => p)
    let currentLevel = root
    let currentPath = ''

    // Create folder nodes for each path segment except the last (filename)
    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = pathParts[i]
      currentPath = currentPath ? `${currentPath}/${part}` : part

      let folderNode = folderMap.get(currentPath)
      if (!folderNode) {
        folderNode = {
          id: `folder_${currentPath}`,
          name: part,
          type: 'folder',
          children: [],
        }
        folderMap.set(currentPath, folderNode)
        currentLevel.push(folderNode)
      }
      currentLevel = folderNode.children!
    }

    // Create document node
    const docNode: TreeNode = {
      id: doc.id,
      name: doc.filename,
      type: 'document',
      document: doc,
      children: doc.navigation?.length > 0 ? buildNavigationTree(doc.navigation) : undefined,
    }
    currentLevel.push(docNode)
  }

  return root
}

// Build navigation tree from navigation entries
function buildNavigationTree(navigation: NavigationEntry[]): TreeNode[] {
  return navigation.map(nav => ({
    id: nav.id,
    name: nav.title,
    type: 'chapter' as const,
    navEntry: nav,
    children: nav.children ? buildNavigationTree(nav.children) : undefined,
  }))
}

// TreeNodeComponent for recursive rendering
function TreeNodeComponent({
  node,
  depth,
  expandedNodes,
  toggleExpanded,
  selectedDocId,
  onSelectDocument,
  onSelectNavigation,
  onDeleteDocument,
}: {
  node: TreeNode
  depth: number
  expandedNodes: Set<string>
  toggleExpanded: (id: string) => void
  selectedDocId: string | null
  onSelectDocument: (doc: Document) => void
  onSelectNavigation: (doc: Document, nav: NavigationEntry) => void
  onDeleteDocument: (docId: string) => void
}) {
  const isExpanded = expandedNodes.has(node.id)
  const hasChildren = node.children && node.children.length > 0

  const handleClick = () => {
    if (node.type === 'folder') {
      toggleExpanded(node.id)
    } else if (node.type === 'document' && node.document) {
      onSelectDocument(node.document)
      if (hasChildren) {
        toggleExpanded(node.id)
      }
    } else if (node.type === 'chapter' && node.navEntry) {
      // Find parent document and navigate
      // This is handled by the parent component
    }
  }

  const Icon = node.type === 'folder' 
    ? (isExpanded ? FolderOpen : Folder)
    : node.type === 'document'
    ? (node.document?.doc_format === 'epub' ? BookMarked : FileText)
    : BookMarked

  return (
    <div>
      <div
        onClick={handleClick}
        className={cn(
          "flex items-center gap-1 py-1 px-2 cursor-pointer hover:bg-slate-800/50 rounded text-xs",
          node.type === 'document' && node.document?.id === selectedDocId && "bg-slate-800",
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              toggleExpanded(node.id)
            }}
            className="p-0.5 text-slate-500 hover:text-white"
          >
            {isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRightIcon className="w-3 h-3" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Icon className={cn(
          "w-3.5 h-3.5 flex-shrink-0",
          node.type === 'folder' ? "text-yellow-500" : 
          node.type === 'document' ? "text-purple-400" : "text-slate-400"
        )} />
        <span className="truncate text-slate-300">{node.name}</span>
        {node.type === 'document' && node.document && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDeleteDocument(node.document!.id)
            }}
            className="ml-auto p-1 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
      </div>
      {isExpanded && hasChildren && (
        <div>
          {node.children!.map(child => (
            <TreeNodeComponent
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedNodes={expandedNodes}
              toggleExpanded={toggleExpanded}
              selectedDocId={selectedDocId}
              onSelectDocument={onSelectDocument}
              onSelectNavigation={onSelectNavigation}
              onDeleteDocument={onDeleteDocument}
            />
          ))}
        </div>
      )}
    </div>
  )
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
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [epubChapter, setEpubChapter] = useState<EpubChapter | null>(null)
  const [isLoadingChapter, setIsLoadingChapter] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchDocuments()
  }, [])

  const toggleExpanded = (id: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const libraryTree = buildLibraryTree(documents)

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

  const handleFolderUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    setIsUploading(true)
    const formData = new FormData()

    // Filter for PDF and EPUB files only
    const validFiles = Array.from(files).filter(f => 
      f.name.toLowerCase().endsWith('.pdf') || f.name.toLowerCase().endsWith('.epub')
    )

    if (validFiles.length === 0) {
      console.error('No PDF or EPUB files found in folder')
      setIsUploading(false)
      return
    }

    // Add files and their relative paths
    for (const file of validFiles) {
      formData.append('files', file)
      // webkitRelativePath contains the folder structure
      formData.append('relative_paths', (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name)
    }

    try {
      const response = await fetch(`${API_BASE}/api/documents/upload-batch`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      console.log('Batch upload result:', data)
      await fetchDocuments()
      // Select the first successfully uploaded document
      const firstSuccess = data.results?.find((r: { status: string; id: string }) => r.status === 'ready')
      if (firstSuccess?.id) {
        await selectDocument(firstSuccess.id)
      }
    } catch (error) {
      console.error('Failed to upload folder:', error)
    } finally {
      setIsUploading(false)
      if (folderInputRef.current) {
        folderInputRef.current.value = ''
      }
    }
  }

  const handleSelectDocument = async (doc: Document) => {
    await selectDocument(doc.id)
  }

  const handleSelectNavigation = (doc: Document, nav: NavigationEntry) => {
    // Navigate to the specific page/chapter
    if (nav.target.type === 'pdf_page' && nav.target.page) {
      setCurrentPage(nav.target.page)
    }
    // For EPUB, we could implement chapter navigation later
  }

    const selectDocument = async (docId: string) => {
      setIsLoading(true)
      setCurrentPage(1)
      setEpubChapter(null)
      try {
        const response = await fetch(`${API_BASE}/api/documents/${docId}`)
        const data = await response.json()
        setSelectedDoc(data)
      
        // If it's an EPUB, load the first chapter
        if (data.doc_format === 'epub') {
          await fetchEpubChapter(docId, 0)
        }
      } catch (error) {
        console.error('Failed to fetch document:', error)
      } finally {
        setIsLoading(false)
      }
    }

    const fetchEpubChapter = async (docId: string, chapterIndex: number) => {
      setIsLoadingChapter(true)
      try {
        const response = await fetch(
          `${API_BASE}/api/documents/${docId}/epub/chapter?chapter_index=${chapterIndex}`
        )
        if (response.ok) {
          const data = await response.json()
          setEpubChapter(data)
        } else {
          console.error('Failed to fetch EPUB chapter:', response.statusText)
          setEpubChapter(null)
        }
      } catch (error) {
        console.error('Failed to fetch EPUB chapter:', error)
        setEpubChapter(null)
      } finally {
        setIsLoadingChapter(false)
      }
    }

    const handlePrevChapter = () => {
      if (selectedDoc && epubChapter && epubChapter.has_prev) {
        fetchEpubChapter(selectedDoc.id, epubChapter.chapter_index - 1)
      }
    }

    const handleNextChapter = () => {
      if (selectedDoc && epubChapter && epubChapter.has_next) {
        fetchEpubChapter(selectedDoc.id, epubChapter.chapter_index + 1)
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
            accept=".pdf,.epub"
            onChange={handleUpload}
            className="hidden"
          />
          <input
            ref={folderInputRef}
            type="file"
            // @ts-expect-error webkitdirectory is not in the type definition
            webkitdirectory=""
            multiple
            onChange={handleFolderUpload}
            className="hidden"
          />
          <button
            onClick={() => folderInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 transition-colors disabled:opacity-50"
            title="Upload folder with PDFs and EPUBs"
          >
            {isUploading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <FolderUp className="w-3 h-3" />
            )}
            Folder
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors disabled:opacity-50"
            title="Upload single PDF or EPUB"
          >
            {isUploading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Upload className="w-3 h-3" />
            )}
            File
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
                <p className="mt-1">Upload a PDF/EPUB or folder</p>
              </div>
            ) : (
              <div className="py-1">
                {/* Filter documents if search query exists */}
                {searchQuery ? (
                  // Flat list for search results
                  documents
                    .filter(doc => doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) || 
                                   doc.library_path.toLowerCase().includes(searchQuery.toLowerCase()))
                    .map((doc) => (
                      <div
                        key={doc.id}
                        onClick={() => selectDocument(doc.id)}
                        className={cn(
                          "flex items-center gap-1 py-1 px-2 cursor-pointer hover:bg-slate-800/50 rounded text-xs",
                          selectedDoc?.id === doc.id && "bg-slate-800"
                        )}
                      >
                        {doc.doc_format === 'epub' ? (
                          <BookMarked className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                        )}
                        <span className="truncate text-slate-300">{doc.filename}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(doc.id)
                          }}
                          className="ml-auto p-1 text-slate-500 hover:text-red-400"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))
                ) : (
                  // Tree view for normal browsing
                  libraryTree.map(node => (
                    <TreeNodeComponent
                      key={node.id}
                      node={node}
                      depth={0}
                      expandedNodes={expandedNodes}
                      toggleExpanded={toggleExpanded}
                      selectedDocId={selectedDoc?.id || null}
                      onSelectDocument={handleSelectDocument}
                      onSelectNavigation={handleSelectNavigation}
                      onDeleteDocument={handleDelete}
                    />
                  ))
                )}
              </div>
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
                      selectedDoc.doc_format === 'epub' ? (
                        <div className="flex flex-col h-full bg-slate-950">
                          {/* EPUB Chapter Navigation */}
                          {epubChapter && (
                            <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
                              <button
                                onClick={handlePrevChapter}
                                disabled={!epubChapter.has_prev || isLoadingChapter}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                <ChevronLeft className="w-4 h-4" />
                                Prev
                              </button>
                              <span className="text-xs text-slate-400">
                                Chapter {epubChapter.chapter_index + 1} of {epubChapter.total_chapters}
                                {epubChapter.title && `: ${epubChapter.title}`}
                              </span>
                              <button
                                onClick={handleNextChapter}
                                disabled={!epubChapter.has_next || isLoadingChapter}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Next
                                <ChevronRight className="w-4 h-4" />
                              </button>
                            </div>
                          )}
                          {/* EPUB Chapter Content */}
                          <div className="flex-1 overflow-auto p-4">
                            {isLoadingChapter ? (
                              <div className="flex items-center justify-center h-full">
                                <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                              </div>
                            ) : epubChapter ? (
                              <>
                                {/* Inject scoped CSS */}
                                <style dangerouslySetInnerHTML={{ __html: epubChapter.css }} />
                                {/* Render sanitized HTML in scoped container */}
                                <div 
                                  className="epub-content prose prose-invert max-w-none"
                                  dangerouslySetInnerHTML={{ __html: epubChapter.html }}
                                />
                              </>
                            ) : (
                              <div className="text-slate-500 text-sm text-center">
                                Failed to load EPUB chapter
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
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
                      )
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
