# AI Agent Response Formatting Research

## Executive Summary

This document analyzes how leading AI agents (Manus, Devin, and similar tools) format their responses, along with relevant arxiv research on structured output and UI design patterns. The key finding is that **plain text is insufficient** - modern AI agents use rich, structured formatting with multiple UI components working together.

## Industry Analysis: How Leading Agents Format Responses

### 1. The Dominant UI Design Pattern (Emerge Haus Analysis)

According to the Utterback-Abernathy model of innovation, AI agent interfaces are converging on a **dominant design** with these key characteristics:

**Three-Panel Layout:**
1. **Conversation Panel** (left) - Chat history with rich message formatting
2. **Workspace Panel** (center) - Live view of agent's work (browser, code, terminal)
3. **Status/Todo Panel** (right) - Task progress, plans, and status indicators

**Key Insight:** The shift from simple chatbot interfaces to agent interfaces represents a fundamental change - users don't just chat with agents, they **delegate tasks** and need visibility into execution.

### 2. Manus Response Formatting

Based on the technical analysis of Manus's architecture:

**Message Structure:**
- **Markdown-rich responses** with headers, lists, code blocks
- **Inline citations** with clickable links to sources
- **Progress indicators** showing task completion status
- **File attachments** rendered inline (images, documents)
- **Interactive elements** for user feedback/approval

**Key Features:**
- Uses a **Planner module** that generates visible task lists
- **Knowledge module** injects relevant context as formatted blocks
- **Memory module** maintains state across operations
- Responses include **structured artifacts** (reports, code, data visualizations)

**Output Types:**
1. Plain text explanations
2. Structured data (tables, JSON)
3. Code blocks with syntax highlighting
4. Interactive widgets (forms, buttons)
5. Embedded media (images, charts)
6. Citation chips linking to sources

### 3. Devin Response Formatting

Based on Devin's documentation and API:

**Message Types:**
- **User messages** - Plain text or multimodal input
- **Assistant messages** - Rich formatted responses with tool calls
- **Activity messages** - Structured UI for progress/status (frontend-only)
- **Tool messages** - Results from tool executions

**Key Formatting Features:**
- **Interactive Planning** - Visual task breakdown with checkboxes
- **Code diffs** - Inline display of changes made
- **Terminal output** - Formatted command results
- **Browser screenshots** - Visual proof of web interactions
- **PR links** - Direct links to created pull requests

**Activity Messages (Unique to Devin-style agents):**
```typescript
interface ActivityMessage {
  id: string
  role: "activity"
  activityType: string  // e.g., "PLAN", "SEARCH", "SCRAPE"
  content: Record<string, any>  // Structured payload
}
```

These are **frontend-only** messages that create rich UI without being sent to the LLM.

### 4. AG-UI Protocol (Agent-User Interaction Standard)

The AG-UI protocol defines a vendor-neutral message format:

**Message Roles:**
- `user` - Human input
- `assistant` - AI response
- `system` - Instructions/context
- `tool` - Tool execution results
- `activity` - UI-only structured content
- `developer` - Debug/internal messages

**Streaming Support:**
- `TEXT_MESSAGE_START` - Begin new message
- `TEXT_MESSAGE_CONTENT` - Stream content chunks
- `TEXT_MESSAGE_END` - Complete message
- `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` - Live UI updates

## Arxiv Research Findings

### 1. Generative Interfaces (Stanford, 2025)

**Paper:** "Generative Interfaces for Language Models" (arxiv:2508.19227)

**Key Finding:** LLMs that generate **task-specific UIs** instead of plain text show up to **72% improvement in human preference**.

**Approach:**
- LLM analyzes user query
- Generates appropriate UI component (form, table, chart, etc.)
- User interacts with generated UI
- Iterative refinement based on interaction

**When to Use Generative UI:**
- Multi-turn, information-dense tasks
- Exploratory tasks with unclear goals
- Tasks requiring data visualization
- Complex workflows with multiple steps

### 2. Structured Output Techniques

**Paper:** "SLOT: Structuring the Output of Large Language Models" (arxiv:2505.04016)

**Key Finding:** Fine-tuned models with constrained decoding achieve **99.5% schema accuracy** vs 74.5% for Claude-3.5-Sonnet.

**Approaches:**
1. **Constrained decoding** - Force output to match schema
2. **Post-processing layer** - Transform unstructured to structured
3. **Fine-tuning** - Train model on structured output tasks

### 3. Markdown Awareness in LLMs

**Paper:** "MDEval: Evaluating and Enhancing Markdown Awareness" (arxiv:2501.15000)

**Key Finding:** Markdown formatting significantly impacts readability and user satisfaction in chatbot interfaces.

**Best Practices:**
- Use headers for section organization
- Code blocks with language-specific syntax highlighting
- Tables for structured data comparison
- Bullet/numbered lists for sequential information
- Bold/italic for emphasis on key terms

### 4. Content-Format Integrated Optimization

**Paper:** "Beyond Prompt Content: Enhancing LLM Performance via Content-Format Integrated Prompt Optimization" (arxiv:2502.04295)

**Key Finding:** Jointly optimizing content AND format yields measurable performance improvements over content-only optimization.

### 5. Decoupling Task-Solving from Output Formatting

**Paper:** "Decoupling Task-Solving and Output Formatting in LLM Generation" (arxiv:2510.03595)

**Key Finding:** Separating format compliance from task solving using a tractable probabilistic model (TPM) yields 1-6% relative gains with guaranteed format compliance.

**Approach (Deco-G):**
- LLM focuses on task solving
- Separate TPM handles format compliance
- Combined probability at each decoding step

## Recommendations for CompyMac

Based on this research, here are concrete recommendations:

