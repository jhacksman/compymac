# Q&A and Research Capabilities Research (#3)

## Overview

This document provides comprehensive research on implementing on-the-fly Q&A and research capabilities for the PASSFEL (Personal ASSistant For Everyday Life) project. The research covers knowledge retrieval systems, data sources, LLM integration strategies, and implementation approaches that balance local processing with cloud services while respecting the 64GB VRAM constraint.

## Research Methodology

Solutions are categorized by complexity to prioritize implementation:
- **Simple**: Ready-to-use APIs, minimal setup, good documentation, no API keys required
- **Moderate**: Requires API keys or configuration, moderate complexity, well-documented
- **Complex**: Complex setup, limited documentation, or significant implementation overhead

## Architecture Overview

The Q&A and research system consists of three main components:

1. **Knowledge Retrieval Layer**: Fetches information from various data sources
2. **RAG (Retrieval-Augmented Generation) System**: Stores and retrieves relevant context using vector embeddings
3. **LLM Processing Layer**: Generates answers and summaries based on retrieved information

## Knowledge Retrieval Data Sources

### 1. Wikipedia API ⭐ RECOMMENDED (Simple)

**Overview:**
Wikipedia provides free, open access to its vast knowledge base through the MediaWiki REST API and Action API, covering millions of articles across hundreds of languages.

**Key Features:**
- 60+ million articles across 300+ languages
- No API key required
- No rate limits for reasonable use
- Structured data with categories and links
- Free and open source (CC BY-SA license)

**API Details:**
- **REST API**: Modern RESTful interface at `https://en.wikipedia.org/api/rest_v1/`
- **Action API**: Legacy but powerful interface at `https://en.wikipedia.org/w/api.php`
- **Rate Limits**: No hard limits, but requests should be reasonable (< 200/sec)
- **User-Agent**: Required header identifying your application

**REST API Endpoints:**
```bash
# Get page summary
GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}

# Get full page content
GET https://en.wikipedia.org/api/rest_v1/page/html/{title}

# Search for pages
GET https://en.wikipedia.org/api/rest_v1/page/search/{query}
```

**Python Integration:**
```python
import requests

class WikipediaClient:
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
        self.headers = {
            "User-Agent": "PASSFEL/1.0 (your-email@example.com)"
        }
    
    def search(self, query, limit=10):
        """Search for Wikipedia articles"""
        url = f"{self.base_url}/page/search/{query}"
        params = {"limit": limit}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_summary(self, title):
        """Get article summary"""
        url = f"{self.base_url}/page/summary/{title}"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_content(self, title):
        """Get full article content"""
        url = f"{self.base_url}/page/html/{title}"
        response = requests.get(url, headers=self.headers)
        return response.text

# Usage
wiki = WikipediaClient()
results = wiki.search("artificial intelligence")
summary = wiki.get_summary("Artificial_intelligence")
print(f"Title: {summary['title']}")
print(f"Extract: {summary['extract']}")
```

**Response Format (Summary):**
```json
{
  "title": "Artificial intelligence",
  "extract": "Artificial intelligence (AI) is intelligence demonstrated by machines...",
  "description": "Intelligence of machines",
  "thumbnail": {
    "source": "https://upload.wikimedia.org/...",
    "width": 320,
    "height": 213
  },
  "content_urls": {
    "desktop": {
      "page": "https://en.wikipedia.org/wiki/Artificial_intelligence"
    }
  }
}
```

**Implementation Complexity:** Simple
- No authentication required
- Well-documented API
- Reliable and fast
- Comprehensive coverage

**Use Cases for PASSFEL:**
- General knowledge queries
- Fact checking
- Background information retrieval
- Entity disambiguation

---

### 2. arXiv API ⭐ RECOMMENDED (Simple)

**Overview:**
arXiv is a free distribution service and open-access archive for nearly 2.4 million scholarly articles in physics, mathematics, computer science, and related fields.

**Key Features:**
- 2.4 million research papers
- Free and open access
- No API key required
- Full-text PDF downloads
- Metadata and abstracts

**API Details:**
- **Base URL**: `http://export.arxiv.org/api/query`
- **Protocol**: Atom feed (XML)
- **Rate Limits**: 3 seconds between requests (recommended)
- **Max Results**: 30,000 per query

**Query Parameters:**
```
search_query: Search terms (ti:title, au:author, abs:abstract, all:all fields)
start: Starting index (0-based)
max_results: Number of results to return
sortBy: relevance, lastUpdatedDate, submittedDate
sortOrder: ascending, descending
```

**Python Integration:**
```python
import requests
import xml.etree.ElementTree as ET
from time import sleep

class ArXivClient:
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.namespace = {"atom": "http://www.w3.org/2005/Atom"}
    
    def search(self, query, max_results=10, sort_by="relevance"):
        """Search arXiv for papers"""
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by
        }
        
        response = requests.get(self.base_url, params=params)
        sleep(3)  # Rate limiting
        
        return self._parse_response(response.text)
    
    def _parse_response(self, xml_text):
        """Parse arXiv XML response"""
        root = ET.fromstring(xml_text)
        papers = []
        
        for entry in root.findall("atom:entry", self.namespace):
            paper = {
                "id": entry.find("atom:id", self.namespace).text,
                "title": entry.find("atom:title", self.namespace).text.strip(),
                "summary": entry.find("atom:summary", self.namespace).text.strip(),
                "published": entry.find("atom:published", self.namespace).text,
                "authors": [
                    author.find("atom:name", self.namespace).text
                    for author in entry.findall("atom:author", self.namespace)
                ],
                "pdf_url": None
            }
            
            # Find PDF link
            for link in entry.findall("atom:link", self.namespace):
                if link.get("title") == "pdf":
                    paper["pdf_url"] = link.get("href")
            
            papers.append(paper)
        
        return papers

# Usage
arxiv = ArXivClient()
papers = arxiv.search("all:machine learning", max_results=5)
for paper in papers:
    print(f"Title: {paper['title']}")
    print(f"Authors: {', '.join(paper['authors'])}")
    print(f"PDF: {paper['pdf_url']}\n")
```

