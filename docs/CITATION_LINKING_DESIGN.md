# Citation Linking Design Document

## Overview

This document specifies the design for citation linking in CompyMac's document library. When the AI agent cites a source from the library, users should be able to click the citation and be taken directly to the referenced passage with visual highlighting.

## User Story

> As a user reviewing AI-generated responses with citations, I want to click on a citation and immediately see the exact passage being referenced, so I can verify the source and understand the context.

**Success Metric:** Citation click lands user at the expected location in under 1 second, with unmistakable visual confirmation (yellow highlight for both EPUB and PDF when text search succeeds, page navigation as fallback for PDF).

## Goals and Non-Goals

### Goals

1. **EPUB highlighting**: Click citation → navigate to chapter → highlight exact quoted text
2. **PDF highlighting with fallback**: Click citation → attempt text search and highlight → fall back to page navigation if search fails (e.g., scanned/image-only PDFs)
3. **Graceful degradation**: Clear feedback when exact location cannot be found
4. **Minimal latency**: Sub-second navigation from click to highlighted view

### Non-Goals

1. Cross-document citation linking (linking between documents)
2. Annotation persistence (saving user highlights/notes)
3. EPUB CFI generation at index time (complex, brittle without full reader integration)

## Current Architecture Analysis

### What Exists Today

**LibraryPanel "Original" Tab:**
- Renders documents as PNG images via `/api/documents/{id}/pages/{page}.png`
- Uses PyMuPDF (`fitz`) for PDF rendering
- **EPUB "Original" view is non-functional** - the endpoint only supports PDFs

**Document Ingestion:**
- PDFs: Text extracted with page markers (`--- Page N ---`)
- EPUBs: Text extracted with chapter markers (`--- Chapter N ---`)
- Chunks store `start_char`/`end_char` positions but **not** spine item `href`
- Original EPUB files stored as `.epub` in `/tmp/compymac_uploads/`

**Navigation Extraction:**
- PDFs: Bookmarks extracted with `{type: "pdf_page", page: N}`
- EPUBs: TOC extracted with `{type: "epub_href", href: "chapter1.xhtml"}`

**Librarian Agent Citations:**
- Returns `{doc_id, doc_title, page_num, chunk_id, score}`
- No locator information for text anchoring

### Architectural Gap

EPUBs require a fundamentally different rendering approach than PDFs:

| Aspect | PDF | EPUB |
|--------|-----|------|
| Original view | PNG image (works) | PNG image (broken) |
| Text layer | Embedded or OCR | Native HTML |
| Highlighting | Text search on page (may fail for scanned PDFs) | DOM manipulation (reliable) |
| Navigation unit | Page number | Spine item href |
| Fallback behavior | Page-level navigation if text search fails | Chapter-level navigation if text not found |

## Proposed Solution

### Phase 1: EPUB Original Rendering (Prerequisite)

Before citation linking can work for EPUBs, we must fix the "Original" tab to render actual EPUB content.

**New Endpoint: `/api/documents/{document_id}/epub/chapter`**

```
GET /api/documents/{document_id}/epub/chapter?href={spine_href}

Response:
{
  "status": "ok",
  "html": "<sanitized XHTML content>",
  "title": "Chapter 1",
  "href": "chapter1.xhtml",
  "prev_href": null,
  "next_href": "chapter2.xhtml"
}
```

**Security Requirements:**
- Sanitize HTML (remove `<script>`, `on*` attributes, external resources)
- Validate `href` against EPUB spine (prevent path traversal)
- Strip or inline CSS (avoid external stylesheet loading)
- Rewrite image URLs to safe endpoint or inline as data URIs

**Frontend Changes:**
- Detect `doc_format === 'epub'` in LibraryPanel
- Render chapter HTML in sandboxed container (not iframe for DOM access)
- Add chapter navigation controls (prev/next based on spine order)

### Phase 2: Citation Locator Format

Adopt a W3C Web Annotation-inspired locator format that's resilient to minor text changes.

