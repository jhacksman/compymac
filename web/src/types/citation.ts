/**
 * Citation Locator Types for CompyMac
 * 
 * Phase 2 of Citation Linking: Defines the data structures for locating
 * and highlighting text in documents when citations are clicked.
 * 
 * Based on W3C Web Annotation TextQuoteSelector for resilient text anchoring.
 */

/**
 * TextQuoteSelector - W3C Web Annotation inspired locator format.
 * 
 * Uses exact text with optional prefix/suffix for disambiguation.
 * Resilient to minor formatting changes (whitespace, punctuation).
 */
export interface TextQuoteSelector {
  type: 'TextQuoteSelector'
  /** The quoted text (50-150 chars, typically from middle of chunk) */
  exact: string
  /** 20-30 chars before the quote for disambiguation */
  prefix?: string
  /** 20-30 chars after the quote for disambiguation */
  suffix?: string
}

/**
 * EPUB Citation Locator - for navigating to text in EPUB documents.
 */
export interface EpubCitationLocator {
  type: 'epub_text'
  /** Spine item href (e.g., "chapter3.xhtml" or "OEBPS/chapter3.xhtml") */
  href: string
  /** Text selector for highlighting */
  selector: TextQuoteSelector
}

/**
 * PDF Citation Locator - for navigating to text in PDF documents.
 * 
 * Includes both page number (for fallback navigation) and text selector
 * (for highlighting when text layer is available).
 */
export interface PdfCitationLocator {
  type: 'pdf_text'
  /** Page number for navigation/fallback (1-indexed) */
  page: number
  /** Text selector for highlighting (may fail for scanned PDFs) */
  selector: TextQuoteSelector
}

/**
 * Web Citation Locator - for opening external URLs in a new browser tab.
 * 
 * Used when the agent browses web pages and wants to cite them.
 */
export interface WebCitationLocator {
  type: 'web_url'
  /** The URL to open */
  url: string
  /** Page title for display */
  title: string
  /** ISO timestamp when the page was retrieved */
  retrieved_at: string
}

/**
 * Union type for all citation locator types.
 */
export type CitationLocator = EpubCitationLocator | PdfCitationLocator | WebCitationLocator

/**
 * Full citation with document reference and locator.
 * 
 * Returned by the librarian agent when citing sources.
 */
export interface Citation {
  /** Document UUID */
  doc_id: string
  /** Document title for display */
  doc_title: string
  /** Chunk ID that was matched */
  chunk_id: string
  /** Search relevance score (0-1) */
  score: number
  /** Display excerpt (first 200 chars of chunk) */
  excerpt: string
  /** Locator for navigating to and highlighting the citation */
  locator: CitationLocator
}

/**
 * Result of attempting to anchor text in a document.
 */
export interface AnchorResult {
  /** Whether the text was found */
  found: boolean
  /** DOM Range for the matched text (if found) */
  range?: Range
  /** Number of matches found */
  matchCount: number
  /** Which fallback strategy was used */
  fallbackUsed: 'none' | 'short_snippet' | 'fuzzy'
  /** Confidence score (0-1, 1 = exact match) */
  confidence: number
}

/**
 * Request to jump to a citation in the library panel.
 */
export interface LibraryJumpRequest {
  /** Document to open */
  docId: string
  /** Locator for navigation and highlighting */
  locator: CitationLocator
  /** Full citation for context */
  citation: Citation
}

/**
 * State for navigating between multiple matches.
 */
export interface MatchNavigationState {
  /** All matches found */
  matches: Array<{ range: Range; position: number }>
  /** Current match index (0-based) */
  currentIndex: number
  /** Whether the navigator is visible */
  isOpen: boolean
  /** Confidence of the match (for fuzzy matches) */
  confidence?: number
}

/**
 * Type guard for EPUB locator.
 */
export function isEpubLocator(locator: CitationLocator): locator is EpubCitationLocator {
  return locator.type === 'epub_text'
}

/**
 * Type guard for PDF locator.
 */
export function isPdfLocator(locator: CitationLocator): locator is PdfCitationLocator {
  return locator.type === 'pdf_text'
}

/**
 * Type guard for Web URL locator.
 */
export function isWebLocator(locator: CitationLocator): locator is WebCitationLocator {
  return locator.type === 'web_url'
}