**Search Query Examples:**
```python
# Search by title
arxiv.search("ti:neural networks")

# Search by author
arxiv.search("au:Hinton")

# Search by abstract
arxiv.search("abs:deep learning")

# Combined search
arxiv.search("ti:transformer AND au:Vaswani")

# Category search
arxiv.search("cat:cs.AI")
```

**Implementation Complexity:** Simple
- No authentication required
- Simple XML parsing
- Rate limiting is straightforward
- Comprehensive academic coverage

**Use Cases for PASSFEL:**
- Research paper lookup
- Academic question answering
- Technical deep dives
- Citation retrieval

---

### 3. Wikidata Query Service (Moderate)

**Overview:**
Wikidata is a free, collaborative knowledge base with structured data about entities, their properties, and relationships. It powers Wikipedia infoboxes and provides machine-readable knowledge.

**Key Features:**
- 100+ million items
- Structured data (entities, properties, relationships)
- SPARQL query interface
- Multilingual support
- Free and open (CC0 license)

**API Details:**
- **SPARQL Endpoint**: `https://query.wikidata.org/sparql`
- **REST API**: `https://www.wikidata.org/w/api.php`
- **Rate Limits**: No hard limits for reasonable use
- **Format**: JSON, XML, CSV, TSV

**SPARQL Query Example:**
```sparql
# Find all programming languages with their creators
SELECT ?language ?languageLabel ?creator ?creatorLabel WHERE {
  ?language wdt:P31 wd:Q9143.  # instance of programming language
  ?language wdt:P178 ?creator.  # developer
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10
```

**Python Integration:**
```python
import requests

class WikidataClient:
    def __init__(self):
        self.sparql_url = "https://query.wikidata.org/sparql"
        self.headers = {
            "User-Agent": "PASSFEL/1.0 (your-email@example.com)"
        }
    
    def query(self, sparql_query):
        """Execute SPARQL query"""
        params = {
            "query": sparql_query,
            "format": "json"
        }
        response = requests.get(
            self.sparql_url,
            params=params,
            headers=self.headers
        )
        return response.json()
    
    def get_entity_info(self, entity_id):
        """Get information about a Wikidata entity"""
        sparql = f"""
        SELECT ?property ?propertyLabel ?value ?valueLabel WHERE {{
          wd:{entity_id} ?p ?value.
          ?property wikibase:directClaim ?p.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 50
        """
        return self.query(sparql)

# Usage
wikidata = WikidataClient()

# Query for programming languages
sparql = """
SELECT ?language ?languageLabel ?year WHERE {
  ?language wdt:P31 wd:Q9143.
  OPTIONAL { ?language wdt:P571 ?year. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10
"""

results = wikidata.query(sparql)
for binding in results["results"]["bindings"]:
    print(f"{binding['languageLabel']['value']}: {binding.get('year', {}).get('value', 'Unknown')}")
```

**Implementation Complexity:** Moderate
- Requires SPARQL knowledge
- Powerful but complex queries
- Well-documented but steep learning curve
- Excellent for structured data

**Use Cases for PASSFEL:**
- Structured fact retrieval
- Entity relationships
- Timeline queries
- Comparative analysis

---

### 4. DuckDuckGo Instant Answer API (Simple)

**Overview:**
DuckDuckGo provides a free instant answer API that returns curated results for queries, including Wikipedia summaries, calculations, and factual answers.

**Key Features:**
- No API key required
- No rate limits
- Instant answers and summaries
- Privacy-focused
- Free to use

**API Details:**
- **Base URL**: `https://api.duckduckgo.com/`
- **Format**: JSON, XML
- **Rate Limits**: None specified
- **Authentication**: None required

**Python Integration:**
```python
import requests

class DuckDuckGoClient:
    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
    
    def query(self, q, format="json"):
        """Query DuckDuckGo Instant Answer API"""
        params = {
            "q": q,
            "format": format,
            "no_html": 1,
            "skip_disambig": 1
        }
        response = requests.get(self.base_url, params=params)
        return response.json()
    
    def get_answer(self, query):
        """Get instant answer for query"""
        result = self.query(query)
        
        if result.get("AbstractText"):
            return {
                "answer": result["AbstractText"],
                "source": result.get("AbstractSource"),
                "url": result.get("AbstractURL")
            }
        elif result.get("Answer"):
            return {
                "answer": result["Answer"],
                "source": "DuckDuckGo",
                "url": None
            }
        else:
            return None

# Usage
ddg = DuckDuckGoClient()
answer = ddg.get_answer("What is Python programming language?")
if answer:
    print(f"Answer: {answer['answer']}")
    print(f"Source: {answer['source']}")
```

**Implementation Complexity:** Simple
- No authentication
- Simple JSON response
- Limited but useful results
- Good for quick facts

**Use Cases for PASSFEL:**
- Quick fact lookup
- Calculations
- Unit conversions
- Simple Q&A

---

### 5. Web Search APIs (Moderate to Complex)

As mentioned in the PDF, the assistant should be able to use web search APIs (Bing or Google) to find relevant information and summarize it for the user.

**Option A: Bing Web Search API (Moderate) ⭐ (Explicitly mentioned in PDF)**
- **Provider**: Microsoft Azure Cognitive Services
- **Pricing**: Free tier with 1,000 queries/month, then $3/1000 queries (S1 tier)
- **Features**: Web search, news, images, videos, entity search, spell check
- **API Key**: Required (Azure subscription)
- **Rate Limits**: 3 queries/second (free tier), 10 queries/second (paid)
- **Documentation**: https://docs.microsoft.com/en-us/azure/cognitive-services/bing-web-search/

**Python Integration:**
```python
import requests

class BingSearchClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
    
    def search(self, query, count=10):
        """Search using Bing Web Search API"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }
        params = {
            "q": query,
            "count": count,
            "responseFilter": "Webpages",
            "textDecorations": True,
            "textFormat": "HTML"
        }
        
        response = requests.get(self.base_url, headers=headers, params=params)
        return response.json()
    
    def get_answer(self, query):
        """Get direct answer if available"""
        results = self.search(query, count=5)
        
        # Check for direct answer
        if "computation" in results:
            return results["computation"]["value"]
        
        # Extract top results
        if "webPages" in results and "value" in results["webPages"]:
            top_results = results["webPages"]["value"][:3]
            return {
                "results": [
                    {
                        "title": r["name"],
                        "snippet": r["snippet"],
                        "url": r["url"]
                    }
                    for r in top_results
                ]
            }
        
        return None

# Usage
bing_client = BingSearchClient("YOUR_AZURE_API_KEY")
results = bing_client.search("How do I prune a rose bush?")
print(results["webPages"]["value"][0]["snippet"])
```

**Recommendation:** Bing Web Search API is explicitly mentioned in the PDF and provides excellent coverage with a reasonable free tier. Good for production use with official Microsoft support.

---

**Option B: Google Programmable Search Engine (Moderate) ⭐ (Explicitly mentioned in PDF)**
- **Provider**: Google Cloud
- **Pricing**: Free tier with 100 queries/day, then $5/1000 queries
- **Features**: Customizable web search, site-restricted search
- **API Key**: Required (Google Cloud API key + Custom Search Engine ID)
- **Rate Limits**: 100 queries/day (free), 10,000 queries/day (paid)
- **Documentation**: https://developers.google.com/custom-search/v1/overview

**Python Integration:**
```python
import requests

class GoogleSearchClient:
    def __init__(self, api_key, search_engine_id):
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    def search(self, query, num=10):
        """Search using Google Custom Search API"""
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": num
        }
        
        response = requests.get(self.base_url, params=params)
        return response.json()
    
    def get_answer(self, query):
        """Get search results and extract relevant information"""
        results = self.search(query, num=5)
        
        if "items" in results:
            top_results = results["items"][:3]
            return {
                "results": [
                    {
                        "title": r["title"],
                        "snippet": r["snippet"],
                        "url": r["link"]
                    }
                    for r in top_results
                ]
            }
        
        return None

# Usage
google_client = GoogleSearchClient("YOUR_API_KEY", "YOUR_SEARCH_ENGINE_ID")
results = google_client.search("What's the capital of Denmark?")
print(results["items"][0]["snippet"])
```

**Setup Requirements:**
1. Create Google Cloud project
2. Enable Custom Search API
3. Create Custom Search Engine at https://programmablesearchengine.google.com/
4. Get API key and Search Engine ID

**Recommendation:** Google Programmable Search is explicitly mentioned in the PDF and provides high-quality results. Free tier is limited (100/day) but sufficient for personal use.

---

**Option C: Brave Search API (Moderate)**
- **Pricing**: Free tier with 2,000 queries/month, then $5/1000 queries
- **Features**: Web search, news, images, privacy-focused
- **API Key**: Required
- **Rate Limits**: Varies by plan
- **Documentation**: https://brave.com/search/api/

**Recommendation:** Good privacy-focused alternative with generous free tier.

---

**Option D: SerpAPI (Moderate)**
- **Pricing**: Free tier with 100 searches/month, then $50/5000 searches
- **Features**: Google search results proxy, structured data
- **API Key**: Required
- **Rate Limits**: Varies by plan
- **Documentation**: https://serpapi.com/

**Recommendation:** Provides Google results without Google API setup, but more expensive.

---

**Option E: Tavily AI (Moderate)**
- **Pricing**: Free tier with 1,000 requests/month
- **Features**: AI-optimized search for LLMs, structured output
- **API Key**: Required
- **Rate Limits**: Varies by plan
- **Documentation**: https://tavily.com/

**Recommendation:** Optimized for AI/LLM use cases, good for RAG systems.

---

**Implementation Note:** The PDF explicitly mentions using "web search APIs (for example, Bing or Google's search API)" for the Q&A system. While these require API keys and have usage limits, they provide high-quality search results that can be summarized by the LLM. For PASSFEL, Bing Web Search API is recommended as the primary option due to its reasonable pricing ($3/1000 queries after free tier) and official Microsoft support.

---

## RAG (Retrieval-Augmented Generation) System

### Vector Database Integration

**Existing Infrastructure:**
CompyMac already uses PostgreSQL with pgvector extension for vector similarity search in its memory system.

**Integration Strategy:**
```python
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

class KnowledgeRAG:
    def __init__(self, db_connection_string):
        self.conn = psycopg2.connect(db_connection_string)
        self._create_tables()
    
    def _create_tables(self):
        """Create knowledge base tables"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector(1536),
                    source TEXT,
                    source_url TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS knowledge_embedding_idx 
                ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            self.conn.commit()
    
    def store_chunk(self, content, embedding, source, source_url, metadata=None):
        """Store a knowledge chunk with its embedding"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO knowledge_chunks 
                (content, embedding, source, source_url, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (content, embedding, source, source_url, metadata))
            chunk_id = cur.fetchone()[0]
            self.conn.commit()
            return chunk_id
    
    def search_similar(self, query_embedding, limit=5, threshold=0.7):
        """Search for similar knowledge chunks"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, content, source, source_url, metadata,
                    1 - (embedding <=> %s) as similarity
                FROM knowledge_chunks
                WHERE 1 - (embedding <=> %s) > %s
                ORDER BY embedding <=> %s
                LIMIT %s
            """, (query_embedding, query_embedding, threshold, query_embedding, limit))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "content": row[1],
                    "source": row[2],
                    "source_url": row[3],
                    "metadata": row[4],
                    "similarity": row[5]
                })
            return results
```

**Chunking Strategy:**
```python
def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks
```

---

## LLM Integration Strategy

### VRAM Constraint Considerations

**Global VRAM Limit:** 64GB across all models

**Current Usage (from CompyMac):**
- Venice.ai API for LLM hosting (external service)
- Omniparser v2 for image classification (external service)

**Strategy for PASSFEL:**
Since CompyMac uses external LLM services (Venice.ai), PASSFEL should follow the same pattern to avoid VRAM constraints.

### Venice.ai Integration

**Overview:**
Venice.ai provides hosted LLM access with embeddings, completions, and chat capabilities.

**Integration Example:**
```python
import requests

class VeniceAIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.venice.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_embedding(self, text, model="text-embedding-ada-002"):
        """Get text embedding"""
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=self.headers,
            json={"input": text, "model": model}
        )
        return response.json()["data"][0]["embedding"]
    
    def chat_completion(self, messages, model="gpt-3.5-turbo", temperature=0.7):
        """Get chat completion"""
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
        )
        return response.json()["choices"][0]["message"]["content"]
```

### Q&A Pipeline

**Complete Q&A Flow:**
```python
class QASystem:
    def __init__(self, venice_client, knowledge_rag, wikipedia_client, arxiv_client):
        self.venice = venice_client
        self.rag = knowledge_rag
        self.wikipedia = wikipedia_client
        self.arxiv = arxiv_client
    
    def answer_question(self, question):
        """Answer a question using RAG + external sources"""
        
        # 1. Get question embedding
        question_embedding = self.venice.get_embedding(question)
        
        # 2. Search local knowledge base
        local_results = self.rag.search_similar(question_embedding, limit=3)
        
        # 3. Search external sources if needed
        external_context = []
        
        # Try Wikipedia
        wiki_results = self.wikipedia.search(question, limit=3)
        for result in wiki_results:
            summary = self.wikipedia.get_summary(result["title"])
            external_context.append({
                "source": "Wikipedia",
                "title": summary["title"],
                "content": summary["extract"],
                "url": summary["content_urls"]["desktop"]["page"]
            })
        
        # Try arXiv for technical questions
        if self._is_technical_question(question):
            arxiv_results = self.arxiv.search(question, max_results=2)
            for paper in arxiv_results:
                external_context.append({
                    "source": "arXiv",
                    "title": paper["title"],
                    "content": paper["summary"],
                    "url": paper["pdf_url"]
                })
        
        # 4. Build context for LLM
        context_parts = []
        
        # Add local knowledge
        for result in local_results:
            context_parts.append(f"[{result['source']}] {result['content']}")
        
        # Add external knowledge
        for item in external_context:
            context_parts.append(f"[{item['source']}: {item['title']}] {item['content']}")
        
        context = "\n\n".join(context_parts)
        
        # 5. Generate answer with LLM
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that answers questions based on provided context. Always cite your sources."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}\n\nProvide a comprehensive answer with citations."
            }
        ]
        
        answer = self.venice.chat_completion(messages)
        
        # 6. Return answer with sources
        sources = []
        for item in external_context:
            sources.append({
                "title": item["title"],
                "source": item["source"],
                "url": item["url"]
            })
        
        return {
            "answer": answer,
            "sources": sources,
            "local_matches": len(local_results),
            "external_matches": len(external_context)
        }
    
    def _is_technical_question(self, question):
        """Determine if question is technical/academic"""
        technical_keywords = [
            "algorithm", "research", "paper", "study", "theory",
            "machine learning", "neural network", "quantum", "physics",
            "mathematics", "computer science"
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in technical_keywords)
```

---

## Implementation Recommendations

### Phase 1: Core Q&A System (Immediate Implementation)

1. **Wikipedia Integration**
   - Implement WikipediaClient for general knowledge
   - Set up basic search and summary retrieval
   - Add caching to reduce API calls
   - **Rationale**: Free, comprehensive, no API key required

2. **RAG System Setup**
   - Extend existing pgvector database for knowledge storage
   - Implement chunking and embedding pipeline
   - Set up similarity search
   - **Rationale**: Leverages existing infrastructure

3. **Venice.ai LLM Integration**
   - Use existing Venice.ai client from CompyMac
   - Implement Q&A prompt templates
   - Add source citation logic
   - **Rationale**: Avoids VRAM constraints, consistent with existing architecture

### Phase 2: Academic Research (Short-term)

4. **arXiv Integration**
   - Implement ArXivClient for research papers
   - Add technical question detection
   - Implement PDF download and parsing (optional)
   - **Rationale**: Free, valuable for technical questions

