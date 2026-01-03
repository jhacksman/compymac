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
- Scope and sanitize CSS (see CSS Handling Strategy below)
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

**Anchoring Strategy (Hypothesis-inspired with Fuzzy Fallback):**

The anchoring algorithm uses a tiered approach:
1. **Exact match** with normalization
2. **Prefix/suffix disambiguation** for multiple matches
3. **Fuzzy matching** (Bitap algorithm) as final fallback

```typescript
interface AnchorResult {
  found: boolean
  range?: Range
  matchCount: number
  fallbackUsed: 'none' | 'short_snippet' | 'fuzzy'
  confidence: number  // 0-1, 1 = exact match
}

function anchorTextQuote(
  container: HTMLElement,
  selector: TextQuoteSelector
): AnchorResult {
  // Step 1: Normalize container text
  const textContent = normalizeText(container.textContent || '')
  const exactNormalized = normalizeText(selector.exact)
  
  // Step 2: Find all exact matches
  const matches = findAllMatches(textContent, exactNormalized)
  
  if (matches.length > 0) {
    // Step 3: Disambiguate using prefix/suffix if multiple matches
    let bestMatch = matches[0]
    if (matches.length > 1 && (selector.prefix || selector.suffix)) {
      bestMatch = disambiguateWithContext(
        textContent, matches, selector.prefix, selector.suffix
      )
    }
    
    return {
      found: true,
      range: textPositionToRange(container, bestMatch),
      matchCount: matches.length,
      fallbackUsed: 'none',
      confidence: 1.0,
    }
  }
  
  // Step 4: Fallback - try shorter snippet (first 50 chars)
  const shortExact = exactNormalized.slice(0, 50)
  const shortMatches = findAllMatches(textContent, shortExact)
  if (shortMatches.length > 0) {
    return {
      found: true,
      range: textPositionToRange(container, shortMatches[0]),
      matchCount: shortMatches.length,
      fallbackUsed: 'short_snippet',
      confidence: 0.8,
    }
  }
  
  // Step 5: Final fallback - fuzzy matching with Bitap algorithm
  // Only search around prefix hits to avoid false positives
  const fuzzyResult = fuzzyAnchor(textContent, selector, { threshold: 0.8 })
  if (fuzzyResult) {
    return {
      found: true,
      range: textPositionToRange(container, fuzzyResult.position),
      matchCount: 1,
      fallbackUsed: 'fuzzy',
      confidence: fuzzyResult.similarity,
    }
  }
  
  return { found: false, matchCount: 0, fallbackUsed: 'none', confidence: 0 }
}

/**
 * Fuzzy text matching using Bitap algorithm (same approach as Hypothesis).
 * Constrained to candidate windows around prefix hits to avoid false positives.
 */
function fuzzyAnchor(
  text: string,
  selector: TextQuoteSelector,
  options: { threshold: number }
): { position: TextPosition; similarity: number } | null {
  const { exact, prefix } = selector
  
  // Find candidate windows using prefix
  const candidateWindows: Array<{ start: number; end: number }> = []
  if (prefix) {
    const prefixMatches = findAllMatches(text, normalizeText(prefix))
    for (const match of prefixMatches) {
      // Search window: after prefix, up to 2x exact length
      candidateWindows.push({
        start: match.end,
        end: Math.min(text.length, match.end + exact.length * 2),
      })
    }
  } else {
    // No prefix - search entire text (slower, more false positives)
    candidateWindows.push({ start: 0, end: text.length })
  }
  
  // Search each candidate window with Bitap
  let bestMatch: { position: TextPosition; similarity: number } | null = null
  for (const window of candidateWindows) {
    const windowText = text.slice(window.start, window.end)
    const result = bitapSearch(windowText, normalizeText(exact), options.threshold)
    if (result && (!bestMatch || result.similarity > bestMatch.similarity)) {
      bestMatch = {
        position: {
          start: window.start + result.start,
          end: window.start + result.end,
        },
        similarity: result.similarity,
      }
    }
  }
  
  return bestMatch
}

/**
 * Bitap (shift-or) algorithm for approximate string matching.
 * Returns best match above threshold, or null.
 */
function bitapSearch(
  text: string,
  pattern: string,
  threshold: number
): { start: number; end: number; similarity: number } | null {
  // Implementation uses edit distance with early termination
  // See: https://en.wikipedia.org/wiki/Bitap_algorithm
  const maxErrors = Math.floor(pattern.length * (1 - threshold))
  
  // ... Bitap implementation details ...
  // Returns { start, end, similarity } or null
}

function normalizeText(text: string): string {
  return text
    .replace(/\s+/g, ' ')           // Collapse whitespace
    .replace(/[\u00AD\u200B]/g, '') // Remove soft hyphens, zero-width spaces
    .replace(/['']/g, "'")          // Normalize quotes
    .replace(/[""]/g, '"')          // Normalize double quotes
    .replace(/[–—]/g, '-')          // Normalize dashes
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
| Multiple matches found | Highlight first match, show match navigator (see Multi-Match UX below) |
| PDF page out of range | Toast: "Page not found in document" + show page 1 |
| Document not in library | Toast: "Document no longer available" |
| Fuzzy match used | Subtle indicator: "Approximate match" badge on highlight |

### Multi-Match UX Specification

When the same text appears multiple times in a chapter, users need to navigate between matches.

**Visual Design:**

```
┌─────────────────────────────────────────────────────────┐
│  [Chapter content with highlighted text...]             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ "quoted text here" is highlighted in yellow     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────┐              │
│  │  Match 1 of 3   [←] [→]   [✕ Close]  │  ← Floating │
│  └──────────────────────────────────────┘    navigator │
└─────────────────────────────────────────────────────────┘
```

**Match Navigator Component:**

```tsx
interface MatchNavigatorProps {
  currentMatch: number
  totalMatches: number
  onPrevious: () => void
  onNext: () => void
  onClose: () => void
  confidence?: number  // Show if fuzzy match
}

