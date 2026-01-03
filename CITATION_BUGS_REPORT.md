# Citation Feature Bug Report
**Review of PRs #203-#209 (Phases 1-7)**
**Date: 2026-01-03**

This report documents bugs found across all 7 phases of the citation linking feature implementation.

---

## Phase 1: EPUB Rendering (#203)

### 🔴 CRITICAL: Unused Cache with Memory Leak Potential
**File:** `src/compymac/ingestion/epub_renderer.py:141`
```python
self._epub_cache: dict[str, Any] = {}  # Cache opened EPUBs
```
**Issue:** The `_epub_cache` is initialized but never actually used anywhere in the code. EPUBs are opened fresh each time without caching or cleanup, leading to potential memory leaks.

**Recommendation:** Either implement the cache properly or remove it.

---

### 🟡 MEDIUM: Path Traversal Security Check Could Be Bypassed
**File:** `src/compymac/api/server.py:1874-1877`
```python
upload_dir = Path("/tmp/compymac_uploads").resolve()
file_path_resolved = Path(file_path).resolve()
if not str(file_path_resolved).startswith(str(upload_dir)):
    raise HTTPException(status_code=403, detail="Access denied")
```
**Issue:** While `.resolve()` is called which should handle symlinks, using string comparison with `startswith` could potentially be bypassed in edge cases. Also, this same security check is duplicated across multiple endpoints.

**Recommendation:**
- Extract to a helper function for DRY principle
- Consider using `file_path_resolved.is_relative_to(upload_dir)` (Python 3.9+)

---

### 🟡 MEDIUM: Duplicate File Path Retrieval Logic
**File:** `src/compymac/api/server.py:1861-1866` and `1913-1918`
```python
file_path = doc.metadata.get("file_path")
if not file_path:
    if doc.chunks and doc.chunks[0].get("metadata", {}).get("filepath"):
        file_path = doc.chunks[0]["metadata"]["filepath"]
```
**Issue:** This exact logic is duplicated in both `/epub/chapter` and `/epub/chapters` endpoints.

**Recommendation:** Extract to a helper function.

---

### 🟢 LOW: Missing Image Support
**File:** `src/compymac/ingestion/epub_renderer.py:433-446`
```python
def _rewrite_image_src(...):
    # For now, strips external images and keeps data URIs.
    # TODO: Add image proxy endpoint for EPUB internal images.
```
**Issue:** All images are stripped from EPUB chapters except data URIs, degrading the reading experience.

**Recommendation:** Implement the image proxy endpoint as noted in the TODO.

---

### 🟢 LOW: Basic CSS Sanitization May Miss Complex Attacks
**File:** `src/compymac/ingestion/epub_renderer.py:486-502`
```python
def _sanitize_css(self, css_content: str) -> str:
    """Remove dangerous CSS properties."""
    sanitized = css_content
    for pattern in DANGEROUS_CSS_PROPERTIES:
        sanitized = re.sub(pattern + r'[^;]*;?', '', sanitized, flags=re.IGNORECASE)
    return sanitized
```
**Issue:** Regex-based CSS sanitization is fragile and may not catch all CSS injection vectors (e.g., CSS expressions, @import with encoded URLs, etc.).

**Recommendation:** Use a proper CSS parser library like `tinycss2` for more robust sanitization.

---

## Phase 2: Citation Locator Format (#204)

### 🔴 CRITICAL: Type Inconsistency Between Python and TypeScript
**File:** `src/compymac/types/citation.py:134` vs `web/src/types/citation.ts:71`

Python:
```python
locator: CitationLocator | None = None
```

TypeScript:
```typescript
locator: CitationLocator  // Required, not optional!
```

**Issue:** The Python backend allows `locator` to be `None`, but the TypeScript frontend expects it to always be present. This will cause runtime errors when citations without locators are rendered.

**Recommendation:** Make both optional OR ensure backend always provides a locator.

---

### 🟡 MEDIUM: No Input Validation in Parsers
**File:** `src/compymac/types/citation.py:112-119`
```python
def parse_citation_locator(data: dict) -> CitationLocator | None:
    """Parse a citation locator from a dictionary."""
    locator_type = data.get("type")
    if locator_type == "epub_text":
        return EpubCitationLocator.from_dict(data)
    elif locator_type == "pdf_text":
        return PdfCitationLocator.from_dict(data)
    return None
```
**Issue:** No validation that required fields are present. For example, `PdfCitationLocator.from_dict` will accept a dict without a `page` field, defaulting to page 1, which might not be valid.