5. **DuckDuckGo Integration**
   - Add DuckDuckGoClient for quick facts
   - Implement fallback logic
   - **Rationale**: Simple, free, no API key

### Phase 3: Structured Knowledge (Medium-term)

6. **Wikidata Integration**
   - Implement WikidataClient for structured queries
   - Add SPARQL query templates
   - Create entity relationship queries
   - **Rationale**: Powerful for structured data

### Phase 4: Web Search (Long-term, Optional)

7. **Web Search API (Optional)**
   - Evaluate Brave Search API or alternatives
   - Implement with API key management
   - Add usage tracking and limits
   - **Rationale**: Enhances coverage but requires API key and costs

---

## Caching Strategy

**Cache Layer:**
```python
import hashlib
import json
from datetime import datetime, timedelta

class QueryCache:
    def __init__(self, db_connection):
        self.conn = db_connection
        self._create_table()
    
    def _create_table(self):
        """Create cache table"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response JSONB NOT NULL,
                    source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS cache_expires_idx 
                ON query_cache(expires_at);
            """)
            self.conn.commit()
    
    def get(self, query, source):
        """Get cached response"""
        query_hash = self._hash_query(query, source)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT response FROM query_cache
                WHERE query_hash = %s AND expires_at > NOW()
            """, (query_hash,))
            
            result = cur.fetchone()
            return result[0] if result else None
    
    def set(self, query, source, response, ttl_hours=24):
        """Cache response"""
        query_hash = self._hash_query(query, source)
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_cache (query_hash, query, response, source, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (query_hash) DO UPDATE
                SET response = EXCLUDED.response,
                    created_at = CURRENT_TIMESTAMP,
                    expires_at = EXCLUDED.expires_at
            """, (query_hash, query, json.dumps(response), source, expires_at))
            self.conn.commit()
    
    def _hash_query(self, query, source):
        """Generate hash for query + source"""
        combined = f"{source}:{query.lower().strip()}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM query_cache WHERE expires_at < NOW()")
            self.conn.commit()
```

---

## Citation and Source Attribution

**Citation System:**
```python
class CitationManager:
    def __init__(self):
        self.citations = []
    
    def add_citation(self, source, title, url, content_snippet):
        """Add a citation"""
        citation_id = len(self.citations) + 1
        self.citations.append({
            "id": citation_id,
            "source": source,
            "title": title,
            "url": url,
            "snippet": content_snippet[:200]
        })
        return citation_id
    
    def format_citations(self):
        """Format citations for display"""
        if not self.citations:
            return ""
        
        formatted = "\n\nSources:\n"
        for cite in self.citations:
            formatted += f"[{cite['id']}] {cite['source']}: {cite['title']}\n"
            formatted += f"    {cite['url']}\n"
        
        return formatted
    
    def get_citation_prompt(self):
        """Get prompt instruction for LLM"""
        return """When answering, cite your sources using [1], [2], etc. 
        Each citation number corresponds to a source in the provided context."""
```

---

## Error Handling and Fallbacks

**Robust Query Handler:**
```python
class RobustQASystem:
    def __init__(self, qa_system, cache):
        self.qa = qa_system
        self.cache = cache
    
    def answer_with_fallbacks(self, question):
        """Answer question with multiple fallback strategies"""
        
        # Try cache first
        cached = self.cache.get(question, "qa_system")
        if cached:
            return cached
        
        try:
            # Try full Q&A system
            result = self.qa.answer_question(question)
            self.cache.set(question, "qa_system", result)
            return result
            
        except Exception as e:
            print(f"Full Q&A failed: {e}")
            
            try:
                # Fallback 1: Wikipedia only
                wiki_results = self.qa.wikipedia.search(question, limit=1)
                if wiki_results:
                    summary = self.qa.wikipedia.get_summary(wiki_results[0]["title"])
                    return {
                        "answer": summary["extract"],
                        "sources": [{
                            "title": summary["title"],
                            "source": "Wikipedia",
                            "url": summary["content_urls"]["desktop"]["page"]
                        }],
                        "fallback": "wikipedia_only"
                    }
            except Exception as e2:
                print(f"Wikipedia fallback failed: {e2}")
            
            try:
                # Fallback 2: DuckDuckGo
                ddg_result = self.qa.ddg.get_answer(question)
                if ddg_result:
                    return {
                        "answer": ddg_result["answer"],
                        "sources": [{
                            "title": "DuckDuckGo Instant Answer",
                            "source": ddg_result["source"],
                            "url": ddg_result["url"]
                        }],
                        "fallback": "duckduckgo"
                    }
            except Exception as e3:
                print(f"DuckDuckGo fallback failed: {e3}")
            
            # Final fallback: Error message
            return {
                "answer": "I'm sorry, I couldn't find an answer to your question at this time.",
                "sources": [],
                "error": str(e)
            }
```

---

## Security and Privacy Considerations

### Data Privacy
- **Local Storage**: Knowledge chunks stored locally in PostgreSQL
- **API Calls**: Minimize external API calls through caching
- **User Queries**: Log queries locally, not sent to third parties except LLM provider

### Rate Limiting
```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
    
    def allow_request(self):
        """Check if request is allowed"""
        now = time.time()
        
        # Remove old requests outside time window
        while self.requests and self.requests[0] < now - self.time_window:
            self.requests.popleft()
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False
    
    def wait_if_needed(self):
        """Wait if rate limit exceeded"""
        while not self.allow_request():
            time.sleep(0.1)
```

### Input Validation
```python
def validate_query(query):
    """Validate user query"""
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    
    if len(query) > 1000:
        raise ValueError("Query too long (max 1000 characters)")
    
    # Check for potential injection attempts
    dangerous_patterns = ["<script>", "javascript:", "DROP TABLE"]
    query_lower = query.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in query_lower:
            raise ValueError("Invalid query content")
    
    return query.strip()
```

---

## Testing Strategy

**Unit Tests:**
```python
import unittest
from unittest.mock import Mock, patch

class TestQASystem(unittest.TestCase):
    def setUp(self):
        self.venice_client = Mock()
        self.knowledge_rag = Mock()
        self.wikipedia_client = Mock()
        self.arxiv_client = Mock()
        
        self.qa_system = QASystem(
            self.venice_client,
            self.knowledge_rag,
            self.wikipedia_client,
            self.arxiv_client
        )
    
    def test_answer_question_with_wikipedia(self):
        """Test answering question using Wikipedia"""
        # Mock Wikipedia response
        self.wikipedia_client.search.return_value = [
            {"title": "Python_(programming_language)"}
        ]
        self.wikipedia_client.get_summary.return_value = {
            "title": "Python (programming language)",
            "extract": "Python is a high-level programming language...",
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Python_(programming_language)"}
            }
        }
        
        # Mock Venice.ai response
        self.venice_client.get_embedding.return_value = [0.1] * 1536
        self.venice_client.chat_completion.return_value = "Python is a high-level programming language..."
        
        # Mock RAG response
        self.knowledge_rag.search_similar.return_value = []
        
        # Test
        result = self.qa_system.answer_question("What is Python?")
        
        self.assertIn("answer", result)
        self.assertIn("sources", result)
        self.assertTrue(len(result["sources"]) > 0)
    
    def test_caching(self):
        """Test query caching"""
        cache = QueryCache(self.mock_db_connection)
        
        # Cache a response
        cache.set("test query", "wikipedia", {"answer": "test"})
        
        # Retrieve cached response
        cached = cache.get("test query", "wikipedia")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["answer"], "test")
```

**Integration Tests:**
```bash
# Test Wikipedia API
python -c "
from qa_system import WikipediaClient
wiki = WikipediaClient()
results = wiki.search('artificial intelligence')
print(f'Found {len(results)} results')
assert len(results) > 0
"

# Test arXiv API
python -c "
from qa_system import ArXivClient
arxiv = ArXivClient()
papers = arxiv.search('all:machine learning', max_results=5)
print(f'Found {len(papers)} papers')
assert len(papers) > 0
"
```

---

## Performance Optimization

### Embedding Batch Processing
```python
def batch_embed_chunks(chunks, venice_client, batch_size=100):
    """Embed chunks in batches for efficiency"""
    embeddings = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_embeddings = [
            venice_client.get_embedding(chunk)
            for chunk in batch
        ]
        embeddings.extend(batch_embeddings)
        time.sleep(1)  # Rate limiting
    
    return embeddings
```

### Parallel Source Querying
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def query_sources_parallel(question, sources):
    """Query multiple sources in parallel"""
    results = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(source.search, question): source_name
            for source_name, source in sources.items()
        }
        
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                results[source_name] = future.result(timeout=5)
            except Exception as e:
                print(f"Error querying {source_name}: {e}")
                results[source_name] = []
    
    return results
```

---

## Cost Analysis

| Component | Setup Cost | Ongoing Cost | Notes |
|-----------|------------|--------------|-------|
| Wikipedia API | $0 | $0 | Free, unlimited |
| arXiv API | $0 | $0 | Free, 3s rate limit |
| Wikidata | $0 | $0 | Free, unlimited |
| DuckDuckGo API | $0 | $0 | Free, unlimited |
| Venice.ai LLM | $0 (existing) | Variable | Existing CompyMac service |
| PostgreSQL + pgvector | $0 (existing) | $0 | Existing infrastructure |
| Brave Search API | $0 | $5/1000 queries (optional) | Optional enhancement |

**Total Estimated Cost (Basic Setup):** $0
**Total Estimated Cost (With Web Search):** $5-50/month (optional)

---

## Multi-Step Research and Agent Capabilities

As mentioned in the PDF, the assistant should be able to perform multi-step research for complex queries like "find me a good laptop under $1000 for programming" by breaking down the task into sub-tasks.

### Agent Architecture

```python
class ResearchAgent:
    def __init__(self, venice_client, search_client, qa_system):
        self.venice = venice_client
        self.search = search_client
        self.qa = qa_system
        self.task_history = []
    
    def research_complex_query(self, query):
        """Handle complex multi-step research queries"""
        
        # Step 1: Decompose query into sub-tasks
        sub_tasks = self._decompose_query(query)
        
        # Step 2: Execute each sub-task
        results = {}
        for task in sub_tasks:
            task_result = self._execute_task(task)
            results[task['id']] = task_result
            self.task_history.append({
                "task": task,
                "result": task_result,
                "timestamp": datetime.now().isoformat()
            })
        
        # Step 3: Synthesize results
        final_answer = self._synthesize_results(query, results)
        
        return {
            "answer": final_answer,
            "sub_tasks": sub_tasks,
            "task_results": results,
            "sources": self._collect_sources(results)
        }
    
    def _decompose_query(self, query):
        """Break down complex query into sub-tasks using LLM"""
        
        prompt = f"""Break down this complex query into specific sub-tasks:
Query: {query}

Identify 3-5 specific sub-tasks needed to answer this query completely.
Return as JSON array with format: [{{"id": 1, "task": "search for...", "type": "search|qa|compare"}}]
"""
        
        response = self.venice.chat_completion([
            {"role": "system", "content": "You are a task decomposition expert."},
            {"role": "user", "content": prompt}
        ])
        
        # Parse LLM response to extract sub-tasks
        import json
        try:
            sub_tasks = json.loads(response)
            return sub_tasks
        except:
            # Fallback: create basic sub-tasks
            return [
                {"id": 1, "task": f"Search for information about: {query}", "type": "search"}
            ]
    
    def _execute_task(self, task):
        """Execute a single sub-task"""
        
        task_type = task.get('type', 'search')
        task_content = task.get('task', '')
        
        if task_type == 'search':
            # Use web search for this sub-task
            search_results = self.search.search(task_content, count=5)
            return {
                "type": "search_results",
                "data": search_results,
                "summary": self._summarize_search_results(search_results)
            }
        
        elif task_type == 'qa':
            # Use Q&A system for this sub-task
            answer = self.qa.answer_question(task_content)
            return {
                "type": "qa_answer",
                "data": answer,
                "summary": answer.get('answer', '')
            }
        
        elif task_type == 'compare':
            # Extract items to compare from task
            items = self._extract_comparison_items(task_content)
            comparison = self._compare_items(items)
            return {
                "type": "comparison",
                "data": comparison,
                "summary": self._format_comparison(comparison)
            }
        
        return {"type": "unknown", "data": None, "summary": ""}
    
    def _summarize_search_results(self, search_results):
        """Summarize search results using LLM"""
        
        if not search_results or "webPages" not in search_results:
            return "No results found."
        
        # Extract snippets from top results
        snippets = []
        for page in search_results["webPages"]["value"][:5]:
            snippets.append(f"{page['name']}: {page['snippet']}")
        
        combined_text = "\n\n".join(snippets)
        
        # Ask LLM to summarize
        prompt = f"Summarize these search results concisely:\n\n{combined_text}"
        summary = self.venice.chat_completion([
            {"role": "user", "content": prompt}
        ])
        
        return summary
    
    def _extract_comparison_items(self, task_content):
        """Extract items to compare from task description"""
        # Use LLM to extract items
        prompt = f"Extract the items to compare from this task: {task_content}\nReturn as JSON array."
        response = self.venice.chat_completion([
            {"role": "user", "content": prompt}
        ])
        
        import json
        try:
            return json.loads(response)
        except:
            return []
    
    def _compare_items(self, items):
        """Compare multiple items"""
        comparisons = []
        
        for item in items:
            # Search for information about each item
            search_results = self.search.search(f"{item} specifications review", count=3)
            
            # Extract key information
            info = self._extract_item_info(item, search_results)
            comparisons.append({
                "item": item,
                "info": info
            })
        
        return comparisons
    
    def _extract_item_info(self, item, search_results):
        """Extract structured information about an item"""
        if not search_results or "webPages" not in search_results:
            return {}
        
        # Combine search result snippets
        snippets = [
            page['snippet']
            for page in search_results["webPages"]["value"][:3]
        ]
        combined = " ".join(snippets)
        
        # Use LLM to extract structured info
        prompt = f"""Extract key specifications and information about {item} from this text:
{combined}

Return as JSON with keys: price, specs, pros, cons, rating"""
        
        response = self.venice.chat_completion([
            {"role": "user", "content": prompt}
        ])
        
        import json
        try:
            return json.loads(response)
        except:
            return {"summary": combined[:200]}
    
    def _format_comparison(self, comparison):
        """Format comparison results"""
        lines = ["Comparison:"]
        for item_data in comparison:
            item = item_data['item']
            info = item_data['info']
            lines.append(f"\n{item}:")
            for key, value in info.items():
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines)
    
    def _synthesize_results(self, original_query, results):
        """Synthesize all sub-task results into final answer"""
        
        # Collect all summaries
        summaries = []
        for task_id, result in results.items():
            summaries.append(f"Task {task_id}: {result.get('summary', '')}")
        
        combined_info = "\n\n".join(summaries)
        
        # Ask LLM to synthesize final answer
        prompt = f"""Based on the following research results, provide a comprehensive answer to: {original_query}

Research Results:
{combined_info}

Provide a clear, actionable answer with specific recommendations."""
        
        final_answer = self.venice.chat_completion([
            {"role": "system", "content": "You are a helpful research assistant."},
            {"role": "user", "content": prompt}
        ])
        
        return final_answer
    
    def _collect_sources(self, results):
        """Collect all sources from sub-task results"""
        sources = []
        
        for result in results.values():
            if result['type'] == 'search_results' and 'data' in result:
                search_data = result['data']
                if "webPages" in search_data:
                    for page in search_data["webPages"]["value"][:3]:
                        sources.append({
                            "title": page['name'],
                            "url": page['url']
                        })
            elif result['type'] == 'qa_answer' and 'data' in result:
                qa_sources = result['data'].get('sources', [])
                sources.extend(qa_sources)
        
        return sources

# Usage Example: Complex laptop search
agent = ResearchAgent(
    venice_client=VeniceClient(),
    search_client=BingSearchClient("API_KEY"),
    qa_system=QASystem(...)
)

result = agent.research_complex_query("find me a good laptop under $1000 for programming")

