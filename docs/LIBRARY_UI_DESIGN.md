# Library UI Design Document

## Executive Summary

This document specifies the design for CompyMac's Library tab - a document management interface that allows users to upload, view, and search PDF and EPUB documents. The key features are:

1. **Nested folder uploads** - Upload entire folder hierarchies (e.g., 15 Humble Bundle folders) with preserved structure
2. **Collapsible tree navigation** - Folders → Documents → Chapters/Sections in one unified tree
3. **Document-internal navigation** - Extract and display PDF bookmarks and EPUB chapter structure
4. **Dual-view document viewer** - Original page image and OCR-extracted text side by side
5. **Multi-format support** - Both PDF and EPUB (DRM-free) documents

**Key Design Principles:**
- Preserve folder structure from upload through display
- Extract and expose document internal navigation (TOC/bookmarks)
- Click-to-jump at any level: folder, document, chapter, or page
- Original page images must be viewable (not just extracted text)
- OCR text shown separately from original for comparison
- Clear indication of OCR confidence and processing status

---

## 1. Layout Architecture

### 1.1 Library Tab Structure (Updated with Folder Tree)

```
+------------------------------------------------------------------+
|  [Library Tab Header]                    [+ Upload Folder] [+ File]|
+------------------------------------------------------------------+
|                    |                                              |
|  NAVIGATION TREE   |  DOCUMENT VIEWER                            |
|  (Left Sidebar)    |                                              |
|                    |  +------------------------------------------+|
|  [Search...]       |  | [< Prev] Page 3 of 13 [Next >]  [Zoom]  ||
|                    |  +------------------------------------------+|
|  ▼ Humble Bundle   |  |                                          ||
|    ▼ Programming   |  |  [Original]  [OCR Text]  [Metadata]      ||
|      ▼ Clean Code  |  |                                          ||
|        Ch 1: Intro |  |  +--------------------------------------+||
|        Ch 2: Names |  |  |                                      |||
|        Ch 3: Funcs |  |  |   Active Tab Content:                |||
|      ▶ Design Pat  |  |  |                                      |||
|    ▶ Game Dev      |  |  |   - Original: PDF page as image      |||
|  ▶ O'Reilly 2024   |  |  |   - OCR Text: Extracted text         |||
|                    |  |  |   - Metadata: Processing info        |||
|                    |  |  |                                      |||
|                    |  |  +--------------------------------------+||
|                    |  +------------------------------------------+|
+------------------------------------------------------------------+
```

### 1.2 Panel Descriptions

**Navigation Tree (Left Sidebar)**
- Collapsible tree with three levels:
  1. **Folders** - Derived from `library_path` (e.g., "Humble Bundle 2025/Programming")
  2. **Documents** - PDF/EPUB files within folders
  3. **Chapters/Sections** - Extracted from PDF bookmarks or EPUB navigation
- Click folder to expand/collapse children
- Click document to select and view
- Click chapter to jump to that page/section
- Search/filter input at top (filters all levels)
- Delete button on hover for documents

**Document Viewer (Main Area)**
- **Page Navigation Bar**: Prev/Next buttons, current page indicator, optional zoom
- **View Tabs**: 
  - **Original**: Rendered PDF page as image (from backend endpoint)
  - **OCR Text**: Extracted text for current page (from OCR processing)
  - **Metadata**: Processing info (confidence, OCR method used, timestamps)
- **Content Area**: Displays selected tab content for current page

### 1.3 Folder Upload Flow

```
User clicks [+ Upload Folder]
    ↓
Browser shows folder picker (webkitdirectory)
    ↓
User selects folder (e.g., "Humble Bundle 2025")
    ↓
Frontend reads all files with webkitRelativePath
    ↓
Frontend sends batch upload request with relative paths
    ↓
Backend processes each file, stores library_path
    ↓
Frontend rebuilds tree from library_path values
    ↓
User sees nested folder structure in sidebar
```

---

## 2. Document Viewer Tabs

### 2.1 Original Tab

Shows the actual PDF page rendered as an image.

**Implementation:**
- Backend endpoint: `GET /api/documents/{id}/pages/{page_num}.png`
- Renders PDF page using PyMuPDF at 150 DPI
- Returns PNG image
- Frontend displays in `<img>` tag with optional zoom controls

**UI Elements:**
- Page image centered in viewport
- Zoom controls (fit width, fit height, 100%, zoom in/out)
- Loading spinner while image loads

### 2.2 OCR Text Tab

Shows the extracted text for the current page.

**Implementation:**
- Text stored per-page in document chunks
- Each chunk has `metadata.page_num` to identify source page
- Frontend filters chunks by current page number

**UI Elements:**
- Monospace text display with proper line breaks
- Copy button to copy text to clipboard
- Confidence indicator if available (e.g., "OCR Confidence: 92%")
- Highlight search terms if search is active

### 2.3 Metadata Tab

Shows processing information for the document.

**UI Elements:**
- Document info: filename, size, page count, upload date
- Processing info: parser used, OCR method, processing time
- Per-page breakdown: which pages used OCR, confidence scores
- Classification: digital/scanned/mixed

---

## 3. Backend API Endpoints

### 3.1 Page Image Endpoint (NEW)

```
GET /api/documents/{document_id}/pages/{page_num}.png
```

**Parameters:**
- `document_id`: UUID of the document
- `page_num`: 1-indexed page number
- `dpi` (optional): Resolution, default 150

**Response:**
- Content-Type: image/png
- PNG image of the rendered page

