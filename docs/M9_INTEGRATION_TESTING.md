# M9: Comprehensive Integration Testing Protocol

**Version:** 2.0  
**Created:** 2025-12-31  
**Last Updated:** 2025-12-31 02:22 UTC  
**Status:** 8/9 PASS, 1 FAIL (INV-6: SecretScanner not integrated into artifact storage)  

---

## Purpose

This document defines the acceptance protocol for verifying the CompyMac memory system works end-to-end with real Venice.ai API calls, real document ingestion, and real trace capture. Unit tests are not sufficient - we need evidence that every component works in production conditions.

This version (2.0) tests all 6 invariants from MEMORY_SYSTEM_DESIGN.md with SQL queries and artifact file verification.

---

## Prerequisites

### Environment Variables
```bash
export LLM_API_KEY="<venice-api-key>"
export LLM_BASE_URL="https://api.venice.ai/api/v1"
export LLM_MODEL="qwen3-235b-a22b-instruct-2507"
```

### Test Script
```bash
python3 scripts/m9_comprehensive_integration.py
```

---

## Invariant Tests

### INV-1: LLM Artifacts

**Requirement:** Every LLM request/response is stored as artifact and referenced in trace_events.

**Test Method:** Make a real LLM call through LLMClient and verify with SQL queries.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| trace_id | `test-inv1-1767147746` |
| span_id | `span-1a23d0736497` |
| span_start_count | 1 |
| span_end_count | 1 |
| artifact_count | 2 |
| input_artifact_hash | `e70ffe7368efa650a187c6212e332c949f643070c88d681f83b4177ff08b1439` |
| output_artifact_hash | `c8c6260911519467075596667173e50c67982b8a7fc54feeedb812de5aaf4cb4` |
| llm_response | `hello` |

**SQL Verification:**
```sql
SELECT * FROM trace_events WHERE trace_id = 'test-inv1-1767147746' AND event_type = 'span_start';
-- Returns 1 row

SELECT * FROM trace_events WHERE trace_id = 'test-inv1-1767147746' AND event_type = 'span_end';
-- Returns 1 row

SELECT * FROM artifacts;
-- Returns 2 rows (input + output)
```

**Result:** PASS

---

### INV-2: Tool Artifacts

**Requirement:** Every tool input/output is stored as artifact.

**Test Method:** Execute a tool through LocalHarness and verify artifacts are stored.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| trace_id | `test-inv2-1767147747` |
| tool_name | `Read` |
| tool_result_success | `true` |
| event_count | 2 |
| artifact_count | 2 |
| artifact_hashes | `16914dc0a26ead96c8fecb54ac55793159cb1ec061ad84a6caa379997c7fde8c`, `193283f2fcad101f08b9ea1d9e2194b04f303a5435b347bc2b77a5167c7bf0f9` |

**Result:** PASS

---

### INV-3: Large Payload Handling

**Requirement:** Large payloads (>10KB) never stored inline in trace_events.

**Test Method:** Create a 15KB payload and verify it's stored as artifact, not inline.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| trace_id | `test-inv3-1767147747` |
| large_content_size | 15000 bytes |
| max_trace_event_data_len | 196 bytes |
| artifact_hash | `7b53845733c8bca180c829db16feb17c6502a2505ab1522afb6c6a94f524f6cf` |
| artifact_exists | `true` |
| artifact_file_size | 15000 bytes |

**SQL Verification:**
```sql
SELECT MAX(LENGTH(data)) FROM trace_events WHERE trace_id = 'test-inv3-1767147747';
-- Returns 196 (well under 10KB threshold)
```

**Result:** PASS

---

### INV-4: Content-Addressed Artifacts

**Requirement:** All artifacts are content-addressed (hash matches content).

**Test Method:** Store multiple artifacts and verify SHA-256 hash matches file content.

**Evidence Collected:**
| Stored Hash | Computed Hash | Match |
|-------------|---------------|-------|
| `2241d4000e5f44aee96313fce2ceda9de2ee4f483a9b22ef162b5cfb90ac7d51` | `2241d4000e5f44aee96313fce2ceda9de2ee4f483a9b22ef162b5cfb90ac7d51` | YES |
| `3815ff0b73b754cebdbd5ea8ba92d367710fa6b6b2ab12c803b20593f0c26fae` | `3815ff0b73b754cebdbd5ea8ba92d367710fa6b6b2ab12c803b20593f0c26fae` | YES |
| `81a944001b21c585a9cedb6a8adb23d0324c6c587196df7a884216d682514f23` | `81a944001b21c585a9cedb6a8adb23d0324c6c587196df7a884216d682514f23` | YES |

**Verification Method:**
```python
import hashlib
with open(artifact_path, 'rb') as f:
    computed = hashlib.sha256(f.read()).hexdigest()
assert computed == stored_hash
```

**Result:** PASS

---

### INV-5: Trace ID and Timestamp

**Requirement:** All persisted records include trace_id + timestamp.

