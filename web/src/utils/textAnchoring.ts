/**
 * Text Anchoring Algorithm for Citation Linking
 * 
 * Phase 6 of Citation Linking: Implements text anchoring to find and highlight
 * cited text in rendered documents.
 * 
 * Uses a tiered approach:
 * 1. Exact match with normalization
 * 2. Prefix/suffix disambiguation for multiple matches
 * 3. Fuzzy matching (Bitap algorithm) as final fallback
 * 
 * Based on W3C Web Annotation TextQuoteSelector and Hypothesis anchoring.
 */

import type { TextQuoteSelector, AnchorResult } from '@/types/citation'

interface TextPosition {
  start: number
  end: number
}

/**
 * Normalize text for matching by collapsing whitespace and standardizing characters.
 */
export function normalizeText(text: string): string {
  return text
    .replace(/\s+/g, ' ')           // Collapse whitespace
    .replace(/[\u00AD\u200B]/g, '') // Remove soft hyphens, zero-width spaces
    .replace(/['']/g, "'")          // Normalize quotes
    .replace(/[""]/g, '"')          // Normalize double quotes
    .replace(/[–—]/g, '-')          // Normalize dashes
    .trim()
}

/**
 * Find all occurrences of a pattern in text.
 */
function findAllMatches(text: string, pattern: string): TextPosition[] {
  const matches: TextPosition[] = []
  let pos = 0
  
  while (pos < text.length) {
    const index = text.indexOf(pattern, pos)
    if (index === -1) break
    
    matches.push({
      start: index,
      end: index + pattern.length,
    })
    pos = index + 1
  }
  
  return matches
}

/**
 * Disambiguate multiple matches using prefix/suffix context.
 */
function disambiguateWithContext(
  text: string,
  matches: TextPosition[],
  prefix: string | undefined,
  suffix: string | undefined
): TextPosition {
  let bestMatch = matches[0]
  let bestScore = 0
  
  const normalizedPrefix = prefix ? normalizeText(prefix) : ''
  const normalizedSuffix = suffix ? normalizeText(suffix) : ''
  
  for (const match of matches) {
    let score = 0
    
    // Check prefix
    if (normalizedPrefix) {
      const prefixStart = Math.max(0, match.start - normalizedPrefix.length - 10)
      const beforeText = text.slice(prefixStart, match.start)
      if (beforeText.includes(normalizedPrefix)) {
        score += 1
      }
    }
    
    // Check suffix
    if (normalizedSuffix) {
      const suffixEnd = Math.min(text.length, match.end + normalizedSuffix.length + 10)
      const afterText = text.slice(match.end, suffixEnd)
      if (afterText.includes(normalizedSuffix)) {
        score += 1
      }
    }
    
    if (score > bestScore) {
      bestScore = score
      bestMatch = match
    }
  }
  
  return bestMatch
}

/**
 * Convert a text position to a DOM Range.
 */
function textPositionToRange(container: HTMLElement, position: TextPosition): Range | null {
  const range = document.createRange()
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  
  let currentPos = 0
  let startNode: Text | null = null
  let startOffset = 0
  let endNode: Text | null = null
  let endOffset = 0
  
  while (walker.nextNode()) {
    const node = walker.currentNode as Text
    const nodeLength = node.textContent?.length || 0
    
    // Find start node
    if (!startNode && currentPos + nodeLength > position.start) {
      startNode = node
      startOffset = position.start - currentPos
    }
    
    // Find end node
    if (currentPos + nodeLength >= position.end) {
      endNode = node
      endOffset = position.end - currentPos
      break
    }
    
    currentPos += nodeLength
  }
  
  if (!startNode || !endNode) return null
  
  try {
    range.setStart(startNode, startOffset)
    range.setEnd(endNode, endOffset)
    return range
  } catch {
    return null
  }
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
  if (pattern.length === 0) return null
  if (pattern.length > 31) {
    // Bitap is limited to ~31 chars due to bit operations
    // Fall back to simple substring search for longer patterns
    const index = text.indexOf(pattern)
    if (index !== -1) {
      return { start: index, end: index + pattern.length, similarity: 1.0 }
    }
    return null
  }
  
  const maxErrors = Math.floor(pattern.length * (1 - threshold))
  const m = pattern.length
  const n = text.length
  
  // Initialize pattern bitmask
  const patternMask: Record<string, number> = {}
  for (let i = 0; i < m; i++) {
    const char = pattern[i]
    patternMask[char] = (patternMask[char] ?? ~0) & ~(1 << i)
  }
  
  // Initialize state arrays for each error count
  const R: number[] = new Array(maxErrors + 1).fill(~1)
  
  let bestMatch: { start: number; end: number; similarity: number } | null = null
  
  for (let i = 0; i < n; i++) {
    const char = text[i]
    const charMask = patternMask[char] ?? ~0
    
    // Update states from highest error count to lowest
    let oldR = R[0]
    R[0] = (R[0] << 1) | charMask
    
    for (let d = 1; d <= maxErrors; d++) {
      const tmp = R[d]
      // Allow substitution, insertion, deletion
      R[d] = ((R[d] << 1) | charMask) & (oldR << 1) & ((tmp | oldR) << 1) & tmp
      oldR = tmp
    }
    
    // Check for match at each error level
    for (let d = 0; d <= maxErrors; d++) {
      if ((R[d] & (1 << (m - 1))) === 0) {
        const similarity = 1 - (d / m)
        const matchEnd = i + 1
        const matchStart = matchEnd - m
        
        if (!bestMatch || similarity > bestMatch.similarity) {
          bestMatch = { start: matchStart, end: matchEnd, similarity }
        }
        break
      }
    }
  }
  
  return bestMatch
}

/**
 * Fuzzy text matching using Bitap algorithm.
 * Constrained to candidate windows around prefix hits to avoid false positives.
 */
function fuzzyAnchor(
  text: string,
  selector: TextQuoteSelector,
  options: { threshold: number }
): { position: TextPosition; similarity: number } | null {
  const { exact, prefix } = selector
  const normalizedExact = normalizeText(exact)
  
  // Find candidate windows using prefix
  const candidateWindows: Array<{ start: number; end: number }> = []
  if (prefix) {
    const normalizedPrefix = normalizeText(prefix)
    const prefixMatches = findAllMatches(text, normalizedPrefix)
    for (const match of prefixMatches) {
      // Search window: after prefix, up to 2x exact length
      candidateWindows.push({
        start: match.end,
        end: Math.min(text.length, match.end + normalizedExact.length * 2),
      })
    }
  }
  
  // If no prefix or no prefix matches, search entire text
  if (candidateWindows.length === 0) {
    candidateWindows.push({ start: 0, end: text.length })
  }
  
  // Search each candidate window with Bitap
  let bestMatch: { position: TextPosition; similarity: number } | null = null
  for (const window of candidateWindows) {
    const windowText = text.slice(window.start, window.end)
    const result = bitapSearch(windowText, normalizedExact, options.threshold)
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
 * Anchor a TextQuoteSelector in a container element.
 * 
 * Uses a tiered approach:
 * 1. Exact match with normalization
 * 2. Prefix/suffix disambiguation for multiple matches
 * 3. Short snippet fallback (first 50 chars)
 * 4. Fuzzy matching (Bitap algorithm) as final fallback
 */
export function anchorTextQuote(
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
    
    const range = textPositionToRange(container, bestMatch)
    return {
      found: !!range,
      range: range || undefined,
      matchCount: matches.length,
      fallbackUsed: 'none',
      confidence: 1.0,
    }
  }
  
  // Step 4: Fallback - try shorter snippet (first 50 chars)
  if (exactNormalized.length > 50) {
    const shortExact = exactNormalized.slice(0, 50)
    const shortMatches = findAllMatches(textContent, shortExact)
    if (shortMatches.length > 0) {
      const range = textPositionToRange(container, shortMatches[0])
      return {
        found: !!range,
        range: range || undefined,
        matchCount: shortMatches.length,
        fallbackUsed: 'short_snippet',
        confidence: 0.8,
      }
    }
  }
  
  // Step 5: Final fallback - fuzzy matching with Bitap algorithm
  const fuzzyResult = fuzzyAnchor(textContent, selector, { threshold: 0.8 })
  if (fuzzyResult) {
    const range = textPositionToRange(container, fuzzyResult.position)
    return {
      found: !!range,
      range: range || undefined,
      matchCount: 1,
      fallbackUsed: 'fuzzy',
      confidence: fuzzyResult.similarity,
    }
  }
  
  return { found: false, matchCount: 0, fallbackUsed: 'none', confidence: 0 }
}

/**
 * Highlight a DOM Range with a yellow background.
 * Returns a cleanup function to remove the highlight.
 */
export function highlightRange(range: Range): () => void {
  const mark = document.createElement('mark')
  mark.className = 'citation-highlight'
  mark.style.backgroundColor = '#fef08a' // Yellow highlight
  mark.style.padding = '2px 0'
  mark.style.borderRadius = '2px'
  
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

/**
 * Find and highlight text in a container using a TextQuoteSelector.
 * Returns the anchor result and a cleanup function.
 */
export function anchorAndHighlight(
  container: HTMLElement,
  selector: TextQuoteSelector
): { result: AnchorResult; cleanup: (() => void) | null } {
  const result = anchorTextQuote(container, selector)
  
  if (result.found && result.range) {
    const cleanup = highlightRange(result.range)
    return { result, cleanup }
  }
  
  return { result, cleanup: null }
}