**Implementation:**
```python
@app.get("/api/documents/{document_id}/pages/{page_num}.png")
async def get_document_page_image(
    document_id: str,
    page_num: int,
    dpi: int = 150,
) -> Response:
    doc = library_store.get_document(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    file_path = doc.metadata.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "Document file not found")
    
    # Validate page number
    if page_num < 1 or page_num > doc.page_count:
        raise HTTPException(400, f"Invalid page number. Document has {doc.page_count} pages.")
    
    # Render page to image
    pdf_doc = fitz.open(file_path)
    page = pdf_doc[page_num - 1]  # 0-indexed
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")
    pdf_doc.close()
    
    return Response(content=image_bytes, media_type="image/png")
```

### 3.2 Document Content Endpoint (UPDATED)

```
GET /api/documents/{document_id}
```

**Response includes:**
- Document metadata
- Chunks array with per-page text
- Processing metadata (OCR info, confidence)

### 3.3 Per-Page Text Endpoint (NEW - Optional)

```
GET /api/documents/{document_id}/pages/{page_num}/text
```

**Response:**
```json
{
  "page_num": 3,
  "text": "Extracted text content...",
  "ocr_used": true,
  "ocr_method": "vision_llm",
  "confidence": 0.92
}
```

---

## 4. OCR Classification Fix

### 4.1 Current Problem

The current classifier uses a 50-character threshold to determine if a page is "digital" or needs OCR:

```python
if len(text) >= 50:  # min_chars_per_page
    text_pages.append(page_num + 1)
else:
    ocr_required_pages.append(page_num + 1)
```

This fails for image-based PDFs with text overlays (stamps, headers) that have 50+ characters of embedded text but the main content is in images requiring OCR.

### 4.2 Improved Classification

Use text density relative to page area, not just character count:

```python
def _classify_pdf(self, doc: "fitz.Document") -> PDFClassification:
    text_pages = []
    ocr_required_pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        
        # Get page dimensions
        rect = page.rect
        page_area = rect.width * rect.height
        
        # Calculate text density (chars per 1000 sq points)
        text_density = (len(text) / page_area) * 1000 if page_area > 0 else 0
        
        # Check for images
        image_list = page.get_images()
        has_large_images = any(
            img[2] * img[3] > page_area * 0.5  # Image covers >50% of page
            for img in image_list
        )
        
        # Classification logic:
        # - High text density (>5 chars/1000 sq pts) AND no large images = digital
        # - Low text density OR large images = likely image-based, needs OCR
        if text_density > 5 and not has_large_images:
            text_pages.append(page_num + 1)
        elif has_large_images or text_density < 1:
            ocr_required_pages.append(page_num + 1)
        else:
            # Ambiguous - check if text is just headers/footers
            # by looking at text block positions
            blocks = page.get_text("blocks")
            content_blocks = [b for b in blocks if b[1] > rect.height * 0.1 and b[3] < rect.height * 0.9]
            if len(content_blocks) < 2:
                ocr_required_pages.append(page_num + 1)
            else:
                text_pages.append(page_num + 1)
    
    # ... rest of classification
```

### 4.3 Force OCR Option

Add parameter to force OCR regardless of classification:

```python
def parse(self, file_path: Path, force_ocr: bool = False) -> ParseResult:
    # If force_ocr, treat all pages as needing OCR
```

---

## 5. Frontend Component Design

### 5.1 LibraryPanel Component

```typescript
interface LibraryPanelProps {
  isMaximized?: boolean
}

function LibraryPanel({ isMaximized }: LibraryPanelProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [activeTab, setActiveTab] = useState<'original' | 'ocr' | 'metadata'>('original')
  
  return (
    <div className="flex h-full">
      <DocumentList 
        documents={documents}
        selectedId={selectedDoc?.id}
        onSelect={setSelectedDoc}
        onDelete={handleDelete}
        onUpload={handleUpload}
      />
      <DocumentViewer
        document={selectedDoc}
        currentPage={currentPage}
        activeTab={activeTab}
        onPageChange={setCurrentPage}
        onTabChange={setActiveTab}
      />
    </div>
  )
}
```

### 5.2 DocumentViewer Component

```typescript
interface DocumentViewerProps {
  document: Document | null
  currentPage: number
  activeTab: 'original' | 'ocr' | 'metadata'
  onPageChange: (page: number) => void
  onTabChange: (tab: 'original' | 'ocr' | 'metadata') => void
}

function DocumentViewer({ document, currentPage, activeTab, onPageChange, onTabChange }: DocumentViewerProps) {
  if (!document) {
    return <EmptyState message="Select a document to view" />
  }
  
  return (
    <div className="flex-1 flex flex-col">
      {/* Page Navigation */}
      <PageNavigation
        currentPage={currentPage}
        totalPages={document.page_count}
        onPageChange={onPageChange}
      />
      
      {/* View Tabs */}
      <TabBar
        tabs={['original', 'ocr', 'metadata']}
        activeTab={activeTab}
        onTabChange={onTabChange}
      />
      
      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'original' && (
          <OriginalPageView 
            documentId={document.id} 
            pageNum={currentPage} 
          />
        )}
        {activeTab === 'ocr' && (
          <OCRTextView 
            document={document} 
            pageNum={currentPage} 
          />
        )}
        {activeTab === 'metadata' && (
          <MetadataView document={document} />
        )}
      </div>
    </div>
  )
}
```

### 5.3 OriginalPageView Component

```typescript
function OriginalPageView({ documentId, pageNum }: { documentId: string; pageNum: number }) {
  const imageUrl = `${API_BASE}/api/documents/${documentId}/pages/${pageNum}.png`
  
  return (
    <div className="flex items-center justify-center p-4">
      <img 
        src={imageUrl}
        alt={`Page ${pageNum}`}
        className="max-w-full max-h-full object-contain shadow-lg"
        onError={() => setError('Failed to load page image')}
      />
    </div>
  )
}
```

---

## 6. Implementation Phases

### Phase 1: Backend Page Image Endpoint
- Add `/api/documents/{id}/pages/{page_num}.png` endpoint
- Use PyMuPDF to render pages at configurable DPI
- Add security validation (only serve from upload directory)