print(result['answer'])
# Output: "Based on my research, I recommend the following laptops under $1000 for programming:
# 1. Dell XPS 13 ($950) - Excellent build quality, 16GB RAM, Intel i7
# 2. Lenovo ThinkPad E15 ($850) - Great keyboard, 16GB RAM, AMD Ryzen 7
# 3. ASUS VivoBook ($750) - Budget option, 12GB RAM, Intel i5
# 
# The Dell XPS 13 offers the best overall value with premium build quality and performance..."

print(f"\nSources consulted: {len(result['sources'])}")
for source in result['sources'][:5]:
    print(f"  - {source['title']}: {source['url']}")
```

### Task Decomposition Examples

**Example 1: Product Research**
```
Query: "Find me a good laptop under $1000 for programming"

Sub-tasks:
1. Search for "best programming laptops 2025 under $1000"
2. Search for "laptop specifications for software development"
3. Compare top 3-5 laptop models (specs, reviews, prices)
4. Synthesize recommendation with pros/cons

Result: Specific laptop recommendations with reasoning
```

**Example 2: Trip Planning**
```
Query: "Plan a 3-day trip to San Francisco"

Sub-tasks:
1. Search for "top attractions in San Francisco"
2. Search for "San Francisco weather forecast"
3. Search for "San Francisco hotel recommendations"
4. Search for "San Francisco restaurant recommendations"
5. Create itinerary combining all information

Result: Day-by-day itinerary with attractions, dining, and logistics
```

**Example 3: Technical Problem Solving**
```
Query: "How do I fix Python import error ModuleNotFoundError"

Sub-tasks:
1. Search for "Python ModuleNotFoundError causes"
2. Search for "how to install Python packages pip"
3. Search for "Python virtual environment setup"
4. Synthesize step-by-step solution

Result: Comprehensive troubleshooting guide with multiple solutions
```

### Key Features Aligned with PDF

1. **Multi-Step Reasoning**: Breaks complex queries into manageable sub-tasks
2. **Tool Use**: Combines search, Q&A, and comparison capabilities
3. **Context Awareness**: Maintains task history and uses previous results
4. **Synthesis**: Combines information from multiple sources into coherent answer
5. **Source Attribution**: Tracks and cites all information sources

This implementation directly addresses the PDF's requirement for "multi-step search and reasoning process" where "AI agents shine" by utilizing "personal context and perform many tasks across applications."

---

## Hardware Constraints and External Services

**IMPORTANT: VRAM and Compute Constraints**

As specified in the CompyMac project requirements:
- **Global VRAM Limit**: 64GB total across ALL models (image identification + LLMs)
- **External Services**: Venice.ai API for LLM hosting, omniparser v2 for image classification
- **Architecture**: Memory system should be a CLIENT to these services, not local PyTorch models

**Implementation Strategy:**

```python
class ExternalLLMClient:
    """Client for Venice.ai API - no local model loading"""
    
    def __init__(self, api_key, base_url="https://api.venice.ai"):
        self.api_key = api_key
        self.base_url = base_url
        # NO local model loading - all processing happens on Venice.ai servers
    
    def chat_completion(self, messages, model="llama-3.1-405b"):
        """Send chat completion request to Venice.ai"""
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": model, "messages": messages}
        )
        return response.json()["choices"][0]["message"]["content"]
    
    def get_embedding(self, text, model="text-embedding-ada-002"):
        """Get text embedding from Venice.ai"""
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": model, "input": text}
        )
        return response.json()["data"][0]["embedding"]

# NO local model initialization like this:
# model = torch.load("model.pth")  # ❌ WRONG - violates VRAM constraint
# tokenizer = AutoTokenizer.from_pretrained("...")  # ❌ WRONG

# Instead, always use external API:
venice_client = ExternalLLMClient(api_key=os.getenv("VENICE_API_KEY"))  # ✅ CORRECT
answer = venice_client.chat_completion([{"role": "user", "content": "What is Python?"}])
```

**Why This Matters:**
- Local LLMs (even quantized) can consume 10-40GB VRAM
- Image models (omniparser v2) already use significant VRAM
- 64GB limit must accommodate ALL models globally
- External APIs eliminate VRAM concerns entirely
- Venice.ai provides enterprise-grade LLM access without local compute

**Cost Considerations:**
- Venice.ai API costs are variable based on usage
- Already part of existing CompyMac infrastructure
- No additional hardware investment needed
- Scales automatically with demand

This approach ensures the Q&A system respects hardware constraints while providing powerful LLM capabilities through external services.

---

## Conclusion

For PASSFEL's Q&A and research capabilities (#3), the recommended implementation approach is:

1. **Start with Wikipedia API** for general knowledge queries (free, comprehensive, no API key)
2. **Add arXiv API** for academic and technical questions (free, specialized)
3. **Implement RAG system** using existing pgvector infrastructure for local knowledge storage
4. **Use Venice.ai** (existing CompyMac service) for LLM processing to avoid VRAM constraints
5. **Add DuckDuckGo API** for quick facts and fallback (free, simple)
6. **Consider Bing or Google Web Search API** (explicitly mentioned in PDF) for enhanced coverage
7. **Implement multi-step research agent** for complex queries requiring task decomposition
8. **Consider Wikidata** for structured queries (free, powerful but complex)

This phased approach provides comprehensive Q&A capabilities while minimizing costs, respecting VRAM constraints (64GB global limit), leveraging existing infrastructure (Venice.ai, pgvector), and supporting both simple queries and complex multi-step research tasks. The system can answer general knowledge questions, technical queries, and research questions with proper source attribution and caching for efficiency.

---

*Last Updated: 2025-10-29*
*Research conducted for PASSFEL project feature #3 (Q&A and Research Capabilities) by Devin*