**TextQuoteSelector Structure:**

```typescript
interface TextQuoteSelector {
  type: 'TextQuoteSelector'
  exact: string      // The quoted text (50-150 chars, from middle of chunk)
  prefix?: string    // 20-30 chars before the quote
  suffix?: string    // 20-30 chars after the quote
}

interface CitationLocator {
  // For EPUB
  type: 'epub_text'
  href: string                    // Spine item href (e.g., "chapter3.xhtml")
  selector: TextQuoteSelector
  
  // For PDF (attempt highlighting, fallback to page navigation)
  type: 'pdf_text'
  page: number                    // Page number for navigation/fallback
  selector: TextQuoteSelector     // For text search and highlighting
}

interface Citation {
  doc_id: string
  doc_title: string
  chunk_id: string
  score: number
  excerpt: string                 // Display text (first 200 chars)
  locator: CitationLocator
}
```

**Why TextQuoteSelector?**
- Used by Hypothesis, W3C Web Annotation, and other robust annotation systems
- Prefix/suffix disambiguate when exact text appears multiple times
- Resilient to minor formatting changes (whitespace, punctuation)
- No dependency on DOM structure or character offsets

### Phase 3: Ingestion Pipeline Changes

**EPUB Chunk Metadata Enhancement:**

Currently, EPUB chunks only have `start_char`/`end_char` in concatenated text. We need to preserve the spine item `href` for each chunk.

```python
# In _parse_with_ebooklib, track href per chapter
for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
    href = item.get_name()  # e.g., "OEBPS/chapter1.xhtml"
    soup = BeautifulSoup(item.get_content(), "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    chapters_text.append({
        "href": href,
        "text": text,
        "start_char": current_pos,
        "end_char": current_pos + len(text),
    })
```

**Chunk Metadata:**
```python
{
    "id": "doc-123-5",
    "content": "...",
    "metadata": {
        "doc_id": "doc-123",
        "chunk_index": 5,
        "format": "epub",
        "href": "OEBPS/chapter3.xhtml",  # NEW
        "chapter_title": "Chapter 3",     # NEW (if available)
    }
}
```

### Phase 4: Librarian Agent Citation Building

**Extract Locator from Search Results:**

```python
def _build_citation_locator(self, chunk: dict, doc_format: str) -> dict:
    """Build a citation locator from a chunk."""
    content = chunk.get("content", "")
    metadata = chunk.get("metadata", {})
    
    # Extract TextQuoteSelector for both formats (used for highlighting)
    selector = self._extract_text_quote_selector(content)
    
    if doc_format == "epub":
        return {
            "type": "epub_text",
            "href": metadata.get("href", ""),
            "selector": selector,
        }
    else:  # PDF - include selector for highlighting, page for fallback
        return {
            "type": "pdf_text",
            "page": metadata.get("page", 1),
            "selector": selector,
        }

def _extract_text_quote_selector(self, content: str, target_len: int = 100) -> dict:
    """Extract a TextQuoteSelector from content."""
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', content.strip())
    
    if len(normalized) <= target_len:
        return {"type": "TextQuoteSelector", "exact": normalized}
    
    # Take from middle to avoid generic start/end text
    start = (len(normalized) - target_len) // 2
    exact = normalized[start:start + target_len]
    
    # Extract prefix/suffix for disambiguation
    prefix_start = max(0, start - 30)
    prefix = normalized[prefix_start:start].strip()
    
    suffix_end = min(len(normalized), start + target_len + 30)
    suffix = normalized[start + target_len:suffix_end].strip()
    
    return {
        "type": "TextQuoteSelector",
        "exact": exact.strip(),
        "prefix": prefix if prefix else None,
        "suffix": suffix if suffix else None,
    }
```

### Phase 5: Frontend Citation Rendering

**Citation Chip Component:**