### Phase 2: Fix OCR Classification
- Update `_classify_pdf` to use text density, not just char count
- Consider image coverage when classifying pages
- Add `force_ocr` parameter option

### Phase 3: Redesign LibraryPanel
- Add page navigation (Prev/Next, page indicator)
- Add view tabs (Original, OCR Text, Metadata)
- Implement OriginalPageView with image loading
- Implement OCRTextView with per-page text display
- Implement MetadataView with processing info

### Phase 4: Per-Page Text Storage
- Update chunking to preserve page boundaries
- Store page_num in chunk metadata
- Update API to return per-page text

---

## 7. Security Considerations

### 7.1 Page Image Endpoint
- Validate document_id exists and belongs to user
- Validate page_num is within bounds
- Only serve files from designated upload directory
- Rate limit to prevent DoS via image generation

### 7.2 File Path Validation
```python
def validate_file_path(file_path: str) -> bool:
    """Ensure file path is within upload directory."""
    upload_dir = Path("/tmp/compymac_uploads").resolve()
    file_path = Path(file_path).resolve()
    return file_path.is_relative_to(upload_dir)
```

---

## 9. Nested Folder Structure Design

### 9.1 Data Model Changes

**LibraryDocument (Updated)**

Add new fields to support folder structure and document navigation:

```python
@dataclass
class LibraryDocument:
    id: str
    user_id: str
    filename: str
    title: str
    page_count: int
    status: DocumentStatus
    created_at: float
    updated_at: float
    file_path: str | None = None
    file_size_bytes: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    
    # NEW: Folder structure support
    library_path: str = ""  # e.g., "Humble Bundle 2025/Programming/Clean Code.pdf"
    doc_format: str = "pdf"  # "pdf" | "epub"
    
    # NEW: Document navigation (TOC/bookmarks)
    navigation: list[dict[str, Any]] = field(default_factory=list)
    # Format: [{"id": "ch1", "title": "Chapter 1", "level": 1, "target": {"type": "page", "page": 1}}]
```

**Navigation Entry Structure**

A format-agnostic structure for both PDF bookmarks and EPUB chapters:

```python
@dataclass
class NavigationEntry:
    id: str           # Unique ID for this entry
    title: str        # Display title (e.g., "Chapter 1: Introduction")
    level: int        # Nesting level (1 = top-level, 2 = subsection, etc.)
    target: dict      # Jump target
    children: list    # Nested entries (optional)

# Target types:
# PDF: {"type": "pdf_page", "page": 17}
# EPUB: {"type": "epub_href", "href": "Text/ch03.xhtml#sec2"}
```

### 9.2 Folder Hierarchy (Derived, Not Stored)

Folders are **derived from `library_path`** at render time, not stored as separate entities.

**Why derived?**
- Simpler implementation (no folder CRUD)
- Handles incremental uploads naturally
- No migration needed for existing documents
- Avoids folder/document sync issues

**How it works:**
1. Backend returns documents with `library_path` field
2. Frontend groups documents by path prefix
3. Tree is built by splitting paths on `/`

```typescript
// Frontend tree building
function buildTree(documents: Document[]): TreeNode[] {
  const root: TreeNode = { name: 'root', children: [], type: 'folder' }
  
  for (const doc of documents) {
    const parts = doc.library_path.split('/')
    let current = root
    
    // Create folder nodes for each path segment
    for (let i = 0; i < parts.length - 1; i++) {
      let folder = current.children.find(c => c.name === parts[i] && c.type === 'folder')
      if (!folder) {
        folder = { name: parts[i], children: [], type: 'folder' }
        current.children.push(folder)
      }
      current = folder
    }
    
    // Add document node with navigation children
    const docNode: TreeNode = {
      name: doc.filename,
      type: 'document',
      document: doc,
      children: doc.navigation.map(nav => ({
        name: nav.title,
        type: 'chapter',
        target: nav.target,
        children: nav.children || []
      }))
    }
    current.children.push(docNode)
  }
  
  return root.children
}
```

### 9.3 PDF Bookmark Extraction

Use PyMuPDF's `get_toc()` to extract PDF bookmarks:

```python
def extract_pdf_navigation(file_path: Path) -> list[dict]:
    """Extract PDF bookmarks/outline as navigation entries."""
    import fitz
    
    doc = fitz.open(file_path)
    toc = doc.get_toc()  # Returns [[level, title, page], ...]
    doc.close()
    
    if not toc:
        return []  # Many PDFs don't have bookmarks
    
    navigation = []
    for i, (level, title, page) in enumerate(toc):
        navigation.append({
            "id": f"nav_{i}",
            "title": title,
            "level": level,
            "target": {"type": "pdf_page", "page": page}
        })
    
    return navigation
```

**Note:** Many PDFs (especially scanned documents) don't have bookmarks. The UI should gracefully handle empty navigation by showing just the document without chapter children.

### 9.4 EPUB Chapter Extraction

Use EbookLib to extract EPUB navigation:

```python
def extract_epub_navigation(file_path: Path) -> list[dict]:
    """Extract EPUB table of contents as navigation entries."""
    from ebooklib import epub
    
    book = epub.read_epub(str(file_path))
    navigation = []
    
    def process_toc_item(item, level=1):
        if isinstance(item, epub.Link):
            return {
                "id": f"nav_{len(navigation)}",
                "title": item.title,
                "level": level,
                "target": {"type": "epub_href", "href": item.href}
            }
        elif isinstance(item, tuple):
            # Section with children: (Section, [children])
            section, children = item
            entry = {
                "id": f"nav_{len(navigation)}",
                "title": section.title if hasattr(section, 'title') else str(section),
                "level": level,
                "target": {"type": "epub_href", "href": getattr(section, 'href', '')},
                "children": [process_toc_item(child, level + 1) for child in children]
            }
            return entry
        return None
    
    for item in book.toc:
        entry = process_toc_item(item)
        if entry:
            navigation.append(entry)
    
    return navigation
```

**DRM Note:** Only DRM-free EPUBs are supported. DRM-protected EPUBs will fail to parse; the UI should show a clear error message.

---

## 10. Folder Upload API

### 10.1 Batch Upload Endpoint (NEW)

```
POST /api/documents/upload-batch
Content-Type: multipart/form-data
```

**Request:**
- `files[]`: Multiple file uploads
- `relative_paths[]`: Corresponding relative paths (same order as files)
- `user_id`: User ID (optional, default: "default")

**Response:**
```json
{
  "job_id": "batch_123",
  "total_files": 15,
  "results": [
    {"filename": "Clean Code.pdf", "id": "doc_1", "status": "ready"},
    {"filename": "Design Patterns.epub", "id": "doc_2", "status": "ready"},
    {"filename": "drm_book.epub", "id": null, "status": "failed", "error": "DRM-protected EPUB"}
  ],
  "success_count": 14,
  "failure_count": 1
}
```

**Implementation:**

```python
@app.post("/api/documents/upload-batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    user_id: str = "default",
) -> dict[str, Any]:
    """
    Upload multiple documents with preserved folder structure.
    
    Args:
        files: List of files to upload
        relative_paths: Corresponding relative paths (from webkitRelativePath)
        user_id: User ID for library storage
    """
    results = []
    
    for file, rel_path in zip(files, relative_paths):
        # Normalize and sanitize path
        safe_path = sanitize_library_path(rel_path)
        
        # Determine format from extension
        ext = Path(file.filename).suffix.lower()
        doc_format = "epub" if ext == ".epub" else "pdf"
        
        try:
            # Create document with library_path
            doc = library_store.create_document(
                user_id=user_id,
                filename=file.filename,
                library_path=safe_path,
                doc_format=doc_format,
            )
            
            # Save and process file
            # ... (similar to existing upload logic)
            
            # Extract navigation
            navigation = extract_navigation(file_path, doc_format)
            library_store.update_document(doc.id, navigation=navigation)
            
            results.append({"filename": file.filename, "id": doc.id, "status": "ready"})
            
        except Exception as e:
            results.append({"filename": file.filename, "id": None, "status": "failed", "error": str(e)})
    
    return {
        "total_files": len(files),
        "results": results,
        "success_count": sum(1 for r in results if r["status"] == "ready"),
        "failure_count": sum(1 for r in results if r["status"] == "failed"),
    }


def sanitize_library_path(path: str) -> str:
    """Sanitize user-provided path to prevent traversal attacks."""
    # Normalize separators
    path = path.replace("\\", "/")
    
    # Remove dangerous components
    parts = [p for p in path.split("/") if p and p != ".." and not p.startswith(".")]
    
    # Rejoin
    return "/".join(parts)
```

### 10.2 Updated Library List Endpoint

```
GET /api/library?user_id=default
```

**Response (Updated):**
```json
{
  "user_id": "default",
  "documents": [
    {
      "id": "doc_1",
      "filename": "Clean Code.pdf",
      "library_path": "Humble Bundle 2025/Programming/Clean Code.pdf",
      "doc_format": "pdf",
      "page_count": 464,
      "status": "ready",
      "navigation": [
        {"id": "nav_0", "title": "Chapter 1: Clean Code", "level": 1, "target": {"type": "pdf_page", "page": 1}},
        {"id": "nav_1", "title": "Chapter 2: Meaningful Names", "level": 1, "target": {"type": "pdf_page", "page": 17}}
      ]
    }
  ],
  "count": 1
}
```

---

## 11. EPUB Support

### 11.1 EPUB Parsing Pipeline

EPUBs are structurally different from PDFs:
- **No pages**: Content is organized by chapters/sections (spine items)
- **HTML-based**: Content is XHTML, not rendered images
- **Navigation**: NCX (EPUB2) or nav.xhtml (EPUB3)

**Parsing approach:**

```python
def parse_epub(file_path: Path) -> ParseResult:
    """Parse EPUB file and extract text content."""
    from ebooklib import epub
    from bs4 import BeautifulSoup
    
    book = epub.read_epub(str(file_path))
    
    # Extract text from each spine item (chapter)
    full_text = []
    chapter_count = 0
    
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        if text:
            chapter_count += 1
            full_text.append(f"--- Chapter {chapter_count} ---\n{text}")
    
    # Extract navigation
    navigation = extract_epub_navigation(file_path)
    
    return ParseResult(
        text="\n\n".join(full_text),
        metadata={
            "doc_format": "epub",
            "chapter_count": chapter_count,
            "title": book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else None,
            "author": book.get_metadata('DC', 'creator')[0][0] if book.get_metadata('DC', 'creator') else None,
        },
        navigation=navigation,
    )
```

### 11.2 EPUB Viewer Considerations

Unlike PDFs, EPUBs don't have "pages" to render as images:

| Feature | PDF | EPUB |
|---------|-----|------|
| Original tab | Page image | Chapter HTML (rendered) |
| Navigation | Page numbers | Chapter/section hrefs |
| Page count | Actual pages | Synthetic (chapter count) |

**EPUB viewer approach:**
- "Original" tab shows rendered chapter HTML
- Navigation jumps to chapter, not page
- No page numbers; use chapter index instead

---

## 12. Frontend Tree Component

### 12.1 Component Selection

Recommended: **Build custom tree** using existing Tailwind/Lucide icons.

**Why custom?**
- Current UI uses Tailwind + Lucide (no component library)
- Tree is simple (3 levels max)
- Avoids heavy dependencies (MUI X, etc.)
- Full control over styling

**Alternative:** If more features needed later, consider:
- `@headlessui/react` for accessibility
- `react-arborist` for drag-and-drop

