# PDF Ingestion Implementation Plan for CompyMac

## Executive Summary

This document outlines a comprehensive plan for implementing PDF document upload and ingestion capabilities in CompyMac.

---

## 1. Research Findings

### 1.1 Key Arxiv Papers Reviewed

1. **arXiv:2412.15262** - Advanced ingestion with LLM parsing
2. **arXiv:2410.09871** - Comparative Study of PDF Parsing Tools  
3. **arXiv:2410.13070** - Semantic Chunking Cost Analysis
4. **arXiv:2507.09935** - Hierarchical Text Segmentation
5. **arXiv:2506.10380** - TableRAG Framework

### 1.2 Key Findings

- Recursive token-based chunking (R100-0) offers best performance/cost ratio
- Context enrichment matters more than chunking method
- Keep tables whole - do not chunk them
- Use Venice.ai API for vision (no local VRAM needed)

---

## 2. Library Feature Design

### 2.1 Overview

Library tab alongside Browser, CLI, Todos for per-user document storage.

### 2.2 UI Components

- Library tab with document list and checkboxes
- Upload dialog with "Add to Library" checkbox
- Search within selected documents

### 2.3 Storage Architecture

```
library/{user_id}/{document_id}/
├── original.pdf
├── metadata.json
├── pages/
├── chunks/
├── index/
└── processing_report.json
```

### 2.4 Retrieval Architecture

Query-time retrieval via `library_search()` tool - NOT pre-loading content.

---

## 3. Implementation Phases

### Phase 1: Basic PDF Upload (MVP)
- File upload endpoint
- PyMuPDF text extraction
- Recursive chunking

### Phase 2: Enhanced Extraction
- Document classification
- Table detection
- OCR fallback

### Phase 3: Vision-LLM Integration
- Venice.ai vision API
- Image descriptions

### Phase 4: Vector Storage & Library
- Embeddings
- ChromaDB/FAISS
- Library UI

### Phase 5: Agent Integration
- library_search tool
- Active sources management

---

## 4. Contingency Planning

### 4.1 Per-Page Processing
Fallback chain: Text -> OCR -> Vision -> Retry -> Mark Failed

### 4.2 Large Documents (2000+ pages)
- Stream page-by-page
- Checkpoint after each page
- Resume from last successful

### 4.3 Vision Failures
- Progressive retry (3 attempts)
- Circuit breaker (pause after 5 failures)

---

## 5. Dependencies

Phase 1: pymupdf, python-multipart
Phase 2+: camelot-py, pytesseract
Phase 4+: chromadb, sentence-transformers, faiss-cpu

---

## 6. Memory Budget (128GB Unified RAM)

- sentence-transformers: ~500MB
- Vision-LLM: 0 (Venice.ai API)
- Total local: ~600MB
- Note: CompyMac targets 128GB unified RAM (Apple Silicon), not discrete VRAM