```tsx
interface CitationChipProps {
  citation: Citation
  index: number
  onClick: (citation: Citation) => void
}

function CitationChip({ citation, index, onClick }: CitationChipProps) {
  return (
    <button
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1 px-2 py-0.5 
                 bg-purple-500/20 text-purple-300 rounded text-xs
                 hover:bg-purple-500/30 transition-colors"
      title={citation.excerpt}
    >
      <BookOpen className="w-3 h-3" />
      [{index + 1}] {citation.doc_title}
    </button>
  )
}
```

**Message Rendering with Citations:**

```tsx
function MessageBubble({ message }: { message: Message }) {
  const { openCitation } = useSessionStore()
  
  return (
    <div className="...">
      <p>{message.content}</p>
      {message.citations && message.citations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {message.citations.map((citation, i) => (
            <CitationChip
              key={citation.chunk_id}
              citation={citation}
              index={i}
              onClick={openCitation}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

### Phase 6: Text Anchoring Algorithm

When a citation is clicked, we need to find and highlight the exact text in the rendered chapter.

**Anchoring Strategy (Hypothesis-inspired):**

```typescript
interface AnchorResult {
  found: boolean
  range?: Range
  matchCount: number
  fallbackUsed: boolean
}

function anchorTextQuote(
  container: HTMLElement,
  selector: TextQuoteSelector
): AnchorResult {
  // Step 1: Normalize container text
  const textContent = normalizeText(container.textContent || '')
  const exactNormalized = normalizeText(selector.exact)
  
  // Step 2: Find all matches of exact text
  const matches = findAllMatches(textContent, exactNormalized)
  
  if (matches.length === 0) {
    // Fallback: try shorter snippets
    const shortExact = exactNormalized.slice(0, 50)
    const shortMatches = findAllMatches(textContent, shortExact)
    if (shortMatches.length > 0) {
      return {
        found: true,
        range: textPositionToRange(container, shortMatches[0]),
        matchCount: shortMatches.length,
        fallbackUsed: true,
      }
    }
    return { found: false, matchCount: 0, fallbackUsed: false }
  }
  
  // Step 3: Disambiguate using prefix/suffix if multiple matches
  let bestMatch = matches[0]
  if (matches.length > 1 && (selector.prefix || selector.suffix)) {
    bestMatch = disambiguateWithContext(
      textContent, matches, selector.prefix, selector.suffix
    )
  }
  
  // Step 4: Convert text position to DOM Range
  const range = textPositionToRange(container, bestMatch)
  
  return {
    found: true,
    range,
    matchCount: matches.length,
    fallbackUsed: false,
  }
}

function normalizeText(text: string): string {
  return text
    .replace(/\s+/g, ' ')           // Collapse whitespace
    .replace(/[\u00AD\u200B]/g, '') // Remove soft hyphens, zero-width spaces
    .trim()
}
```

**Highlighting the Range:**

```typescript
function highlightRange(range: Range): () => void {
  const mark = document.createElement('mark')
  mark.className = 'citation-highlight'
  mark.style.backgroundColor = '#fef08a' // Yellow highlight
  mark.style.padding = '2px 0'
  
  try {
    range.surroundContents(mark)
  } catch {
    // Range spans multiple elements - use alternative approach
    const fragment = range.extractContents()
    mark.appendChild(fragment)
    range.insertNode(mark)
  }
  
  // Scroll into view
  mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
  
  // Return cleanup function
  return () => {
    const parent = mark.parentNode
    if (parent) {
      while (mark.firstChild) {
        parent.insertBefore(mark.firstChild, mark)
      }
      parent.removeChild(mark)
    }
  }
}
```

### Phase 7: UX Flow and State Management

**Session Store Additions:**

```typescript
interface LibraryJumpRequest {
  docId: string
  locator: CitationLocator
  citation: Citation
}

interface SessionState {
  // ... existing state
  libraryJumpRequest: LibraryJumpRequest | null
  activeTab: 'browser' | 'terminal' | 'todos' | 'knowledge' | 'library'
  
  openCitation: (citation: Citation) => void
  clearLibraryJumpRequest: () => void
}
```

**Citation Click Flow:**

```
1. User clicks citation chip in chat
   ↓