### 12.2 Tree Component Design

```typescript
interface TreeNode {
  id: string
  name: string
  type: 'folder' | 'document' | 'chapter'
  children?: TreeNode[]
  document?: Document  // For document nodes
  target?: NavigationTarget  // For chapter nodes
}

interface NavigationTarget {
  type: 'pdf_page' | 'epub_href'
  page?: number
  href?: string
}

function LibraryTree({ documents, onSelectDocument, onJumpToTarget }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const tree = useMemo(() => buildTree(documents), [documents])
  
  const toggleExpand = (nodeId: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }
  
  const renderNode = (node: TreeNode, depth: number) => (
    <div key={node.id}>
      <div 
        className={cn("flex items-center gap-1 py-1 px-2 hover:bg-slate-800 cursor-pointer", 
          depth > 0 && `ml-${depth * 4}`)}
        onClick={() => handleClick(node)}
      >
        {node.children?.length ? (
          expanded.has(node.id) ? <ChevronDown /> : <ChevronRight />
        ) : <span className="w-4" />}
        
        {node.type === 'folder' && <Folder className="w-4 h-4 text-yellow-400" />}
        {node.type === 'document' && <FileText className="w-4 h-4 text-blue-400" />}
        {node.type === 'chapter' && <BookOpen className="w-4 h-4 text-purple-400" />}
        
        <span className="text-sm truncate">{node.name}</span>
      </div>
      
      {expanded.has(node.id) && node.children?.map(child => renderNode(child, depth + 1))}
    </div>
  )
  
  return <div className="overflow-y-auto">{tree.map(node => renderNode(node, 0))}</div>
}
```

---

## 13. Implementation Phases (Updated)

### Phase 1: Data Model Updates
- Add `library_path`, `doc_format`, `navigation` fields to LibraryDocument
- Update `create_document()` to accept new fields
- Update `to_dict()` to include new fields in API responses

### Phase 2: Navigation Extraction
- Implement `extract_pdf_navigation()` using PyMuPDF `get_toc()`
- Implement `extract_epub_navigation()` using EbookLib
- Add EbookLib + BeautifulSoup dependencies

### Phase 3: Batch Upload API
- Add `POST /api/documents/upload-batch` endpoint
- Implement path sanitization
- Update existing upload to set `library_path` (filename only for single uploads)

### Phase 4: EPUB Parsing
- Implement `parse_epub()` for text extraction
- Update DocumentParser to handle both PDF and EPUB
- Add format detection based on file extension

### Phase 5: Frontend Tree Component
- Build `LibraryTree` component with folder/document/chapter nodes
- Add folder upload button with `webkitdirectory`
- Implement click-to-jump for chapters
- Update LibraryPanel to use new tree

### Phase 6: EPUB Viewer
- Add chapter-based navigation for EPUBs
- Render chapter HTML in "Original" tab
- Handle EPUB-specific metadata display

---

## 14. Browser Compatibility

### 14.1 webkitdirectory Support

| Browser | Support |
|---------|---------|
| Chrome | Full (since v6) |
| Firefox | Full (since v50) |
| Edge | Full (since v14) |
| Safari | Partial (since v11.1) |

**Fallback:** For unsupported browsers, show "Upload individual files" option.

### 14.2 Feature Detection

```typescript
const supportsDirectoryUpload = 'webkitdirectory' in document.createElement('input')

// In component:
{supportsDirectoryUpload ? (
  <button onClick={handleFolderUpload}>Upload Folder</button>
) : (
  <button onClick={handleFileUpload}>Upload Files</button>
)}
```

---

## 15. Library-Agent RAG Integration

This section documents research on Retrieval-Augmented Generation (RAG) techniques for integrating the document library with the agent's query pipeline. The goal is to enable the agent to answer questions about uploaded documents by retrieving relevant chunks and using them as context for Venice.ai LLM responses.

### 15.1 Research Summary (arXiv 2024)

The following papers inform our RAG integration design:

**Core RAG Techniques:**

1. **DR-RAG (arXiv:2406.07348)** - Dynamic Document Relevance for multi-hop QA. Key insight: even documents with low direct relevance to a query can help retrieve other relevant documents when combined with the query. Proposes a two-stage retrieval framework that improves recall while calling the LLM only once for efficiency.

2. **REAR (arXiv:2402.17497)** - Relevance-Aware RAG for open-domain QA. Addresses the problem that LLMs cannot precisely assess relevance of retrieved documents, leading to incorrect utilization of external knowledge. Proposes an assessment module that evaluates document relevance before generation, using bi-granularity relevance fusion.

3. **RQ-RAG (arXiv:2404.00610)** - Learning to Refine Queries. Addresses ambiguous or complex queries that need clarification or decomposition. Equips the model with explicit rewriting, decomposition, and disambiguation capabilities. Achieves 1.9% improvement over SOTA on single-hop QA.

4. **RAIDD (arXiv:2410.03754)** - Retrieval from AI Derived Documents. Proposes deriving inferred features (summaries, example questions) from documents at ingest time, then retrieving against these derived features rather than raw text. Significantly improves performance on subjective QA tasks where the answer isn't directly stated.

**Chunking Strategies:**

5. **Semantic Chunking Analysis (arXiv:2410.13070)** - Evaluates whether semantic chunking is worth the computational cost. Finding: semantic chunking does NOT consistently outperform simple fixed-size chunking across document retrieval, evidence retrieval, and answer generation tasks. Recommendation: use fixed-size chunking (200-500 tokens) with overlap for efficiency unless domain-specific needs justify semantic chunking.

**Agent-RAG Integration:**