**Test Method:** Create multiple traces and verify no NULL values.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| total_events | 6 |
| null_trace_id_or_timestamp | 0 |

**Sample Records:**
| trace_id | timestamp |
|----------|-----------|
| `test-inv5-0-1767147747` | `2025-12-31T02:22:27.337362+00:00` |
| `test-inv5-0-1767147747` | `2025-12-31T02:22:27.337729+00:00` |
| `test-inv5-1-1767147747` | `2025-12-31T02:22:27.338125+00:00` |
| `test-inv5-1-1767147747` | `2025-12-31T02:22:27.338470+00:00` |
| `test-inv5-2-1767147747` | `2025-12-31T02:22:27.338829+00:00` |

**SQL Verification:**
```sql
SELECT COUNT(*) FROM trace_events WHERE trace_id IS NULL OR timestamp IS NULL;
-- Returns 0
```

**Result:** PASS

---

### INV-6: Secret Redaction

**Requirement:** No secrets in stored content (after redaction enabled).

**Test Method:** Store content with secrets and verify if redacted in artifact file.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| trace_id | `test-inv6-1767147747` |
| artifact_hash | `40b1fb7e549891e02aecc3a601520890e4af5441ea788fa6a40c2d85f68aa29f` |
| secrets_in_stored_artifact | `true` |
| scanner_detected_count | 3 |
| scanner_redaction_works | `true` |

**Stored Content Sample (UNREDACTED):**
```
API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz
password=hunter2
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**CRITICAL GAP:** SecretScanner is NOT integrated into artifact storage path. The scanner works correctly (detects 3 secrets, redaction function works), but it is NOT called when storing artifacts.

**Result:** FAIL

**Required Fix:**
1. Wire SecretScanner into `ArtifactStore.store()` before writing to disk
2. Or wire into `TraceContext.store_artifact()` before calling ArtifactStore
3. Add configuration flag to enable/disable redaction

---

## Component Tests

### M8: Librarian Tool Registration

**Requirement:** librarian_search tool is registered and callable through LocalHarness.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| total_tools | 63 |
| librarian_in_schemas | `true` |
| librarian_registered | `true` |

**Sample Tools:** Read, Edit, Write, bash, bash_output, write_to_shell, kill_shell, grep, glob, wait

**Result:** PASS

---

### M6: Document Ingestion E2E

**Requirement:** Documents can be ingested with Venice.ai embeddings.

**Evidence Collected:**
| Field | Value |
|-------|-------|
| document_id | `doc-6890f87d87513aa4` |
| results_count | 1 |
| embedding_dimension | 1024 |
| sample_result | `CompyMac Memory System Documentation...` |

**Result:** PASS

---

### M5: Hybrid Retrieval

**Requirement:** HybridRetriever combines sparse + dense search.

**Evidence Collected:**
| Query | Type | Result Count | Top Score | Match Type |
|-------|------|--------------|-----------|------------|
| `TraceStore SQLite` | keyword | 1 | 0.0164 | hybrid |
| `how to store agent execution logs` | semantic | 1 | 0.0164 | hybrid |
| `vector embeddings for search` | mixed | 1 | 0.0164 | hybrid |

**Result:** PASS

---

## Summary Table

| Test | Status | Evidence |
|------|--------|----------|
| INV-1: LLM Artifacts | **PASS** | trace_id, 2 artifacts, hash verified |
| INV-2: Tool Artifacts | **PASS** | 2 events, 2 artifacts |
| INV-3: Large Payload | **PASS** | 15KB stored as artifact, not inline |
| INV-4: Content-Addressed | **PASS** | 3/3 hashes match |
| INV-5: Trace ID/Timestamp | **PASS** | 0 NULL values in 6 events |
| INV-6: Secret Redaction | **FAIL** | Scanner works but NOT integrated |
| M8: Librarian Tool | **PASS** | 63 tools, librarian registered |
| M6: Document Ingestion | **PASS** | doc_id, 1024-dim embeddings |
| M5: Hybrid Retrieval | **PASS** | 3 queries, all return results |

**Overall: 8/9 PASS**

---

## Blocking Issues

### 1. SecretScanner Not Integrated (CRITICAL)

**Impact:** Secrets in tool outputs and LLM responses are stored unredacted in artifact files.

**Risk:** Credential leakage in trace artifacts.

**Evidence:** Test INV-6 shows secrets are stored verbatim despite SecretScanner being available and functional.

**Fix Required:** Wire SecretScanner into artifact storage path before writing to disk.

---

## Test Execution Details

- **Test Script:** `scripts/m9_comprehensive_integration.py`
- **Test Directory:** `/tmp/m9_comprehensive`
- **Results File:** `/tmp/m9_comprehensive/results.json`
- **Execution Time:** 2025-12-31 02:22:26 UTC
- **Git Commit:** 1cc8b25 (main)
- **Repository:** jhacksman/compymac

---

**END OF M9 COMPREHENSIVE TESTING PROTOCOL**
