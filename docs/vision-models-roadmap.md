# Vision Models Roadmap

## Intent: Self-Hosting on GB10 Boards

This document captures the planned vision model architecture for CompyMac when self-hosted on NVIDIA DGX Spark / GB10 boards.

**Hardware Specs:**
- Single GB10: 128GB VRAM
- Dual GB10 (linked): 256GB VRAM

## Primary: OmniParser V2

**Purpose:** UI element detection and labeling with x,y coordinates for browser/interface automation.

**Why OmniParser V2:**
- Microsoft's pure vision-based screen parsing tool that converts UI screenshots to structured format
- Combines fine-tuned YOLOv8 for icon detection + Florence-2 for icon description
- Outputs bounding boxes with x,y coordinates for clickable/actionable regions
- Enables any LLM to become a "computer use" agent without native vision capabilities
- MIT licensed, open source

**Architecture:**
- YOLOv8 model detects interactable UI elements (buttons, links, inputs, etc.)
- Florence-2 generates descriptions for each detected element
- Output: structured JSON with element type, description, and bounding box coordinates

**Use Case in CompyMac:**
- Browser automation: identify clickable elements without relying on DOM/accessibility tree
- Cross-platform UI automation: works on any screenshot regardless of OS/application
- Fallback when devinid attributes are not available

**Resources:**
- HuggingFace: https://huggingface.co/microsoft/OmniParser-v2.0
- GitHub: https://github.com/microsoft/OmniParser
- Paper: arxiv:2408.00203

## Alternative: DeepSeek-OCR

**Purpose:** Token-efficient OCR for document/text extraction from images.

**Why DeepSeek-OCR:**
- 3B parameter vision-language model optimized for OCR
- Context optical compression: maps large 2D visual contexts into compressed vision tokens
- Handles tables, charts, handwriting, math, multilingual text
- Available via Ollama (6.7GB model size)
- MIT licensed

**Use Case in CompyMac:**
- Extract text from screenshots when needed
- Parse documents, receipts, code snippets from images
- Complement to OmniParser (OCR for text vs OmniParser for UI elements)

**Resources:**
- GitHub: https://github.com/deepseek-ai/DeepSeek-OCR
- Ollama: https://ollama.com/library/deepseek-ocr

## Current State (Venice.ai)

While self-hosting is not yet available, CompyMac uses Venice.ai's `mistral-31-24b` model for vision tasks. This model has `supportsVision: true` and serves as a temporary solution for visual_checker functionality.

## VRAM Budget

**Single GB10 (128GB VRAM):**

| Model | Estimated VRAM | Purpose |
|-------|----------------|---------|
| OmniParser V2 (YOLOv8 + Florence-2) | ~4-8GB | UI element detection |
| DeepSeek-OCR | ~7GB | Text extraction |
| Primary LLM (full precision) | ~80-100GB | Agent reasoning |
| **Total** | **~95-115GB** | Within 128GB budget |

**Dual GB10 Linked (256GB VRAM):**

With 256GB available, we can run larger models or multiple concurrent agents without model swapping.

| Model | Estimated VRAM | Purpose |
|-------|----------------|---------|
| OmniParser V2 (YOLOv8 + Florence-2) | ~4-8GB | UI element detection |
| DeepSeek-OCR | ~7GB | Text extraction |
| Primary LLM (large, full precision) | ~150-200GB | Agent reasoning |
| **Total** | **~165-215GB** | Within 256GB budget |

Note: Exact VRAM usage depends on quantization and batch size. With 128GB+ headroom, model swapping is less critical but may still be useful for optimizing latency.

## Implementation Notes

- OmniParser V2 and DeepSeek-OCR are external services/models, not local PyTorch implementations
- Memory system should be implemented as a client to these services
- Consider model swapping strategy if VRAM is tight (load OmniParser only during browser automation)