6. **GeAR (arXiv:2412.18431)** - Graph-enhanced Agent for RAG. Addresses multi-hop retrieval scenarios where traditional retrievers struggle. Proposes: (i) graph expansion mechanism that augments base retrievers like BM25, and (ii) agent framework for multi-step retrieval. Achieves 10%+ improvement on MuSiQue dataset while consuming fewer tokens.

7. **RAG Survey (arXiv:2409.14924)** - Comprehensive survey on external data integration. Proposes task categorization: explicit fact queries, implicit fact queries, interpretable rationale queries, and hidden rationale queries. Each level requires different retrieval and generation strategies.

8. **RAG Text Generation Survey (arXiv:2404.10981)** - Organizes RAG into four stages: pre-retrieval, retrieval, post-retrieval, and generation. Highlights that RAG provides cost-effective solution to hallucination by grounding responses in real-world data.

### 15.2 Recommended Architecture for CompyMac

Based on the research, we recommend a **tool-based RAG integration** where the agent explicitly calls library search tools rather than automatic context injection:

```
User Query: "What does the Data Science book say about A/B tests?"
    ↓
Agent receives query
    ↓
Agent decides to use library_search tool
    ↓
library_search("A/B tests", top_k=5) → returns relevant chunks
    ↓
Agent incorporates chunks into context
    ↓
Venice.ai generates response with citations
    ↓
User receives grounded answer
```

**Why tool-based over automatic injection?**
- Agent can decide when retrieval is needed (not all queries need library context)
- Explicit tool calls are auditable and debuggable
- Aligns with GeAR's agent framework approach
- Supports multi-step retrieval for complex queries
- Avoids context pollution for non-library queries

### 15.3 Librarian Tools Design

