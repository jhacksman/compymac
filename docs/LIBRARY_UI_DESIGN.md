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

## 15. References

- GAP1_INTERACTIVE_UI_DESIGN.md - Overall UI architecture
- PDF_INGESTION_IMPLEMENTATION_PLAN.md - PDF processing pipeline
- PR #184 - OCR provider abstraction
- PyMuPDF `get_toc()` - https://pymupdf.readthedocs.io/en/latest/document.html#Document.get_toc
- EbookLib - https://github.com/aerkalov/ebooklib
- webkitdirectory MDN - https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory
