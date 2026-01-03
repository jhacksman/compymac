"""
Librarian Sub-Agent - A specialist agent for document library operations.

This module implements a single "librarian" tool that acts as a sub-agent with:
- Its own specialized system prompt for RAG/document retrieval
- Access to private library tools (search, get_content, list, activate/deactivate)
- Structured output with answer, citations, excerpts, and actions_taken

Based on research:
- MALADE (arXiv:2408.01869): Multi-agent RAG with specialized agents
- Tool-to-Agent Retrieval (arXiv:2511.01854): Agents and tools in shared space
- Dynamic Multi-Agent Orchestration (arXiv:2412.17964): Specialized agents for retrieval
- LIBRARY_UI_DESIGN.md Section 15: Tool-based RAG integration

The librarian tool reduces cognitive load on the main agent by consolidating
6 individual library tools into a single entry point.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from compymac.citation_types import (
    Citation,
    EpubCitationLocator,
    PdfCitationLocator,
    TextQuoteSelector,
)

if TYPE_CHECKING:
    from compymac.llm import LLMClient
    from compymac.storage.library_store import LibraryStore

logger = logging.getLogger(__name__)


class LibrarianAction(Enum):
    """Actions the librarian can perform."""
    SEARCH = "search"  # Search for content matching a query
    LIST = "list"  # List all documents in the library
    GET_CONTENT = "get_content"  # Get full content of a document/page
    ACTIVATE = "activate"  # Activate a document for search
    DEACTIVATE = "deactivate"  # Deactivate a document from search
    STATUS = "status"  # Get status of active sources
    ANSWER = "answer"  # Search and synthesize an answer with citations


LIBRARIAN_SYSTEM_PROMPT = """You are Librarian, a specialist agent for document retrieval and grounded answers.

Your job is to retrieve and ground answers from the user's document library. You have access to uploaded PDFs and EPUBs that the user has added to their library.

## Your Capabilities

You can:
1. **Search** - Find relevant content across documents using semantic search
2. **List** - Show all available documents in the library
3. **Get Content** - Retrieve full text of specific documents or pages
4. **Activate/Deactivate** - Control which documents are included in searches
5. **Answer** - Search and synthesize answers with citations

## Retrieval Discipline

- Use search first to find relevant content
- Prefer minimal tool calls - retrieve top 5-8 chunks
- Deduplicate overlapping content
- Don't dump full documents unless explicitly asked
- Prefer summaries + pointers over raw text

## Relevance Validation

- Treat retrieved text as evidence
- If evidence is weak or absent, say so clearly
- Propose follow-up queries if initial search is insufficient
- Ask clarifying questions when the query is ambiguous

## Output Contract

Always return structured JSON with:
- `answer`: Your response to the query (or null if just performing an action)
- `citations`: List of {doc_id, doc_title, page_num, chunk_id} for sources used
- `excerpts`: Short quotes from the documents (max 200 chars each)
- `actions_taken`: List of internal tool calls made
- `needs_clarification`: Boolean if query is ambiguous
- `clarifying_question`: Question to ask if clarification needed

## Anti-Hallucination Rules

- NEVER invent citations
- NEVER claim something is in the library unless you have an excerpt
- If you can't find relevant content, say "I couldn't find information about X in the library"
- Always include the source document and page number for claims

## Size Limits