**Recommendation:** Add validation to ensure required fields are present and valid.

---

### 🟡 MEDIUM: Invalid Default Values
**File:** `src/compymac/types/citation.py:23`
```python
exact: str = ""
```
**Issue:** An empty string is not a valid TextQuoteSelector. The `exact` field should always contain text.

**Recommendation:** Make this a required field without a default, or validate in `__post_init__`.

---

## Phase 3: Ingestion Pipeline (#205)

### 🔴 CRITICAL: Character Position Gap at Chapter Boundaries
**File:** `src/compymac/ingestion/parsers.py:605-606`
```python
chapters_text.append(chapter_content)
current_pos = chapter_end + 2  # +2 for "\n\n" separator
```
**Issue:** The separator `"\n\n"` creates a 2-character gap between chapters. When a chunk falls in this gap, `find_chapter_for_position` will return `None` because no chapter owns those positions.

**File:** `src/compymac/ingestion/chunker.py:41-45`
```python
if start <= char_pos < end:
    return chapter
```
**Issue:** The boundary check uses `<` for end, so positions exactly at chapter boundaries or in the gaps won't match any chapter.

**Recommendation:** Adjust the boundary logic to handle gaps, or don't add gaps in character positions (track logical positions separately).

---

### 🟡 MEDIUM: Index Inconsistency (0-based vs 1-based)
**File:** `src/compymac/ingestion/parsers.py:574-602`
```python
chapter_count = 0
...
chapter_count += 1  # Now chapter_count = 1, 2, 3...
...
chapter_ranges.append({
    "chapter_index": chapter_count,  # Stores 1, 2, 3... but called "index"
```
**Issue:** The field is called `chapter_index` which implies 0-based indexing, but the values are 1-based (starting from 1).

**Recommendation:** Either use 0-based indexing throughout, or rename to `chapter_number`.

---

### 🟡 MEDIUM: Metadata Dictionary Mutation
**File:** `src/compymac/ingestion/chunker.py:200`
```python
chunk_metadata.pop("chapter_ranges", None)
```
**Issue:** This modifies the dictionary that includes spread `**base_metadata`. While a new dict is created via spread, if base_metadata is reused elsewhere, removing keys could cause subtle bugs.

**Recommendation:** Be more explicit about copying: `chunk_metadata = {**base_metadata}` then mutate.

---

## Phase 4: Librarian Agent Citation Building (#206)

### 🔴 CRITICAL: Wrong Import Path
**File:** `src/compymac/ingestion/librarian_agent.py:26-31`
```python
from compymac.citation_types import (
    Citation,
    EpubCitationLocator,
    PdfCitationLocator,
    TextQuoteSelector,
)
```
**Issue:** The module is located at `compymac.types.citation`, NOT `compymac.citation_types`. This will cause an `ImportError` at runtime.

**Recommendation:** Fix import path to `from compymac.types.citation import ...`

---

### 🔴 CRITICAL: Missing href Validation
**File:** `src/compymac/ingestion/librarian_agent.py:348-351`
```python
if doc_format == "epub":
    return EpubCitationLocator(
        href=metadata.get("href", ""),
        selector=selector,
    )
```
**Issue:** If `metadata` doesn't contain `href` (which can happen if Phase 3's chunking failed or for older documents), the locator will have an empty `href`. Later, when the frontend tries to navigate to this chapter, it will fail.

**Recommendation:** Check if href exists and is non-empty, otherwise fall back or raise an error.

---

### 🟡 MEDIUM: Incorrect Page Metadata
**File:** `src/compymac/ingestion/librarian_agent.py:354-355`
```python
else:
    return PdfCitationLocator(
        page=metadata.get("page", 1),
```
**Issue:** According to Phase 3, chunk metadata contains `chunk_index`, not `page`. The `page` field is only added by the PDF parser for PDF chunks, but this code assumes it's always there.

**Recommendation:** Verify the metadata structure for PDF chunks, or extract page from a different source.

---

### 🟡 MEDIUM: Text Extraction May Split Mid-Word
**File:** `src/compymac/ingestion/librarian_agent.py:310-312`
```python
start = (len(normalized) - target_len) // 2
exact = normalized[start : start + target_len]
```
**Issue:** Extracting a fixed-length substring from the middle can split words, making the text harder to match and less readable.