### 1. Rich Message Formatting

**Current:** Plain text responses
**Recommended:** Markdown with rendered components

```typescript
interface RichMessage {
  id: string
  role: "assistant"
  content: string  // Markdown content
  format: "markdown" | "plain"
  components: UIComponent[]  // Embedded rich components
  citations: Citation[]
  attachments: Attachment[]
}

interface UIComponent {
  type: "code" | "table" | "chart" | "checklist" | "card"
  data: any
  position: "inline" | "block"
}
```

### 2. Activity Messages for Progress

Add frontend-only activity messages for rich progress display:

```typescript
interface ActivityMessage {
  type: "PLAN" | "SEARCH" | "BROWSE" | "CODE" | "COMPLETE"
  title: string
  items?: ChecklistItem[]
  progress?: number
  metadata?: Record<string, any>
}
```

### 3. Citation Chips (Already Implemented)

Continue using citation chips for sources, but enhance with:
- Preview on hover
- Grouped citations by source
- Visual distinction between web/library citations

### 4. Structured Response Templates

For common response types, use templates:

**Research Response:**
```markdown
## Summary
[Brief overview]

## Key Findings
1. [Finding with citation chip]
2. [Finding with citation chip]

## Details
[Expanded content with inline citations]

## Sources
[List of citation chips]
```

**Task Completion Response:**
```markdown
## Task Complete

**What was done:**
- [Action 1]
- [Action 2]

**Results:**
[Embedded component: table/chart/code]

**Next Steps:**
[Optional follow-up suggestions]
```

### 5. Generative UI Components

For specific task types, generate appropriate UI:

| Task Type | UI Component |
|-----------|--------------|
| Data analysis | Interactive table + chart |
| Code review | Diff viewer with comments |
| Research | Expandable sections with citations |
| Planning | Interactive checklist |
| Comparison | Side-by-side cards |

### 6. Streaming with Structure

Implement structured streaming:

```typescript
// Start with structure hint
{ type: "MESSAGE_START", format: "research_report" }

// Stream content sections
{ type: "SECTION_START", name: "summary" }
{ type: "CONTENT", delta: "..." }
{ type: "SECTION_END" }

// Add components as they're ready
{ type: "COMPONENT", component: { type: "table", data: [...] } }

// Complete
{ type: "MESSAGE_END" }
```

### 7. Text Area Formatting Tools

Modern AI agent interfaces provide rich text editing capabilities in the input area, allowing users to format their messages before sending. This follows patterns established by tools like Notion, Slack, and Discord.

**File Upload Button (+):**
A prominent "+" button allows users to attach files directly to their message. For CompyMac, this should support:
- EPUB files (added to library)
- PDF files (added to library)

The button should be positioned at the left edge of the text area for easy access.

**Formatting Toolbar:**
A toolbar above or below the text area provides quick access to common formatting options:

| Icon | Function | Markdown Syntax |
|------|----------|-----------------|
| **B** | Bold | `**text**` |
| *I* | Italic | `*text*` |
| <u>U</u> | Underline | `<u>text</u>` |
| ~~S~~ | Strikethrough | `~~text~~` |
| 🔗 | Link | `[text](url)` |
| 1. | Numbered List | `1. item` |
| • | Bullet List | `- item` |
| ☐ | Task List | `- [ ] item` |
| `</>` | Inline Code | `` `code` `` |
| `{/}` | Code Block | ` ``` ` (fenced code block) |

**Implementation Approach:**
1. Toolbar buttons insert markdown syntax at cursor position
2. Selected text is wrapped with appropriate syntax
3. Preview mode shows rendered markdown before sending
4. Keyboard shortcuts for power users (Ctrl+B, Ctrl+I, etc.)

**User Experience Benefits:**
- Reduces friction for formatting complex messages
- Enables structured input (task lists, code snippets)
- File upload streamlines document ingestion workflow
- Consistent with modern productivity tools

## Implementation Priority

1. **High Priority:**
   - Markdown rendering in frontend (headers, lists, code blocks)
   - Activity messages for progress display
   - Structured response templates
   - Text area formatting toolbar
   - File upload button for EPUB/PDF

2. **Medium Priority:**
   - Generative UI components (tables, charts)
   - Enhanced citation chips with previews
   - Streaming with structure hints

3. **Lower Priority:**
   - Interactive components (forms, buttons)
   - Custom UI generation based on task type
   - Multi-modal response support

## Conclusion

The research clearly shows that **plain text is insufficient** for modern AI agent responses. The industry is converging on rich, structured formatting with:

1. **Markdown as the baseline** - Headers, lists, code blocks, tables
2. **Activity messages** - Frontend-only progress/status UI
3. **Citation chips** - Clickable source references
4. **Embedded components** - Charts, tables, diffs, images
5. **Generative UI** - Task-specific interfaces when appropriate

The key insight from arxiv research is that **format and content should be optimized together**, and that generative interfaces (where the LLM creates appropriate UI) show significant improvements in user preference over plain text.

## References

1. Emerge Haus - "The New Dominant UI Design for AI Agents" (2025)
2. AG-UI Protocol - docs.ag-ui.com
3. Manus Technical Analysis - GitHub Gist by renschni
4. Devin Documentation - docs.devin.ai
5. arxiv:2508.19227 - "Generative Interfaces for Language Models"
6. arxiv:2505.04016 - "SLOT: Structuring the Output of Large Language Models"
7. arxiv:2501.15000 - "MDEval: Evaluating and Enhancing Markdown Awareness"
8. arxiv:2502.04295 - "Content-Format Integrated Prompt Optimization"
9. arxiv:2510.03595 - "Decoupling Task-Solving and Output Formatting"