function MatchNavigator({
  currentMatch,
  totalMatches,
  onPrevious,
  onNext,
  onClose,
  confidence,
}: MatchNavigatorProps) {
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 
                    bg-slate-800 rounded-lg shadow-lg px-4 py-2
                    flex items-center gap-3 text-sm">
      {confidence && confidence < 1 && (
        <span className="text-amber-400 text-xs">
          ~{Math.round(confidence * 100)}% match
        </span>
      )}
      <span className="text-slate-300">
        Match {currentMatch} of {totalMatches}
      </span>
      <div className="flex gap-1">
        <button
          onClick={onPrevious}
          disabled={currentMatch === 1}
          className="p-1 hover:bg-slate-700 rounded disabled:opacity-50"
          title="Previous match (p)"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button
          onClick={onNext}
          disabled={currentMatch === totalMatches}
          className="p-1 hover:bg-slate-700 rounded disabled:opacity-50"
          title="Next match (n)"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
      <button
        onClick={onClose}
        className="p-1 hover:bg-slate-700 rounded"
        title="Close (Escape)"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
```

**Keyboard Shortcuts:**

| Key | Action |
|-----|--------|
| `n` or `→` | Next match |
| `p` or `←` | Previous match |
| `Escape` | Close navigator and clear highlights |
| `1-9` | Jump to match N (if ≤9 matches) |

**State Management:**

```typescript
interface MatchNavigationState {
  matches: Array<{ range: Range; position: number }>
  currentIndex: number
  isOpen: boolean
}

// In session store
matchNavigation: MatchNavigationState | null
setMatchNavigation: (state: MatchNavigationState | null) => void
navigateToMatch: (index: number) => void
```

**Behavior:**
1. On citation click with multiple matches, highlight first match and show navigator
2. Navigator floats at bottom center, doesn't obscure content
3. Previous/next buttons scroll to and highlight the target match
4. Close button clears all highlights and hides navigator
5. Clicking elsewhere in document closes navigator but keeps current highlight
6. Navigator auto-hides after 30 seconds of inactivity

## Security Considerations

### EPUB HTML Sanitization

EPUB content is untrusted HTML. Before rendering:

1. **Remove dangerous elements:** `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`
2. **Remove event handlers:** All `on*` attributes
3. **Sanitize URLs:** Only allow `data:`, relative paths to safe endpoints
4. **Scope and sanitize CSS:** Keep internal styles but scope to container (see CSS Handling Strategy)
5. **Use DOMPurify** or similar battle-tested sanitizer

```python
import bleach
from lxml import html as lxml_html

ALLOWED_TAGS = [
    'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'a', 'em', 'strong', 'b', 'i', 'u',
    'blockquote', 'pre', 'code', 'br', 'hr', 'img', 'table',
    'thead', 'tbody', 'tr', 'th', 'td', 'figure', 'figcaption',
    'style',  # Allow style tags for scoped CSS
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'style'],  # Allow inline styles
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

def sanitize_epub_html(html: str, doc_id: str) -> str:
    """Sanitize EPUB HTML for safe rendering."""
    # Use lxml with recovery mode for malformed HTML tolerance
    try:
        doc = lxml_html.fromstring(html, parser=lxml_html.HTMLParser(recover=True))
    except Exception:
        # Fallback to basic string sanitization if parsing fails
        doc = None
    
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

### CSS Handling Strategy

EPUBs rely heavily on CSS for typography, layout, and readability. Stripping CSS entirely degrades the reading experience. Instead, we scope and sanitize CSS:

**Approach: Scope Internal Styles to Container**

```python
import re
from cssutils import parseStyle, parseStylesheet

def scope_epub_css(css_content: str, container_class: str = "epub-content") -> str:
    """
    Scope EPUB CSS to a container class to prevent style leakage.
    
    Example:
        Input:  "p { margin: 1em; }"
        Output: ".epub-content p { margin: 1em; }"
    """
    # Parse and scope each rule
    scoped_rules = []
    for rule in re.findall(r'([^{]+)\{([^}]+)\}', css_content):
        selector, properties = rule
        # Skip @rules (media queries, font-face, etc.)
        if selector.strip().startswith('@'):
            continue
        # Scope selector
        scoped_selector = f".{container_class} {selector.strip()}"
        scoped_rules.append(f"{scoped_selector} {{ {properties} }}")
    
    return "\n".join(scoped_rules)

# Dangerous CSS properties to strip
DANGEROUS_CSS_PROPERTIES = [
    'position: fixed',
    'position: absolute',
    'z-index',
    'expression(',  # IE CSS expressions
    'javascript:',
    'behavior:',    # IE behaviors
    '-moz-binding', # XBL bindings
]

def sanitize_css(css_content: str) -> str:
    """Remove dangerous CSS properties."""
    sanitized = css_content
    for prop in DANGEROUS_CSS_PROPERTIES:
        sanitized = re.sub(rf'{prop}[^;]*;?', '', sanitized, flags=re.IGNORECASE)
    return sanitized
```

**Frontend Container:**

```tsx
function EpubChapterView({ html, css }: { html: string; css: string }) {
  return (
    <div className="epub-content">
      <style dangerouslySetInnerHTML={{ __html: css }} />
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  )
}
```

**CSS Handling Rules:**
1. **Keep internal stylesheets** from EPUB `<style>` tags
2. **Scope all selectors** to `.epub-content` container class
3. **Strip external resources** (no `@import`, external fonts)
4. **Remove dangerous properties** (fixed positioning, z-index, expressions)
5. **Allow inline styles** but sanitize property values
6. **Override font sizes** with CSS custom properties for accessibility

### Malformed EPUB Tolerance

Real-world EPUBs often contain malformed HTML, proprietary extensions, and quirky formatting. The parser must be tolerant:

**Use lxml with Recovery Mode:**

```python
from lxml import html as lxml_html
from lxml.etree import XMLSyntaxError

def parse_epub_chapter(content: bytes) -> str:
    """
    Parse EPUB chapter content with tolerance for malformed HTML.
    
    Uses lxml's recovery mode which handles:
    - Unclosed tags
    - Invalid nesting
    - Malformed entities
    - Non-standard attributes
    """
    try:
        # Try strict parsing first
        doc = lxml_html.fromstring(content)
    except XMLSyntaxError:
        # Fall back to recovery mode
        parser = lxml_html.HTMLParser(
            recover=True,           # Attempt to recover from errors
            remove_comments=True,   # Strip HTML comments
            remove_pis=True,        # Remove processing instructions
        )
        try:
            doc = lxml_html.fromstring(content, parser=parser)
        except Exception:
            # Last resort: treat as plain text
            return f"<pre>{html.escape(content.decode('utf-8', errors='replace'))}</pre>"
    
    # Extract body content
    body = doc.find('.//body')
    if body is not None:
        return lxml_html.tostring(body, encoding='unicode')
    return lxml_html.tostring(doc, encoding='unicode')
```

**Common EPUB Issues Handled:**

| Issue | Handling |
|-------|----------|
| Unclosed `<p>`, `<div>` tags | lxml auto-closes |
| Invalid nesting (`<p><div>...</div></p>`) | lxml restructures |
| Malformed entities (`&nbsp` without `;`) | lxml recovers |
| Non-UTF8 encoding | Decode with `errors='replace'` |
| Empty/missing body | Fall back to full document |
| Binary content in text nodes | Escape and wrap in `<pre>` |

**Fallback Chain:**

1. Strict lxml parsing
2. lxml with recovery mode
3. BeautifulSoup with `lxml` parser
4. BeautifulSoup with `html.parser` (most lenient)
5. Plain text extraction with HTML escaping

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

### Large Chapter Optimization

For chapters exceeding 50KB of text, text anchoring can become slow. Mitigations:

**Web Worker for Text Search:**

```typescript
// anchoring-worker.ts
self.onmessage = (e: MessageEvent<{
  text: string
  selector: TextQuoteSelector
}>) => {
  const { text, selector } = e.data
  const result = anchorTextQuote(text, selector)
  self.postMessage(result)
}

// Usage in main thread
const worker = new Worker('/anchoring-worker.js')
worker.postMessage({ text: chapterText, selector })
worker.onmessage = (e) => {
  const result = e.data
  if (result.found) {
    highlightRange(result.range)
  }
}
```

**Position Marker Optimization:**

For very long chapters, maintain position markers during parsing:

```python
# During EPUB parsing, add position markers every 10KB
MARKER_INTERVAL = 10_000  # characters

def parse_with_markers(text: str) -> list[dict]:
    """Parse text and create position markers for binary search."""
    markers = []
    for i in range(0, len(text), MARKER_INTERVAL):
        markers.append({
            "offset": i,
            "snippet": text[i:i+100],  # First 100 chars of segment
        })
    return markers
```

**Anchor Position Cache Structure:**

```typescript
interface AnchorCache {
  // Key: hash of (doc_id, selector.exact)
  // Value: cached anchor result
  [key: string]: {
    chapterHref: string
    textOffset: number
    timestamp: number  // For LRU eviction
  }
}

// Cache hit = instant navigation, no re-search needed
const ANCHOR_CACHE_SIZE = 500  // entries
const ANCHOR_CACHE_TTL = 3600_000  // 1 hour
```

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

## Re-indexing Strategy

Existing EPUBs lack `href` metadata in their chunks, which is required for citation linking. We need a migration strategy.

**Recommended Approach: Lazy Re-indexing with Flag**

```python
# Document metadata schema addition
class DocumentMetadata:
    # ... existing fields ...
    needs_reindex: bool = False  # True for pre-migration EPUBs
    index_version: int = 1       # Increment when schema changes

# On feature deployment, mark all existing EPUBs
async def mark_epubs_for_reindex():
    """Mark all existing EPUBs as needing re-indexing."""
    for doc in library_store.list_documents():
        if doc.format == "epub" and doc.index_version < 2:
            doc.needs_reindex = True
            library_store.update_document(doc)

# Lazy re-indexing on citation request
async def get_citation_locator(doc_id: str, chunk_id: str) -> CitationLocator:
    doc = library_store.get_document(doc_id)
    
    if doc.needs_reindex:
        # Re-index on demand
        await reindex_epub(doc)
        doc.needs_reindex = False
        doc.index_version = 2
        library_store.update_document(doc)
    
    # Now chunks have href metadata
    return build_locator_from_chunk(chunk_id)
```

**UI Indicator:**

```tsx
// Show subtle indicator for documents needing re-index
{doc.needs_reindex && (
  <button
    onClick={() => reindexDocument(doc.id)}
    className="text-xs text-amber-400 hover:text-amber-300"
    title="Re-index for improved citation linking"
  >
    <RefreshCw className="w-3 h-3" />
  </button>
)}
```

**Migration Options:**

| Option | Pros | Cons |
|--------|------|------|
| **Lazy (recommended)** | No upfront cost, transparent to user | First citation click is slower |
| **Background job** | Consistent performance | Server load, complexity |
| **Manual button** | User control | Requires user action |
| **On-demand extraction** | No migration needed | Slower every time, no caching |

**Decision:** Use lazy re-indexing. First citation click triggers re-index if needed (~2-5 seconds), then subsequent clicks are instant. Show loading indicator during re-index.

## PDF Rendering and Highlighting Clarification

**Critical Architectural Note:** PDF highlighting depends on the rendering strategy.

### Current State

The "Original" tab renders PDFs as PNG images via `/api/documents/{id}/pages/{page}.png`. PNG images have **no selectable text layer** - you cannot highlight text in an image.

### Highlighting Options

| Approach | Where Highlighting Works | Complexity |
|----------|-------------------------|------------|
| **OCR Text Tab** | Separate "Text" tab with extracted text | Low - already exists |
| **PDF.js Text Layer** | Overlay on "Original" view | High - new dependency |
| **Coordinate Overlay** | Canvas overlay on PNG | Medium - requires OCR coordinates |

**Recommended Approach for MVP:**

1. **PDF "Original" view**: Navigate to correct page only (no highlighting)
2. **PDF "Text" view**: Full text search and highlighting (using DOM-based approach like EPUB)
3. **User feedback**: Toast indicates which view has highlighting

```typescript
// Citation click handler for PDF
function handlePdfCitation(locator: PdfTextLocator) {
  // Navigate to page in Original view
  setCurrentPage(locator.page)
  
  // Attempt text search
  const textContent = await fetchPageText(locator.page)
  const anchorResult = anchorTextQuote(textContent, locator.selector)
  
  if (anchorResult.found) {
    // Switch to Text tab and highlight
    setActiveDocTab('text')
    highlightRange(anchorResult.range)
    toast.success('Showing highlighted text in Text view')
  } else {
    // Stay on Original view, page-only navigation
    toast.info('Showing page (text highlighting unavailable)')
  }
}
```

**Future Enhancement (PDF.js):**

If users need highlighting in the "Original" view, add PDF.js with text layer:

```tsx
// PDF.js integration (future)
import { Document, Page } from 'react-pdf'

function PdfOriginalView({ docId, page, highlight }: Props) {
  return (
    <Document file={`/api/documents/${docId}/pdf`}>
      <Page
        pageNumber={page}
        renderTextLayer={true}  // Enables text selection/highlighting
        customTextRenderer={({ str, itemIndex }) => (
          <span className={shouldHighlight(str) ? 'bg-yellow-200' : ''}>
            {str}
          </span>
        )}
      />
    </Document>
  )
}
```

**Decision for MVP:** Highlight in Text tab, page-only navigation in Original tab. Add PDF.js later if users request Original view highlighting.

## Remaining Open Questions

1. **Highlight persistence:** Should highlights auto-clear after N seconds, or persist until user navigates away?
   - **Recommendation:** Persist until user clicks elsewhere or presses Escape. Auto-clear after 60 seconds of inactivity.

2. **Mobile UX:** How should citation chips behave on touch devices?
   - **Recommendation:** Tap to navigate directly (no preview). Long-press shows tooltip with excerpt.

3. **epub.js Contingency:** When should we switch from custom rendering to epub.js?
   - **Recommendation:** If we encounter >3 EPUB edge cases that require significant workarounds, evaluate epub.js. The 60KB gzipped cost is acceptable if it saves weeks of debugging.

## References

- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [EPUB Canonical Fragment Identifiers](https://idpf.org/epub/linking/cfi/)
- [URL Fragment Text Directives](https://wicg.github.io/scroll-to-text-fragment/)
- [Hypothesis Anchoring](https://github.com/hypothesis/client/tree/main/src/annotator/anchoring)
- [Hypothesis Fuzzy Anchoring Blog](https://web.hypothes.is/blog/fuzzy-anchoring/) - Explains the Bitap algorithm approach
- [epub.js Highlights Example](https://github.com/futurepress/epub.js/blob/master/examples/highlights.html)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [DOMPurify](https://github.com/cure53/DOMPurify) - Battle-tested HTML sanitizer