**Recommendation:** Use word boundaries to extract a more natural text snippet.

---

### 🟢 LOW: Prefix/Suffix Might Be Empty String
**File:** `src/compymac/ingestion/librarian_agent.py:317-323`
```python
prefix = normalized[prefix_start:start].strip() if prefix_start < start else None
suffix = (
    normalized[start + target_len : suffix_end].strip()
    if start + target_len < suffix_end
    else None
)
```
**Issue:** If `.strip()` results in an empty string, it's still assigned (not None). This could lead to empty prefix/suffix in the selector.

**Recommendation:** Check length after stripping: `prefix if prefix else None`

---

## Phase 5: Frontend Citation Rendering (#207)

### 🟡 MEDIUM: Missing Message.citations Parsing
**File:** `web/src/store/session.ts:10`
```typescript
citations?: Citation[]
```
**Issue:** The `Message` interface now includes `citations`, but there's no code shown that actually parses citations from the WebSocket message and adds them to the message object.

**Recommendation:** Ensure the WebSocket handler or message processing logic extracts citations from the backend response.

---

### 🟡 MEDIUM: Memory Leak - No Cleanup for pendingCitationJump
**File:** `web/src/store/session.ts:118`
```typescript
pendingCitationJump: null,
```
**Issue:** The `pendingCitationJump` is set when a citation is clicked, but if the user never opens the library panel or the navigation fails silently, this state is never cleared, potentially accumulating.

**Recommendation:** Add timeout-based cleanup or clear on component unmount.

---

### 🟡 MEDIUM: Race Condition with Multiple Citation Clicks
**File:** `web/src/store/session.ts:277-284`
```typescript
openCitation: (citation: Citation) => {
    const jumpRequest: LibraryJumpRequest = {
      docId: citation.doc_id,
      locator: citation.locator,
      citation,
    }
    set({ pendingCitationJump: jumpRequest })
  },
```
**Issue:** If a user clicks multiple citations rapidly, only the last one will be stored in `pendingCitationJump`. Previous requests are silently lost.

**Recommendation:** Consider using a queue or showing a "citation in progress" state.

---

### 🟢 LOW: No Validation Before Creating Jump Request
**File:** `web/src/store/session.ts:277-284`
**Issue:** Doesn't check if `citation.locator` exists before creating the jump request. Given the Python/TypeScript type mismatch (Phase 2), this could cause errors.

**Recommendation:** Add validation: `if (!citation.locator) return;`

---

## Phase 6: Text Anchoring Algorithm (#208)

### 🔴 CRITICAL: Bitap Algorithm Initialization Bug
**File:** `web/src/utils/textAnchoring.ts:173`
```typescript
patternMask[char] = (patternMask[char] || ~0) & ~(1 << i)
```
**Issue:** The expression `patternMask[char] || ~0` will incorrectly treat `0` as falsy and replace it with `~0`. Since `~0` is `-1` (all bits set), and `0` is a valid bit pattern, this breaks the algorithm for characters that appear multiple times in the pattern.

**Recommendation:** Use nullish coalescing:
```typescript
patternMask[char] = (patternMask[char] ?? ~0) & ~(1 << i)
```

---

### 🔴 CRITICAL: DOM Modification in highlightRange
**File:** `web/src/utils/textAnchoring.ts:350`
```typescript
const fragment = range.extractContents()
mark.appendChild(fragment)
range.insertNode(mark)
```
**Issue:** `extractContents()` **permanently removes** the content from the DOM. This destructively modifies the document structure, not just for highlighting. If cleanup fails, the content is moved permanently.

**Recommendation:** Use `cloneContents()` or a different highlighting strategy that doesn't modify the original DOM structure.

---

### 🟡 MEDIUM: Bitap Match Start Calculation Error
**File:** `web/src/utils/textAnchoring.ts:201`
```typescript
const matchEnd = i + 1
const matchStart = matchEnd - m
```
**Issue:** With fuzzy matching, insertions and deletions mean the actual match length may differ from the pattern length `m`. This calculation assumes exact length, leading to incorrect highlighting bounds.

**Recommendation:** Track actual match bounds during the Bitap algorithm execution.

---

### 🟡 MEDIUM: Text Position Boundary Off-by-One
**File:** `web/src/utils/textAnchoring.ts:119`
```typescript
if (!startNode && currentPos + nodeLength > position.start) {
```
**Issue:** Should use `>=` to handle the case where `position.start` is exactly at a node boundary.

