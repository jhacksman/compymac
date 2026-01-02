"""
Librarian Tools - Agent tools for document library interaction.

Phase 5 of PDF ingestion: Provides tools for the agent to:
- Search documents in the library
- Activate/deactivate sources for context
- Query specific documents
- List available documents
"""

import json
from typing import Any

from compymac.storage.library_store import LibraryStore
from compymac.tools import Tool, ToolRegistry


def create_librarian_tools(
    library_store: LibraryStore,
    session_id: str,
) -> ToolRegistry:
    """
    Create a registry of librarian tools for agent use.

    Args:
        library_store: The library store to query
        session_id: Session ID for source activation

    Returns:
        ToolRegistry with librarian tools
    """
    registry = ToolRegistry()

    # Tool: Search documents
    def search_documents(query: str, top_k: int = 5) -> str:
        """Search for relevant content across all active documents."""
        # Get active sources for this session
        active_docs = library_store.get_active_sources(session_id)
        doc_ids = [doc.id for doc in active_docs] if active_docs else None

        results = library_store.search_chunks(
            query=query,
            doc_ids=doc_ids,
            top_k=top_k,
        )

        if not results:
            return json.dumps({
                "status": "no_results",
                "message": f"No relevant content found for query: {query}",
                "active_sources": len(active_docs) if active_docs else 0,
            })

        return json.dumps({
            "status": "success",
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    registry.register(Tool(
        name="library_search",
        description=(
            "Search for relevant content in the document library. "
            "Returns matching chunks from active source documents. "
            "Use this to find information from uploaded PDFs and documents."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant content",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=search_documents,
    ))

    # Tool: List documents
    def list_documents(user_id: str = "default") -> str:
        """List all documents in the library."""
        docs = library_store.get_user_documents(user_id)

        if not docs:
            return json.dumps({
                "status": "empty",
                "message": "No documents in library",
            })

        doc_list = [doc.to_dict() for doc in docs]
        return json.dumps({
            "status": "success",
            "document_count": len(docs),
            "documents": doc_list,
        })

    registry.register(Tool(
        name="library_list",
        description=(
            "List all documents in the document library. "
            "Shows document titles, status, and chunk counts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID to list documents for (default: 'default')",
                    "default": "default",
                },
            },
            "required": [],
        },
        handler=list_documents,
    ))

    # Tool: Activate source
    def activate_source(document_id: str) -> str:
        """Activate a document as a source for search."""
        doc = library_store.get_document(document_id)
        if not doc:
            return json.dumps({
                "status": "error",
                "message": f"Document not found: {document_id}",
            })

        success = library_store.add_active_source(session_id, document_id)
        if success:
            return json.dumps({
                "status": "success",
                "message": f"Activated source: {doc.title}",
                "document_id": document_id,
            })
        else:
            return json.dumps({
                "status": "error",
                "message": f"Failed to activate source: {document_id}",
            })

    registry.register(Tool(
        name="library_activate_source",
        description=(
            "Activate a document as a source for search queries. "
            "When a document is activated, its content will be included in search results. "
            "Use library_list to get document IDs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The ID of the document to activate",
                },
            },
            "required": ["document_id"],
        },
        handler=activate_source,
    ))

    # Tool: Deactivate source
    def deactivate_source(document_id: str) -> str:
        """Deactivate a document as a source for search."""
        doc = library_store.get_document(document_id)
        if not doc:
            return json.dumps({
                "status": "error",
                "message": f"Document not found: {document_id}",
            })

        success = library_store.remove_active_source(session_id, document_id)
        if success:
            return json.dumps({
                "status": "success",
                "message": f"Deactivated source: {doc.title}",
                "document_id": document_id,
            })
        else:
            return json.dumps({
                "status": "error",
                "message": f"Source was not active: {document_id}",
            })

    registry.register(Tool(
        name="library_deactivate_source",
        description=(
            "Deactivate a document as a source for search queries. "
            "The document will no longer be included in search results."
        ),
        parameters={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The ID of the document to deactivate",
                },
            },
            "required": ["document_id"],
        },
        handler=deactivate_source,
    ))

    # Tool: Get active sources
    def get_active_sources() -> str:
        """Get list of currently active source documents."""
        active_docs = library_store.get_active_sources(session_id)

        if not active_docs:
            return json.dumps({
                "status": "empty",
                "message": "No active sources",
            })

        doc_list = [doc.to_dict() for doc in active_docs]
        return json.dumps({
            "status": "success",
            "active_count": len(active_docs),
            "active_sources": doc_list,
        })

    registry.register(Tool(
        name="library_get_active_sources",
        description=(
            "Get the list of currently active source documents. "
            "These are the documents that will be searched when using library_search."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=get_active_sources,
    ))

    # Tool: Get document content
    def get_document_content(document_id: str, page: int | None = None) -> str:
        """Get the content of a specific document or page."""
        doc = library_store.get_document(document_id)
        if not doc:
            return json.dumps({
                "status": "error",
                "message": f"Document not found: {document_id}",
            })

        if not doc.chunks:
            return json.dumps({
                "status": "error",
                "message": f"Document has no content: {doc.title}",
            })

        # Filter by page if specified
        if page is not None:
            chunks = [
                c for c in doc.chunks
                if c.get("metadata", {}).get("page") == page
            ]
            if not chunks:
                return json.dumps({
                    "status": "error",
                    "message": f"No content found for page {page}",
                })
        else:
            chunks = doc.chunks

        # Combine chunk content
        content = "\n\n".join(c.get("content", "") for c in chunks)

        return json.dumps({
            "status": "success",
            "document_id": document_id,
            "title": doc.title,
            "page": page,
            "chunk_count": len(chunks),
            "content": content[:10000],  # Limit content size
            "truncated": len(content) > 10000,
        })

    registry.register(Tool(
        name="library_get_content",
        description=(
            "Get the content of a specific document or page. "
            "Use this to read the full text of a document after finding it with search."
        ),
        parameters={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The ID of the document to read",
                },
                "page": {
                    "type": "integer",
                    "description": "Optional page number to read (1-indexed)",
                },
            },
            "required": ["document_id"],
        },
        handler=get_document_content,
    ))

    return registry


def get_librarian_tool_schemas(
    library_store: LibraryStore,
    session_id: str,
) -> list[dict[str, Any]]:
    """
    Get OpenAI-format tool schemas for librarian tools.

    Args:
        library_store: The library store to query
        session_id: Session ID for source activation

    Returns:
        List of tool schemas in OpenAI format
    """
    registry = create_librarian_tools(library_store, session_id)
    return registry.get_schemas()
