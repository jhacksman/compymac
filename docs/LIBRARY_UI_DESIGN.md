# Library UI Design Document

## Executive Summary

This document specifies the design for CompyMac's Library tab - a document management interface that allows users to upload, view, and search PDF documents. The key feature is a **dual-view document viewer** that shows both the original scanned page image and the OCR-extracted text side by side (or in tabs).

**Key Design Principles:**
- Original page images must be viewable (not just extracted text)
- OCR text shown separately from original for comparison
- Page-by-page navigation for multi-page documents
- Clear indication of OCR confidence and processing status

---

## 1. Layout Architecture

### 1.1 Library Tab Structure

```
+------------------------------------------------------------------+
|  [Library Tab Header]                           [+ Upload PDF]   |
+------------------------------------------------------------------+
|                    |                                              |
|  DOCUMENT LIST     |  DOCUMENT VIEWER                            |
|  (Left Sidebar)    |                                              |
|                    |  +------------------------------------------+|
|  [Search...]       |  | [< Prev] Page 3 of 13 [Next >]  [Zoom]  ||
|                    |  +------------------------------------------+|
|  - doc1.pdf        |  |                                          ||
|    12 pages        |  |  [Original]  [OCR Text]  [Metadata]      ||
|    Ready           |  |                                          ||
|                    |  |  +--------------------------------------+||
|  - doc2.pdf  [x]   |  |  |                                      |||
|    5 pages         |  |  |   Active Tab Content:                |||
|    Processing...   |  |  |                                      |||
|                    |  |  |   - Original: PDF page as image      |||
|  - doc3.pdf        |  |  |   - OCR Text: Extracted text         |||
|    8 pages         |  |  |   - Metadata: Processing info        |||
|    Ready           |  |  |                                      |||
|                    |  |  +--------------------------------------+||
|                    |  +------------------------------------------+|
+------------------------------------------------------------------+
```

### 1.2 Panel Descriptions

**Document List (Left Sidebar)**
- Scrollable list of uploaded documents
- Each item shows: filename, page count, status (processing/ready/error)
- Click to select and view document
- Delete button (trash icon) on hover
- Search/filter input at top

**Document Viewer (Main Area)**
- **Page Navigation Bar**: Prev/Next buttons, current page indicator, optional zoom
- **View Tabs**: 
  - **Original**: Rendered PDF page as image (from backend endpoint)
  - **OCR Text**: Extracted text for current page (from OCR processing)
  - **Metadata**: Processing info (confidence, OCR method used, timestamps)
- **Content Area**: Displays selected tab content for current page

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

The current classifier uses a 50-character threshold to determine if a page is "digital" or "scanned":

```python
if len(text) >= 50:  # min_chars_per_page
    text_pages.append(page_num + 1)
else:
    scanned_pages.append(page_num + 1)
```

This fails for scanned PDFs with text overlays (stamps, headers) that have 50+ characters of embedded text but the main content is in scanned images.

### 4.2 Improved Classification

Use text density relative to page area, not just character count:

```python
def _classify_pdf(self, doc: "fitz.Document") -> PDFClassification:
    text_pages = []
    scanned_pages = []
    
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
        # - Low text density OR large images = likely scanned
        if text_density > 5 and not has_large_images:
            text_pages.append(page_num + 1)
        elif has_large_images or text_density < 1:
            scanned_pages.append(page_num + 1)
        else:
            # Ambiguous - check if text is just headers/footers
            # by looking at text block positions
            blocks = page.get_text("blocks")
            content_blocks = [b for b in blocks if b[1] > rect.height * 0.1 and b[3] < rect.height * 0.9]
            if len(content_blocks) < 2:
                scanned_pages.append(page_num + 1)
            else:
                text_pages.append(page_num + 1)
    
    # ... rest of classification
```

### 4.3 Force OCR Option

Add parameter to force OCR regardless of classification:

```python
def parse(self, file_path: Path, force_ocr: bool = False) -> ParseResult:
    # If force_ocr, treat all pages as scanned
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

## 8. References

- GAP1_INTERACTIVE_UI_DESIGN.md - Overall UI architecture
- PDF_INGESTION_IMPLEMENTATION_PLAN.md - PDF processing pipeline
- PR #184 - OCR provider abstraction