**Recommendation:** Change to `currentPos + nodeLength >= position.start`

---

### 🟡 MEDIUM: Disambiguation Doesn't Check Adjacency
**File:** `web/src/utils/textAnchoring.ts:75-89`
```typescript
const beforeText = text.slice(prefixStart, match.start)
if (beforeText.includes(normalizedPrefix)) {
    score += 1
}
```
**Issue:** This only checks if the prefix appears *somewhere* in the window before the match, not if it's immediately adjacent. This could lead to false positives.

**Recommendation:** Check if the prefix ends exactly at `match.start`:
```typescript
if (beforeText.endsWith(normalizedPrefix)) {
    score += 1
}
```

---

### 🟢 LOW: Short Snippet Always Takes First 50 Chars
**File:** `web/src/utils/textAnchoring.ts:305`
```typescript
const shortExact = exactNormalized.slice(0, 50)
```
**Issue:** Cutting at exactly 50 chars might split in the middle of a word, making matching less reliable.

**Recommendation:** Use word boundaries to extract a more natural snippet.

---

### 🟢 LOW: Memory Leak - Text Nodes Not Normalized After Cleanup
**File:** `web/src/utils/textAnchoring.ts:359-367`
```typescript
return () => {
    const parent = mark.parentNode
    if (parent) {
      while (mark.firstChild) {
        parent.insertBefore(mark.firstChild, mark)
      }
      parent.removeChild(mark)
    }
  }
```
**Issue:** After removing the `<mark>` element and moving its children back, the parent node may have fragmented text nodes. This doesn't cause functional issues but can degrade performance with many highlights.

**Recommendation:** Call `parent.normalize()` after cleanup.

---

## Phase 7: UX Flow Integration (#209)

### 🔴 CRITICAL: Match Navigation Doesn't Actually Navigate
**File:** `web/src/components/workspace/LibraryPanel.tsx:1119-1133`
```typescript
onPrevious={() => {
    if (matchNavigation.currentIndex > 0) {
      setMatchNavigation({
        ...matchNavigation,
        currentIndex: matchNavigation.currentIndex - 1,
      })
    }
  }}
```
**Issue:** The code updates the `currentIndex` but doesn't actually move the highlight to the new match. Looking at line 377 in `anchorAndHighlightInEpub`:
```typescript
setMatchNavigation({
  matches: [{ range: result.range, position: 0 }],  // Only ONE match!
  currentIndex: 0,
  isOpen: true,
  confidence: result.confidence,
})
```
The `matches` array only ever contains a single match (the current one), so navigation is impossible.

**Recommendation:** Store ALL matches from `anchorTextQuote`, then update the highlight when navigating between them.

---

### 🔴 CRITICAL: Duplicate Citation Jump Handling
**File:** `web/src/components/workspace/LibraryPanel.tsx:421-425` and `433-440`
```typescript
// First useEffect (line 421)
useEffect(() => {
    if (!pendingCitationJump) return
    const handleCitationJump = async () => { ... }
    handleCitationJump()
  }, [pendingCitationJump, documents, clearPendingCitationJump, anchorAndHighlightInEpub])

// Second useEffect (line 433)
useEffect(() => {
    if (epubChapter && pendingCitationJump && isEpubLocator(pendingCitationJump.locator)) {
      setTimeout(() => {
        anchorAndHighlightInEpub(pendingCitationJump.locator.selector)
      }, 100)
    }
  }, [epubChapter, pendingCitationJump, anchorAndHighlightInEpub])
```
**Issue:** Two separate `useEffect` hooks both try to handle the citation jump. This can cause:
- Duplicate highlighting attempts
- Race conditions between the two effects
- The second effect runs every time `epubChapter` changes, potentially re-anchoring incorrectly

**Recommendation:** Combine into a single effect with proper state management.

---

### 🔴 CRITICAL: Race Condition with Render Timing
**File:** `web/src/components/workspace/LibraryPanel.tsx:478`
```typescript
setTimeout(() => {
    anchorAndHighlightInEpub(locator.selector)
  }, 100)
```
**Issue:** The 100ms delay is arbitrary and may not be sufficient for slow devices or large EPUB chapters. If the content hasn't fully rendered, anchoring will fail.

**Recommendation:** Use `useLayoutEffect` or a `MutationObserver` to detect when the content is actually rendered.

---