Two tools for agent-library interaction (already implemented in PR #183):

**Tool 1: library_search**
```python
def library_search(
    query: str,
    top_k: int = 5,
    doc_ids: list[str] | None = None,  # Optional: limit to specific documents
    min_score: float = 0.0,
) -> list[dict]:
    """
    Search the document library for chunks relevant to the query.
    
    Returns:
        List of chunks with: id, text, score, doc_id, doc_title, page_num
    """
```

**Tool 2: library_get_chunk**
```python
def library_get_chunk(chunk_id: str) -> dict:
    """
    Get full content of a specific chunk by ID.
    
    Returns:
        Chunk with: id, text, doc_id, doc_title, page_num, metadata
    """
```

### 15.4 Retrieval Strategy

Based on research findings, we recommend:

**Chunking (at ingest time):**
- Fixed-size chunks: 500 tokens with 50-token overlap
- Preserve page boundaries where possible (don't split mid-sentence across pages)
- Store chunk metadata: doc_id, page_num, section_title (from navigation)

**Embedding:**
- Use Venice.ai embedding endpoint (if available) or sentence-transformers
- Store embeddings in vector store (existing hybrid search infrastructure)

**Retrieval (at query time):**
- Hybrid search: combine BM25 keyword matching with vector similarity
- Top-k retrieval with k=5-10 chunks
- Optional: reranking step using LLM relevance scoring (REAR approach)

**Context Assembly:**
- Deduplicate overlapping chunks
- Order by relevance score
- Include source citations (doc title, page number)
- Limit total context to ~2000 tokens to leave room for generation

### 15.5 Implementation Phases

**Phase 1: Wire Librarian Tools to Agent**
- Add `library_search` and `library_get_chunk` to agent's tool registry
- Update system prompt to describe library tools
- Test basic retrieval flow

**Phase 2: Improve Retrieval Quality**
- Implement hybrid search (BM25 + vector)
- Add chunk overlap handling
- Add relevance score thresholding

**Phase 3: Enhanced Features (Optional)**
- Query rewriting for ambiguous queries (RQ-RAG)
- Multi-step retrieval for complex queries (GeAR)
- Derived features at ingest (RAIDD) - summaries, example questions

### 15.6 Evaluation Metrics

To measure RAG quality:
- **Retrieval Recall@k**: % of relevant chunks in top-k results
- **Answer Accuracy**: correctness of generated answers (manual eval)
- **Groundedness**: % of claims that can be traced to retrieved chunks
- **Latency**: time from query to response

### 15.7 Venice.ai Integration Notes

Per project guidelines, CompyMac uses Venice.ai API for LLM hosting. The RAG integration should:
- Use Venice.ai chat completion endpoint for generation
- Pass retrieved chunks as system context or user message prefix
- Request citations in the response format
- Handle rate limits gracefully

---

## 16. Librarian Sub-Agent: Research-Backed Prompt Architecture

This section documents the complete prompt architecture for the Librarian sub-agent, with research backing for each design decision. The Librarian consolidates 6 individual library tools into a single specialist agent, reducing cognitive load on the main agent while maintaining full library functionality.

### 16.1 Research Foundation

The Librarian sub-agent design is informed by the following research:

**Multi-Agent RAG Patterns:**
- **MALADE (arXiv:2408.01869)** - Multi-agent system for RAG with specialized agents. Key insight: domain-specific agents with constrained toolsets outperform general-purpose agents with many tools.
- **Tool-to-Agent Retrieval (arXiv:2511.01854)** - Proposes treating agents and tools in a shared retrieval space. Supports consolidating tools into specialist agents to reduce tool selection complexity.
- **Dynamic Multi-Agent Orchestration (arXiv:2412.17964)** - Demonstrates that specialized agents with focused prompts achieve higher task completion rates than monolithic agents.

**Anti-Hallucination Techniques:**
- **REAR (arXiv:2402.17497)** - Relevance-aware RAG that assesses document relevance before generation. Informs our "evidence-first" approach.
- **Self-RAG (arXiv:2310.11511)** - Self-reflective retrieval that teaches models to critique their own outputs. Informs our "claim-evidence binding" rules.

**Retrieval Discipline:**
- **RQ-RAG (arXiv:2404.00610)** - Query refinement for ambiguous queries. Informs our query decomposition guidance.
- **GeAR (arXiv:2412.18431)** - Graph-enhanced agent for multi-step retrieval. Informs our iterative search with stop conditions.

### 16.2 Prompt Layers Overview

The Librarian operates through three distinct prompt layers, each serving a specific purpose:

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Main Agent System Prompt                               │
│ Purpose: Teach main agent WHEN and HOW to call librarian        │
│ Location: server.py SYSTEM_PROMPT                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Tool Schema Description                                │
│ Purpose: What model sees at tool selection time                 │
│ Location: local_harness.py register_library_tools()             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Librarian System Prompt                                │
│ Purpose: Retrieval discipline, anti-hallucination, output       │
│ Location: librarian_agent.py LIBRARIAN_SYSTEM_PROMPT            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Synthesis Prompt (Optional)                            │
│ Purpose: Answer generation from retrieved excerpts              │
│ Location: librarian_agent.py _synthesize_answer()               │
└─────────────────────────────────────────────────────────────────┘
```

### 16.3 Layer 1: Main Agent System Prompt

**Purpose:** Teach the main agent when to delegate to the librarian and how to interpret results.

**Location:** `src/compymac/api/server.py` - SYSTEM_PROMPT

```
## Document Library Tools

You have access to a document library containing uploaded PDFs and EPUBs. 
Use the `librarian` tool to search and retrieve information. The librarian 
is a specialist agent that handles all library operations.

**Librarian Actions:**
- `list`: List all documents in the library with their IDs and metadata
- `activate`: Activate a document for searching (requires document_id)
- `deactivate`: Remove a document from active search sources (requires document_id)
- `status`: See which documents are currently active for search
- `search`: Search for relevant content across active documents (requires query)
- `get_content`: Get the full content of a specific document or page (requires document_id)
- `answer`: Search and synthesize an answer with citations (requires query)

**Example workflow:**
1. `librarian(action="list")` - see available documents
2. `librarian(action="activate", document_id="...")` - enable a document for search
3. `librarian(action="answer", query="What does the document say about X?")` - get grounded answer with citations

The librarian returns structured JSON with answer, citations, excerpts, and actions_taken.
```

**Research Rationale:**
- Explicit action enumeration reduces tool selection errors (Tool-to-Agent Retrieval)
- Example workflow provides concrete usage pattern (few-shot prompting)
- Structured output description sets expectations for result parsing

### 16.4 Layer 2: Tool Schema Description

**Purpose:** The description field in the tool schema acts as a mini-prompt that the model sees when deciding which tool to call.

**Location:** `src/compymac/local_harness.py` - register_library_tools()

```python
ToolSchema(
    name="librarian",
    description=(
        "A specialist agent for document library operations. "
        "Use this tool to search, list, and retrieve content from uploaded documents (PDFs, EPUBs). "
        "Actions: 'search' (find content), 'list' (show documents), 'get_content' (read document), "
        "'activate'/'deactivate' (control search scope), 'status' (show active sources), "
        "'answer' (search and synthesize answer with citations). "
        "Returns structured JSON with answer, citations, excerpts, and actions_taken."
    ),
    required_params=["action"],
    optional_params=["query", "document_id", "page", "top_k", "user_id"],
    ...
)
```

**Research Rationale:**
- Concise description fits in tool selection context window
- Action list provides quick reference without needing to read full docs
- Output format description helps model anticipate result structure

### 16.5 Layer 3: Librarian System Prompt (Critical)

**Purpose:** This is the core prompt that governs the Librarian's behavior. It establishes retrieval discipline, anti-hallucination rules, and output contract.

**Location:** `src/compymac/ingestion/librarian_agent.py` - LIBRARIAN_SYSTEM_PROMPT

```python
LIBRARIAN_SYSTEM_PROMPT = """You are Librarian, a specialist agent for document retrieval and grounded answers.

Your job is to retrieve and ground answers from the user's document library. You have access to uploaded PDFs and EPUBs that the user has added to their library.

## Your Capabilities

You can:
1. **Search** - Find relevant content across documents using semantic search
2. **List** - Show all available documents in the library
3. **Get Content** - Retrieve full text of specific documents or pages
4. **Activate/Deactivate** - Control which documents are included in searches
5. **Answer** - Search and synthesize answers with citations

## Retrieval Discipline

- Use search first to find relevant content
- Prefer minimal tool calls - retrieve top 5-8 chunks
- Deduplicate overlapping content
- Don't dump full documents unless explicitly asked
- Prefer summaries + pointers over raw text

## Relevance Validation

- Treat retrieved text as evidence
- If evidence is weak or absent, say so clearly
- Propose follow-up queries if initial search is insufficient
- Ask clarifying questions when the query is ambiguous

## Output Contract

Always return structured JSON with:
- `answer`: Your response to the query (or null if just performing an action)
- `citations`: List of {doc_id, doc_title, page_num, chunk_id} for sources used
- `excerpts`: Short quotes from the documents (max 200 chars each)
- `actions_taken`: List of internal tool calls made
- `needs_clarification`: Boolean if query is ambiguous
- `clarifying_question`: Question to ask if clarification needed

## Anti-Hallucination Rules

- NEVER invent citations
- NEVER claim something is in the library unless you have an excerpt
- If you can't find relevant content, say "I couldn't find information about X in the library"
- Always include the source document and page number for claims

## Size Limits

- Keep excerpts under 200 characters each
- Limit answer to 500 words unless more detail is requested
- Return at most 10 citations per response
"""
```

**Research Rationale:**

1. **Role Definition** ("You are Librarian..."):
   - Clear role identity improves task focus (MALADE)
   - Specialist framing reduces scope creep

2. **Retrieval Discipline** (top 5-8 chunks, minimal calls):
   - Based on GeAR finding that focused retrieval outperforms exhaustive retrieval
   - Prevents context pollution and token waste

3. **Relevance Validation** (treat as evidence, propose follow-ups):
   - Inspired by REAR's relevance assessment before generation
   - Reduces hallucination by forcing explicit evidence evaluation

4. **Output Contract** (structured JSON):
   - Machine-parseable output enables verification
   - `actions_taken` field provides audit trail
   - `needs_clarification` enables graceful degradation

5. **Anti-Hallucination Rules**:
   - "Never invent citations" - explicit prohibition (Self-RAG)
   - "Must have excerpt" - claim-evidence binding requirement
   - Abstention template ("I couldn't find...") - reduces gap-filling hallucinations

6. **Size Limits**:
   - Prevents context overflow
   - Forces summarization over raw dumps

### 16.6 Layer 4: Synthesis Prompt

**Purpose:** When the librarian needs to synthesize an answer from retrieved chunks, this prompt governs the generation step.

**Location:** `src/compymac/ingestion/librarian_agent.py` - _synthesize_answer()

```python
synthesis_prompt = f"""Based on the following excerpts from the document library, answer the user's question.
Include citations to the source documents.

User Question: {query}

Document Excerpts:
{context}

Provide a clear, grounded answer based only on the provided excerpts. If the excerpts don't contain enough information, say so."""
```

**Research Rationale:**
- Explicit grounding instruction ("based only on the provided excerpts")
- Citation requirement in prompt
- Abstention instruction ("If excerpts don't contain enough information, say so")
- Separates retrieval from generation (2-pass pattern from RAG literature)

### 16.7 Advanced Prompting Patterns (Future Enhancements)

Based on research, the following patterns could further improve reliability:

**1. Query Decomposition (RQ-RAG inspired):**
```
Before searching, decompose complex queries into 1-3 focused sub-queries.
For each sub-query, search separately, then merge results.
Stop when you have at least 3 independent chunks that agree.
```

**2. Claim-Evidence Binding (Self-RAG inspired):**
```
Every non-trivial claim in your answer must be supported by:
- At least one citation (doc_id, page_num)
- At least one short quote excerpt

If you cannot bind a claim to evidence, you must either:
(a) Omit the claim
(b) Mark it as uncertain
(c) Ask a clarifying question
```

**3. Counterfactual Check:**
```
If excerpts conflict, do not reconcile or average.
Report the disagreement with citations to both sources.
```

**4. Evidence Strength Assessment:**
```
After retrieval, assess evidence strength:
- "strong": Multiple independent sources agree
- "mixed": Sources partially agree or conflict
- "weak": Only tangential mentions found
- "none": No relevant content found

Include this assessment in your response.
```

**5. Structured Retrieval Plan (instead of free-form CoT):**
```json
{
  "subqueries": ["query1", "query2"],
  "filters": {"doc_ids": [...], "min_score": 0.5},
  "stop_criteria": "3+ agreeing chunks or 2 search iterations"
}
```

### 16.8 Output Contract Schema (Detailed)

For maximum reliability, the Librarian returns this structured output:

```python
@dataclass
class LibrarianResult:
    """Structured result from the librarian agent."""
    
    # The synthesized answer (null for action-only requests)
    answer: str | None = None
    
    # Citations with stable identifiers
    citations: list[dict] = field(default_factory=list)
    # Each citation: {doc_id, doc_title, page_num, chunk_id, score}
    
    # Short quotes from source documents (max 200 chars each)
    excerpts: list[str] = field(default_factory=list)
    
    # Audit trail of internal tool calls
    actions_taken: list[str] = field(default_factory=list)
    # Format: ["library_search(query='X', top_k=5)", ...]
    
    # Graceful degradation flags
    needs_clarification: bool = False
    clarifying_question: str | None = None
    
    # Error handling
    error: str | None = None
```

**Research Rationale:**
- `citations` with stable IDs enables verification
- `actions_taken` provides audit trail for debugging
- `needs_clarification` enables graceful degradation
- Separate `error` field for clean error handling

### 16.9 Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Layer 1: Main Agent Prompt | Implemented | server.py |
| Layer 2: Tool Schema | Implemented | local_harness.py |
| Layer 3: Librarian System Prompt | Implemented | librarian_agent.py |
| Layer 4: Synthesis Prompt | Implemented | librarian_agent.py |
| Query Decomposition | Future | - |
| Claim-Evidence Binding | Partial (in prompt) | librarian_agent.py |
| Evidence Strength Assessment | Future | - |

---

## 17. References

- GAP1_INTERACTIVE_UI_DESIGN.md - Overall UI architecture
- PDF_INGESTION_IMPLEMENTATION_PLAN.md - PDF processing pipeline
- PR #184 - OCR provider abstraction
- PR #183 - Librarian tools implementation
- PyMuPDF `get_toc()` - https://pymupdf.readthedocs.io/en/latest/document.html#Document.get_toc
- EbookLib - https://github.com/aerkalov/ebooklib
- webkitdirectory MDN - https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory

**arXiv Papers:**
- DR-RAG: https://arxiv.org/abs/2406.07348
- REAR: https://arxiv.org/abs/2402.17497
- RQ-RAG: https://arxiv.org/abs/2404.00610
- RAIDD: https://arxiv.org/abs/2410.03754
- Semantic Chunking Analysis: https://arxiv.org/abs/2410.13070
- GeAR: https://arxiv.org/abs/2412.18431
- RAG Survey: https://arxiv.org/abs/2409.14924
- RAG Text Generation Survey: https://arxiv.org/abs/2404.10981
- Self-RAG: https://arxiv.org/abs/2310.11511
- MALADE: https://arxiv.org/abs/2408.01869
- Tool-to-Agent Retrieval: https://arxiv.org/abs/2511.01854
- Dynamic Multi-Agent Orchestration: https://arxiv.org/abs/2412.17964