- Keep excerpts under 200 characters each
- Limit answer to 500 words unless more detail is requested
- Return at most 10 citations per response
"""


@dataclass
class LibrarianResult:
    """Structured result from the librarian agent."""
    answer: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    excerpts: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "excerpts": self.excerpts,
            "actions_taken": self.actions_taken,
            "needs_clarification": self.needs_clarification,
            "clarifying_question": self.clarifying_question,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class LibrarianAgent:
    """
    A specialist sub-agent for document library operations.

    This agent has its own system prompt and access to private library tools.
    It's called by the main agent through a single "librarian" tool, reducing
    tool overload while maintaining full library functionality.
    """

    def __init__(
        self,
        library_store: "LibraryStore",
        session_id: str,
        llm_client: "LLMClient | None" = None,
    ):
        """
        Initialize the librarian agent.

        Args:
            library_store: The LibraryStore instance for document access
            session_id: Session ID for source activation tracking
            llm_client: Optional LLM client for answer synthesis
        """
        self.library_store = library_store
        self.session_id = session_id
        self.llm_client = llm_client
        self._actions_taken: list[str] = []

    def _log_action(self, action: str) -> None:
        """Log an internal action."""
        self._actions_taken.append(action)
        logger.debug(f"[Librarian] {action}")

    def _search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search for relevant content across documents."""
        self._log_action(f"library_search(query='{query}', top_k={top_k})")

        # Get active sources for this session
        active_docs = self.library_store.get_active_sources(self.session_id)
        doc_ids = [doc.id for doc in active_docs] if active_docs else None

        results = self.library_store.search_chunks(
            query=query,
            doc_ids=doc_ids,
            top_k=top_k,
        )

        return results or []

    def _list_documents(self, user_id: str = "default") -> list[dict[str, Any]]:
        """List all documents in the library."""
        self._log_action(f"library_list(user_id='{user_id}')")

        docs = self.library_store.get_user_documents(user_id)

        if not docs:
            return []

        return [
            {
                "id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
                "page_count": doc.page_count,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "library_path": getattr(doc, 'library_path', ''),
                "doc_format": getattr(doc, 'doc_format', 'pdf'),
            }
            for doc in docs
        ]

    def _get_content(
        self,
        document_id: str,
        page: int | None = None,
    ) -> dict[str, Any]:
        """Get the content of a specific document or page."""
        self._log_action(f"library_get_content(document_id='{document_id}', page={page})")

        doc = self.library_store.get_document(document_id)
        if not doc:
            return {"error": f"Document not found: {document_id}"}

        if not doc.chunks:
            return {"error": f"Document has no content: {doc.title}"}

        # Filter by page if specified
        if page is not None:
            chunks = [
                c for c in doc.chunks
                if c.get("metadata", {}).get("page") == page
            ]
            if not chunks:
                return {"error": f"No content found for page {page}"}
        else:
            chunks = doc.chunks

        # Combine chunk content
        content = "\n\n".join(c.get("content", "") for c in chunks)

        return {
            "document_id": document_id,
            "title": doc.title,
            "page": page,
            "chunk_count": len(chunks),
            "content": content[:10000],  # Limit content size
            "truncated": len(content) > 10000,
        }

    def _activate_source(self, document_id: str) -> dict[str, Any]:
        """Activate a document as a source for search."""
        self._log_action(f"library_activate_source(document_id='{document_id}')")

        doc = self.library_store.get_document(document_id)
        if not doc:
            return {"error": f"Document not found: {document_id}"}

        success = self.library_store.add_active_source(self.session_id, document_id)
        if success:
            return {"success": True, "message": f"Activated source: {doc.title}"}
        else:
            return {"error": f"Failed to activate source: {document_id}"}

    def _deactivate_source(self, document_id: str) -> dict[str, Any]:
        """Deactivate a document as a source for search."""
        self._log_action(f"library_deactivate_source(document_id='{document_id}')")

        doc = self.library_store.get_document(document_id)
        if not doc:
            return {"error": f"Document not found: {document_id}"}

        success = self.library_store.remove_active_source(self.session_id, document_id)
        if success:
            return {"success": True, "message": f"Deactivated source: {doc.title}"}
        else:
            return {"error": f"Source was not active: {document_id}"}

    def _get_active_sources(self) -> list[dict[str, Any]]:
        """Get list of currently active source documents."""
        self._log_action("library_get_active_sources()")

        active_docs = self.library_store.get_active_sources(self.session_id)

        if not active_docs:
            return []

        return [
            {
                "id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
            }
            for doc in active_docs
        ]

    def _extract_text_quote_selector(
        self,
        content: str,
        target_len: int = 100,
    ) -> TextQuoteSelector:
        """
        Extract a TextQuoteSelector from content.

        Phase 4 Citation Linking: Creates a text anchor for highlighting
        the cited text in the source document.

        Args:
            content: The chunk content to extract selector from
            target_len: Target length for the exact match text

        Returns:
            TextQuoteSelector with exact text and optional prefix/suffix
        """
        normalized = re.sub(r"\s+", " ", content.strip())

        if len(normalized) <= target_len:
            return TextQuoteSelector(exact=normalized)

        start = (len(normalized) - target_len) // 2
        exact = normalized[start : start + target_len]

        prefix_start = max(0, start - 30)
        prefix = normalized[prefix_start:start].strip() if prefix_start < start else None

        suffix_end = min(len(normalized), start + target_len + 30)
        suffix = (
            normalized[start + target_len : suffix_end].strip()
            if start + target_len < suffix_end
            else None
        )

        return TextQuoteSelector(
            exact=exact.strip(),
            prefix=prefix if prefix else None,
            suffix=suffix if suffix else None,
        )

    def _build_citation_locator(
        self,
        chunk: dict[str, Any],
        doc_format: str,
    ) -> EpubCitationLocator | PdfCitationLocator:
        """
        Build a citation locator from a chunk.

        Phase 4 Citation Linking: Creates a locator that can be used
        to navigate to and highlight the cited text in the source document.

        Args:
            chunk: The search result chunk with content and metadata
            doc_format: Document format ("epub" or "pdf")

        Returns:
            EpubCitationLocator or PdfCitationLocator
        """
        content = chunk.get("content", chunk.get("text", ""))
        metadata = chunk.get("metadata", {})
        selector = self._extract_text_quote_selector(content)

        if doc_format == "epub":
            return EpubCitationLocator(
                href=metadata.get("href", ""),
                selector=selector,
            )
        else:
            return PdfCitationLocator(
                page=metadata.get("page", 1),
                selector=selector,
            )

    def _build_citations(
        self,
        search_results: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Build citations and excerpts from search results.

        Phase 4 Citation Linking: Now includes locators for each citation
        to enable navigation and highlighting in source documents.
        """
        citations = []
        excerpts = []

        for result in search_results[:10]:
            metadata = result.get("metadata", {})
            content = result.get("content", result.get("text", ""))
            doc_format = metadata.get("format", "pdf")

            locator = self._build_citation_locator(result, doc_format)

            citation = Citation(
                doc_id=result.get("doc_id", ""),
                doc_title=result.get("doc_title", ""),
                chunk_id=result.get("chunk_id", result.get("id", "")),
                score=result.get("score", 0.0),
                excerpt=content[:200].strip() + ("..." if len(content) > 200 else ""),
                locator=locator,
            )
            citations.append(citation.to_dict())

            if content:
                excerpt = content[:200].strip()
                if len(content) > 200:
                    excerpt += "..."
                excerpts.append(excerpt)

        return citations, excerpts

    def _synthesize_answer(
        self,
        query: str,
        search_results: list[dict[str, Any]],
    ) -> str:
        """Synthesize an answer from search results using LLM."""
        if not self.llm_client:
            # Without LLM, just return a summary of results
            if not search_results:
                return f"I couldn't find information about '{query}' in the library."

            result_summary = []
            for i, result in enumerate(search_results[:5], 1):
                doc_title = result.get("doc_title", "Unknown")
                page = result.get("page", result.get("metadata", {}).get("page", "?"))
                content = result.get("content", result.get("text", ""))[:150]
                result_summary.append(f"{i}. From '{doc_title}' (page {page}): {content}...")

            return f"Found {len(search_results)} relevant results for '{query}':\n\n" + "\n\n".join(result_summary)

        # Build context from search results
        context_parts = []
        for result in search_results[:5]:
            doc_title = result.get("doc_title", "Unknown")
            page = result.get("page", result.get("metadata", {}).get("page", "?"))
            content = result.get("content", result.get("text", ""))
            context_parts.append(f"[From '{doc_title}', page {page}]\n{content}")

        context = "\n\n---\n\n".join(context_parts)

        # Use LLM to synthesize answer
        synthesis_prompt = f"""Based on the following excerpts from the document library, answer the user's question.
Include citations to the source documents.

User Question: {query}

Document Excerpts:
{context}

Provide a clear, grounded answer based only on the provided excerpts. If the excerpts don't contain enough information, say so."""

        try:
            from compymac.types import Message

            response = self.llm_client.chat(
                messages=[
                    Message(role="system", content=LIBRARIAN_SYSTEM_PROMPT),
                    Message(role="user", content=synthesis_prompt),
                ],
                temperature=0.0,
            )

            if response.content:
                return response.content
            else:
                return f"Found {len(search_results)} results but couldn't synthesize an answer."
        except Exception as e:
            logger.warning(f"LLM synthesis failed: {e}")
            return f"Found {len(search_results)} results. (Synthesis unavailable: {e})"

    def execute(
        self,
        action: str,
        query: str | None = None,
        document_id: str | None = None,
        page: int | None = None,
        top_k: int = 5,
        user_id: str = "default",
    ) -> LibrarianResult:
        """
        Execute a librarian action.

        Args:
            action: The action to perform (search, list, get_content, activate, deactivate, status, answer)
            query: Search query (required for search/answer actions)
            document_id: Document ID (required for get_content, activate, deactivate)
            page: Page number (optional for get_content)
            top_k: Number of results to return (for search/answer)
            user_id: User ID for listing documents

        Returns:
            LibrarianResult with answer, citations, excerpts, and actions_taken
        """
        self._actions_taken = []  # Reset actions for this execution
        result = LibrarianResult()

        try:
            action_enum = LibrarianAction(action.lower())
        except ValueError:
            result.error = f"Unknown action: {action}. Valid actions: {[a.value for a in LibrarianAction]}"
            return result

        try:
            if action_enum == LibrarianAction.LIST:
                docs = self._list_documents(user_id)
                if docs:
                    result.answer = f"Found {len(docs)} documents in the library:\n" + "\n".join(
                        f"- {d['title']} (ID: {d['id']}, {d['page_count']} pages, status: {d['status']})"
                        for d in docs
                    )
                else:
                    result.answer = "No documents in library. Upload documents via the Library tab in the UI."

            elif action_enum == LibrarianAction.STATUS:
                active = self._get_active_sources()
                if active:
                    result.answer = f"{len(active)} active sources:\n" + "\n".join(
                        f"- {s['title']} (ID: {s['id']})"
                        for s in active
                    )
                else:
                    result.answer = "No active sources. Use 'activate' action with a document_id to enable documents for search."

            elif action_enum == LibrarianAction.ACTIVATE:
                if not document_id:
                    result.error = "document_id is required for activate action"
                else:
                    activate_result = self._activate_source(document_id)
                    if "error" in activate_result:
                        result.error = activate_result["error"]
                    else:
                        result.answer = activate_result["message"]

            elif action_enum == LibrarianAction.DEACTIVATE:
                if not document_id:
                    result.error = "document_id is required for deactivate action"
                else:
                    deactivate_result = self._deactivate_source(document_id)
                    if "error" in deactivate_result:
                        result.error = deactivate_result["error"]
                    else:
                        result.answer = deactivate_result["message"]

            elif action_enum == LibrarianAction.GET_CONTENT:
                if not document_id:
                    result.error = "document_id is required for get_content action"
                else:
                    content_result = self._get_content(document_id, page)
                    if "error" in content_result:
                        result.error = content_result["error"]
                    else:
                        result.answer = content_result.get("content", "")
                        result.citations = [{
                            "doc_id": document_id,
                            "doc_title": content_result.get("title", ""),
                            "page_num": page,
                            "chunk_id": None,
                        }]

            elif action_enum == LibrarianAction.SEARCH:
                if not query:
                    result.error = "query is required for search action"
                else:
                    search_results = self._search(query, top_k)
                    if search_results:
                        citations, excerpts = self._build_citations(search_results)
                        result.citations = citations
                        result.excerpts = excerpts
                        result.answer = f"Found {len(search_results)} results for '{query}'."
                    else:
                        # Check if there are active sources
                        active = self._get_active_sources()
                        if not active:
                            result.answer = f"No results for '{query}'. No documents are currently active. Use 'list' to see available documents, then 'activate' to enable them for search."
                            result.needs_clarification = True
                            result.clarifying_question = "Would you like me to list available documents?"
                        else:
                            result.answer = f"No results found for '{query}' in {len(active)} active documents."

            elif action_enum == LibrarianAction.ANSWER:
                if not query:
                    result.error = "query is required for answer action"
                else:
                    search_results = self._search(query, top_k)
                    if search_results:
                        citations, excerpts = self._build_citations(search_results)
                        result.citations = citations
                        result.excerpts = excerpts
                        result.answer = self._synthesize_answer(query, search_results)
                    else:
                        active = self._get_active_sources()
                        if not active:
                            result.answer = f"I couldn't find information about '{query}' because no documents are active. Use 'list' to see available documents, then 'activate' to enable them."
                            result.needs_clarification = True
                            result.clarifying_question = "Would you like me to list available documents?"
                        else:
                            result.answer = f"I couldn't find information about '{query}' in the {len(active)} active documents."

        except Exception as e:
            logger.exception(f"Librarian action failed: {e}")
            result.error = str(e)

        result.actions_taken = self._actions_taken
        return result


def create_librarian_tool_handler(
    library_store: "LibraryStore",
    session_id: str,
    llm_client: "LLMClient | None" = None,
):
    """
    Create a handler function for the librarian tool.

    This returns a function that can be registered as a tool handler
    in the LocalHarness.

    Args:
        library_store: The LibraryStore instance
        session_id: Session ID for source tracking
        llm_client: Optional LLM client for answer synthesis

    Returns:
        A handler function for the librarian tool
    """
    agent = LibrarianAgent(library_store, session_id, llm_client)

    def librarian_handler(
        action: str,
        query: str | None = None,
        document_id: str | None = None,
        page: int | None = None,
        top_k: int = 5,
        user_id: str = "default",
    ) -> str:
        """
        Librarian tool handler.

        A specialist agent for document library operations. Use this tool to:
        - Search for content in uploaded documents
        - List available documents
        - Get full content of documents
        - Activate/deactivate documents for search
        - Get grounded answers with citations

        Args:
            action: The action to perform. One of:
                - "search": Search for content matching a query
                - "list": List all documents in the library
                - "get_content": Get full content of a document/page
                - "activate": Activate a document for search
                - "deactivate": Deactivate a document from search
                - "status": Get status of active sources
                - "answer": Search and synthesize an answer with citations
            query: Search query (required for search/answer actions)
            document_id: Document ID (required for get_content, activate, deactivate)
            page: Page number (optional for get_content)
            top_k: Number of results to return (default: 5)
            user_id: User ID for listing documents (default: "default")

        Returns:
            JSON string with answer, citations, excerpts, and actions_taken
        """
        result = agent.execute(
            action=action,
            query=query,
            document_id=document_id,
            page=page,
            top_k=top_k,
            user_id=user_id,
        )
        return result.to_json()

    return librarian_handler