### 🟡 MEDIUM: Memory Leak - No Cleanup on Unmount
**File:** `web/src/components/workspace/LibraryPanel.tsx:359`
```typescript
const [highlightCleanup, setHighlightCleanup] = useState<(() => void) | null>(null)
```
**Issue:** If the component unmounts while a highlight exists, the cleanup function is never called, leaving the highlight in the DOM (if the DOM still exists).

**Recommendation:** Add a cleanup effect:
```typescript
useEffect(() => {
    return () => {
      if (highlightCleanup) highlightCleanup()
    }
  }, [highlightCleanup])
```

---

### 🟡 MEDIUM: State Updates After Unmount
**File:** `web/src/components/workspace/LibraryPanel.tsx:421-511`
```typescript
const handleCitationJump = async () => {
    // ... lots of async operations ...
    setEpubChapter(chapterData)  // Component might be unmounted by now
    setToast({ ... })
  }
```
**Issue:** The async function performs multiple fetches and state updates, but doesn't check if the component is still mounted. This can cause React warnings.

**Recommendation:** Use an `isMounted` ref or AbortController to cancel async operations on unmount.

---

### 🟡 MEDIUM: Potential Infinite Loop
**File:** `web/src/components/workspace/LibraryPanel.tsx:433-440`
```typescript
useEffect(() => {
    if (epubChapter && pendingCitationJump && isEpubLocator(pendingCitationJump.locator)) {
      setTimeout(() => {
        anchorAndHighlightInEpub(pendingCitationJump.locator.selector)
      }, 100)
    }
  }, [epubChapter, pendingCitationJump, anchorAndHighlightInEpub])
```
**Issue:** This effect depends on `pendingCitationJump` but never clears it. If anchoring fails and doesn't clear the pending jump, the effect could re-trigger every time `epubChapter` changes.

**Recommendation:** Clear `pendingCitationJump` after attempting to anchor, or add a flag to track if anchoring was attempted.

---

### 🟡 MEDIUM: Missing Null Check for locator.href
**File:** `web/src/components/workspace/LibraryPanel.tsx:470`
```typescript
const response = await fetch(
    `${API_BASE}/api/documents/${docId}/epub/chapter?href=${encodeURIComponent(locator.href)}`
  )
```
**Issue:** If `locator.href` is undefined or null (from Phase 4 bug), `encodeURIComponent` will stringify it to `"undefined"` or `"null"`, causing a failed fetch.

**Recommendation:** Validate locator.href exists before using it.

---

### 🟢 LOW: Toast Auto-Closes While User May Be Reading
**File:** `web/src/components/workspace/LibraryPanel.tsx:72-75`
```typescript
useEffect(() => {
    const timer = setTimeout(onClose, 5000)
    return () => clearTimeout(timer)
  }, [onClose])
```
**Issue:** Toast messages always auto-close after 5 seconds, even if the user is still reading. For longer messages, this might be too fast.

**Recommendation:** Make timeout configurable based on message length, or require explicit dismissal for error messages.

---

## Summary Statistics

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 CRITICAL | 9 | Bugs that will cause crashes or major functionality breaks |
| 🟡 MEDIUM | 17 | Bugs that cause incorrect behavior or poor UX |
| 🟢 LOW | 7 | Minor issues, missing features, or code quality concerns |
| **TOTAL** | **33** | **Bugs across all 7 phases** |

---

## Priority Fixes

### Must Fix Before Release:
1. **Phase 4**: Fix import path (`compymac.citation_types` → `compymac.types.citation`)
2. **Phase 6**: Fix Bitap algorithm initialization (`||` → `??`)
3. **Phase 6**: Fix highlightRange DOM modification (use non-destructive approach)
4. **Phase 7**: Fix match navigation (store all matches, not just one)
5. **Phase 2**: Fix Python/TypeScript type inconsistency for `locator` field
6. **Phase 3**: Fix character position gaps at chapter boundaries
7. **Phase 7**: Remove duplicate citation jump handling

### Should Fix Soon:
- Phase 4: Validate href exists before creating EPUB locators
- Phase 7: Fix race conditions with setTimeout
- Phase 7: Add proper cleanup on unmount
- Phase 1: Implement or remove unused epub_cache
- All phases: Add proper input validation

### Nice to Have:
- Phase 1: Implement image proxy for EPUB images
- Phase 6: Use word boundaries for text extraction
- Various: Better error messages and user feedback