2. openCitation(citation) called
   ↓
3. Store sets libraryJumpRequest and activeTab = 'library'
   ↓
4. LibraryPanel detects libraryJumpRequest via useEffect
   ↓
5. LibraryPanel:
   a. Opens document (if not already open)
   b. For EPUB: fetches chapter HTML, renders, anchors text, highlights
   c. For PDF: navigates to page, attempts text search and highlight, falls back to page-only if search fails
   ↓
6. clearLibraryJumpRequest() called
   ↓
7. User sees highlighted passage (EPUB or PDF with text layer) or page (PDF fallback)
```

**Failure States:**

| Scenario | User Feedback |
|----------|---------------|
| EPUB text not found | Toast: "Couldn't locate exact quote. Showing chapter." + scroll to chapter top |
| PDF text search succeeds | Yellow highlight on matched text (same as EPUB) |
| PDF text search fails (scanned/image PDF) | Toast: "Text highlighting unavailable for this PDF. Showing page." + navigate to page |
| Multiple matches found | Highlight first match, show badge: "2 other matches" with navigation arrows |
| PDF page out of range | Toast: "Page not found in document" + show page 1 |
| Document not in library | Toast: "Document no longer available" |

## Security Considerations

### EPUB HTML Sanitization

EPUB content is untrusted HTML. Before rendering:

1. **Remove dangerous elements:** `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`
2. **Remove event handlers:** All `on*` attributes
3. **Sanitize URLs:** Only allow `data:`, relative paths to safe endpoints
4. **Strip external resources:** No external CSS, fonts, or images unless proxied
5. **Use DOMPurify** or similar battle-tested sanitizer

```python
import bleach

ALLOWED_TAGS = [
    'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'a', 'em', 'strong', 'b', 'i', 'u',
    'blockquote', 'pre', 'code', 'br', 'hr', 'img', 'table',
    'thead', 'tbody', 'tr', 'th', 'td', 'figure', 'figcaption',
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

def sanitize_epub_html(html: str, doc_id: str) -> str:
    """Sanitize EPUB HTML for safe rendering."""
    # First pass: bleach
    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    
    # Second pass: rewrite image URLs
    # Convert relative paths to safe endpoint
    clean = re.sub(
        r'src="([^"]+)"',
        lambda m: f'src="/api/documents/{doc_id}/epub/resource?path={quote(m.group(1))}"',
        clean,
    )
    
    return clean
```

### Path Traversal Prevention

```python
def validate_epub_path(epub_path: Path, requested_href: str) -> Path | None:
    """Validate and resolve EPUB internal path safely."""
    # Normalize and resolve
    safe_href = requested_href.lstrip('/')
    
    # Check for traversal attempts
    if '..' in safe_href or safe_href.startswith('/'):
        return None
    
    # Resolve within EPUB
    # (EPUBs are ZIP files - use zipfile to access)
    return safe_href if is_valid_spine_item(epub_path, safe_href) else None
```

## Performance Considerations

### Caching

1. **Chapter HTML cache:** Cache sanitized chapter HTML in memory (LRU, ~50 chapters)
2. **Anchor position cache:** After successful anchor, cache `{selector_hash → text_position}` for instant re-navigation
3. **EPUB extraction cache:** Extract EPUB to temp directory on first access, reuse for subsequent requests

### Lazy Loading

1. Don't extract full EPUB on upload - extract chapters on demand
2. Don't render all chapters - only the requested one
3. Preload adjacent chapters (prev/next) for smooth navigation

## Testing Strategy

### Unit Tests

1. **TextQuoteSelector extraction:** Various content lengths, edge cases
2. **Text anchoring algorithm:** Single match, multiple matches, no match, fallback
3. **HTML sanitization:** XSS vectors, malformed HTML, resource rewriting
4. **Path validation:** Traversal attempts, valid paths, edge cases

### Integration Tests

1. **EPUB chapter endpoint:** Valid href, invalid href, non-existent document
2. **Citation flow:** Upload EPUB → search → get citation → click → verify highlight
3. **PDF flow:** Upload PDF → search → get citation → click → verify page navigation

### Manual Test Cases

1. Upload EPUB with complex formatting (tables, images, nested lists)
2. Search for text that appears multiple times
3. Search for text with special characters (quotes, em-dashes)
4. Click citation for text near chapter boundary
5. Click citation after document has been deleted

## Alternatives Considered

### EPUB CFI (Canonical Fragment Identifier)

**Pros:** Industry standard, precise, sortable, interoperable
**Cons:** Complex to generate correctly, requires full DOM structure at index time, brittle to EPUB modifications

**Decision:** Use TextQuoteSelector for MVP. CFI can be added as optimization layer later (cache CFI after successful anchor).

### epub.js Library

**Pros:** Full-featured EPUB reader, built-in highlighting, CFI support
**Cons:** Large dependency (~200KB), opinionated UI, integration complexity

**Decision:** Build minimal EPUB rendering for MVP. Consider epub.js if users need advanced reader features (pagination, bookmarks, annotations).

### URL Text Fragments (`#:~:text=`)

**Pros:** Browser-native, automatic highlighting via `::target-text` CSS
**Cons:** Requires iframe navigation, inconsistent in SPA contexts, no programmatic control

**Decision:** Not suitable for primary mechanism. Could be used as enhancement for "copy link to citation" feature.

### PDF.js for Advanced PDF Rendering

**Pros:** Full PDF rendering control, text layer access, annotation support
**Cons:** Large dependency, complex integration, overkill for basic text search

**Decision:** Use existing PyMuPDF text extraction + frontend text search for MVP. The current approach (search extracted text on page, highlight if found, fallback to page navigation) is simpler and sufficient. Consider PDF.js only if we need advanced features like annotation persistence or precise coordinate-based highlighting.

## Rollout Plan

### Phase 1: EPUB Original Rendering (Week 1)
- [ ] Add `/api/documents/{id}/epub/chapter` endpoint
- [ ] Add HTML sanitization with bleach/DOMPurify
- [ ] Update LibraryPanel to detect EPUB and render HTML
- [ ] Add chapter navigation (prev/next)

### Phase 2: Ingestion Enhancement (Week 1)
- [ ] Update EPUB parser to preserve `href` in chunk metadata
- [ ] Re-index existing EPUBs (or mark for re-processing)

### Phase 3: Citation Locator (Week 2)
- [ ] Add TextQuoteSelector extraction to librarian agent
- [ ] Update citation format in WebSocket messages
- [ ] Add Citation type to frontend store

### Phase 4: Frontend Integration (Week 2)
- [ ] Add CitationChip component
- [ ] Update MessageBubble to render citations
- [ ] Add libraryJumpRequest state and handlers
- [ ] Implement text anchoring algorithm

### Phase 5: Polish and Testing (Week 3)
- [ ] Add failure state handling and toasts
- [ ] Add multi-match navigation
- [ ] Write tests
- [ ] Performance optimization (caching)

## Open Questions

1. **Re-indexing strategy:** Should existing EPUBs be automatically re-indexed to add `href` metadata, or only new uploads?

2. **Resource handling:** Should EPUB images/CSS be served via proxy endpoint, inlined as data URIs, or stripped entirely?

3. **Highlight persistence:** Should highlights auto-clear after N seconds, or persist until user navigates away?

4. **Mobile UX:** How should citation chips behave on touch devices? Tap to preview, long-press to navigate?

## References

- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [EPUB Canonical Fragment Identifiers](https://idpf.org/epub/linking/cfi/)
- [URL Fragment Text Directives](https://wicg.github.io/scroll-to-text-fragment/)
- [Hypothesis Anchoring](https://github.com/hypothesis/client/tree/main/src/annotator/anchoring)
- [epub.js Highlights Example](https://github.com/futurepress/epub.js/blob/master/examples/highlights.html)
