# LLM Architecture for PASSFEL

**Last Updated:** 2025-10-29

## Executive Summary

PASSFEL (Personal ASSistant For Everyday Life) requires a self-hosted LLM as the central orchestrator for all user interactions and data sources. This document evaluates SOTA models for deployment on the ASUS Ascent GX10 (NVIDIA GB10 Grace Blackwell, 128GB unified memory).

**FINAL DECISION (2025-10-29):** ✅ **Qwen3-Next-80B-A3B-Thinking selected as the production model for PASSFEL**

**Critical Findings:**
1. **Llama models are NOT SOTA** - Llama 3.1/3.3 70B rank poorly on tool-calling benchmarks (17-31% BFCL accuracy)
2. **Tool-calling performance is critical** - PASSFEL requires strong function-calling for weather/news/calendar/finance/Home Assistant
3. **Qwen3-Next-80B-A3B-Thinking is the winner** - 72.0% BFCL-v3, Apache 2.0 license, fits GX10 with FP8 (90-100GB)
4. **Leaderboard rankings matter** - LMSys Arena (human preference) and BFCL (tool-calling) are more relevant than older benchmarks
5. **Qwen3-Max is NOT compatible** - 1T+ params requires 500GB+ memory (GX10 has 128GB)
6. **No Nemotron fine-tunes exist** - Qwen3-Next-80B-A3B-Thinking is too new (released Sep 2025)

**Recommended Model:** Qwen3-Next-80B-A3B-Thinking (80B total, 3B activated MoE) with FP8 quantization

## Hardware Specifications

### ASUS Ascent GX10
- **GPU**: NVIDIA GB10 (Grace Blackwell, integrated)
- **CPU**: ARM v9.2-A (Grace)
- **Memory**: 128GB LPDDR5x unified memory (shared CPU+GPU)
- **AI Performance**: 10,000 AI TOPS (FP4)
- **Architecture**: Single integrated GPU (not multi-GPU system)
- **NVLink-C2C**: CPU+GPU coherence technology
- **OS**: Ubuntu Linux

**Memory Constraint:** 128GB unified memory is the hard limit for model weights + KV cache + activations.

## Model Evaluation

**Evaluation Criteria:**
1. **Tool-Calling Performance (BFCL)** - Critical for PASSFEL's weather/news/calendar/finance/Home Assistant integration
2. **GX10 Compatibility** - Must fit in 128GB unified memory with FP8/INT4 quantization
3. **License** - Prefer Apache 2.0 or MIT for commercial use
4. **Leaderboard Rankings** - LMSys Arena (human preference), BFCL (tool-calling), Open LLM Leaderboard
5. **Context Length** - Prefer 128K+ for multi-domain context

### 1. Qwen3-Next-80B-A3B-Thinking ✅ RECOMMENDED

**Source:** https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking

**Parameters:** 80B total, 3B activated per token (High-Sparsity MoE)

**Architecture:**
- 512 experts, 10 activated per token, 1 shared expert
- Hybrid Attention: Gated DeltaNet + Gated Attention
- 48 layers with hybrid layout: 12 × (3 × (Gated DeltaNet → MoE) → 1 × (Gated Attention → MoE))
- Expert Intermediate Dimension: 512
- Multi-Token Prediction (MTP) for 2-3x inference speedup

**Memory Calculation:**
```
BF16: 80B × 2 bytes = 160 GB (DOES NOT FIT)
FP8:  80B × 1 byte  = 80 GB + ~15GB KV cache = ~95GB (FITS comfortably)
INT4: 80B × 0.5 bytes = 40 GB + ~15GB KV cache = ~55GB (FITS easily)
```

**Verdict:** ✅ **RECOMMENDED** - Best balance of tool-calling performance, GX10 compatibility, and permissive licensing

**Training:** 15T tokens pretraining + GSPO post-training

**Key Features:**
- 262,144 tokens native context (extensible to 1,010,000 with YaRN)
- Thinking mode with `<think>` tags (similar to DeepSeek-R1)
- Apache 2.0 license (fully permissive)
- Multi-Token Prediction for inference acceleration
- Optimized for ultra-long context with hybrid attention

**Benchmarks:**
- **BFCL-v3 (Tool-Calling):** 72.0% (beats Qwen3-235B's 71.9%)
- **TAU1-Retail (Agent):** 69.6% (best among compared models)
- **AIME25 (Math Reasoning):** 87.8%
- **LiveCodeBench v6 (Coding):** 68.7%
- **MMLU-Pro (Knowledge):** 82.7%
- **Arena-Hard v2 (Alignment):** 62.3%

**Deployment:**
- vLLM >= 0.10.2 or SGLang >= 0.5.2
- FP8 quantization recommended for GX10
- Enable MTP with `--speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'`
- Reasoning parser: `--reasoning-parser deepseek_r1`

**Why This Model Wins:**
1. **Top Tool-Calling:** 72.0% BFCL-v3 (only 0.4% behind Qwen3-30B-A3B-Thinking)
2. **GX10 Compatible:** Fits in 95GB with FP8 quantization
3. **Apache 2.0 License:** No restrictions
4. **Efficient MoE:** 3B activated per token (10x faster than 70B dense for long context)
5. **Strong Reasoning:** Outperforms Gemini-2.5-Flash-Thinking on most benchmarks
6. **Ultra-Long Context:** 262K native, 1M with YaRN

---

### 2. NVIDIA Nemotron-Ultra-253B-v1 ❌ NOT COMPATIBLE

**Source:** https://huggingface.co/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1

**Parameters:** 253B (dense decoder-only Transformer)

**Official Hardware Requirements:**
- **BF16**: 8x NVIDIA H100-80GB (640GB total VRAM)
- **FP8**: 4x NVIDIA H100-80GB (320GB total VRAM)

**Memory Calculation:**
```
BF16: 253B × 2 bytes = 506 GB (DOES NOT FIT)
FP8:  253B × 1 byte  = 253 GB (DOES NOT FIT)
INT4: 253B × 0.5 bytes = 126.5 GB + KV cache + activations = EXCEEDS 128GB
```

**Verdict:** ❌ **NOT COMPATIBLE** with GX10 (128GB unified memory)

**Training Date:** November 2024 - April 2025

**Key Features:**
- 128K context length
- Reasoning mode (ON/OFF) via system prompt
- Neural Architecture Search (NAS) optimized
- Post-trained for reasoning, RAG, tool calling

**Benchmarks (Reasoning ON):**
- GPQA: 76.01
- AIME25: 72.50
- MATH500: 97.00
- BFCL V2 Live (tool calling): 74.10
- LiveCodeBench: 66.31
- IFEval: 89.45

---

### 2. NVIDIA Nemotron-Super-49B-v1.5 ✅ COMPATIBLE (RECOMMENDED)

**Source:** https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1_5

**Parameters:** 50B (dense decoder-only Transformer, NAS-optimized from Llama-3.3-70B)

**Official Test Hardware:**
- 2x NVIDIA H100-80GB
- 2x NVIDIA A100-80GB

**Memory Calculation:**
```
BF16: 50B × 2 bytes = 100 GB + ~20GB KV cache = ~120GB (FITS with tight margin)
FP8:  50B × 1 byte  = 50 GB + ~20GB KV cache = ~70GB (FITS comfortably)
INT4: 50B × 0.5 bytes = 25 GB + ~20GB KV cache = ~45GB (FITS easily)
```

**Verdict:** ✅ **COMPATIBLE** with GX10 using FP8 or INT4 quantization

**Training Date:** November 2024 - July 2025

**Key Features:**
- 128K context length
- Reasoning mode (default ON, `/no_think` for OFF)
- Neural Architecture Search (NAS) optimized for single H100-80GB
- Post-trained for reasoning, RAG, tool calling
- Derivative of Meta Llama-3.3-70B-Instruct
- Optimized for single GPU deployment

**Architecture Optimizations:**
- Skip attention: Some blocks skip attention entirely or use single linear layer
- Variable FFN: Different expansion/compression ratios per block
- Block-wise distillation from reference model

**Benchmarks (Reasoning ON, temp=0.6, top_p=0.95):**
- MATH500: 97.4
- AIME 2024: 87.5
- AIME 2025: 82.71
- GPQA: 71.97
- LiveCodeBench 24.10-25.02: 73.58
- BFCL v3 (tool calling): 71.75
- IFEval: 88.61
- ArenaHard: 92.0
- MMLU Pro (CoT): 79.53

**Deployment:**
- vLLM 0.9.2 recommended
- TensorRT-LLM for NVIDIA hardware
- Tool calling support with custom parser
- Recommended: `tensor-parallel-size=8` (for multi-GPU, needs adjustment for single GB10)

---

### 3. Qwen2.5-72B-Instruct (RESEARCH IN PROGRESS)

**Source:** https://huggingface.co/Qwen/Qwen2.5-72B-Instruct

**Parameters:** 72.7B (70.0B non-embedding)

**Architecture:**
- Transformers with RoPE, SwiGLU, RMSNorm, Attention QKV bias
- 80 layers
- GQA: 64 heads for Q, 8 heads for KV
- Context: 131,072 tokens (full), 8,192 tokens (generation)

**Memory Calculation (PRELIMINARY):**
```
BF16: 73B × 2 bytes = 146 GB (DOES NOT FIT)
FP8:  73B × 1 byte  = 73 GB + ~20GB KV cache = ~93GB (FITS with margin)
INT4: 73B × 0.5 bytes = 36.5 GB + ~20GB KV cache = ~56.5GB (FITS comfortably)
```

**Verdict:** ✅ **LIKELY COMPATIBLE** with GX10 using FP8 or INT4 quantization

**Key Features:**
- Significantly more knowledge in coding and mathematics
- Improved instruction following
- Long-context support (128K tokens)
- Multilingual: 29+ languages
- JSON structured output generation

**Training Stage:** Pretraining & Post-training

**Note:** Need to research tool-calling benchmarks and deployment requirements for GB10.

---

### 4. Meta Llama 3.1 70B Instruct ✅ COMPATIBLE

**Source:** https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct

**Parameters:** 70.6B (dense decoder-only Transformer)

**Official Training Hardware:**
- H100-80GB GPUs (7.0M GPU hours)

**Memory Calculation:**
```
BF16: 71B × 2 bytes = 142 GB (DOES NOT FIT)
FP8:  71B × 1 byte  = 71 GB + ~12GB KV cache = ~83GB (FITS comfortably)
INT4: 71B × 0.5 bytes = 35.5 GB + ~6GB KV cache = ~41.5GB (FITS easily)
```

**Verdict:** ✅ **COMPATIBLE** with GX10 using FP8 or INT4 quantization

**Training Date:** Pretraining cutoff December 2023, Released July 23, 2024

**Key Features:**
- 128K context length
- Multilingual support (8 languages: English, German, French, Italian, Portuguese, Hindi, Spanish, Thai)
- Tool calling support (multiple formats)
- Optimized for dialogue use cases
- Supervised fine-tuning (SFT) + RLHF
- Grouped-Query Attention (GQA)

**Benchmarks (Llama 3.1 70B Instruct):**

**General:**
- MMLU: 83.6
- MMLU (CoT): 86.0
- MMLU-Pro (CoT): 66.4
- IFEval: 87.5

**Reasoning:**
- ARC-C: 94.8
- GPQA: 46.7

**Code:**
- HumanEval: 80.5
- MBPP++: 86.0
- Multipl-E HumanEval: 65.5
- Multipl-E MBPP: 62.0

**Math:**
- GSM-8K (CoT): 95.1
- MATH (CoT): 68.0

**Tool Use (CRITICAL FOR PASSFEL):**
- API-Bank: 90.0
- BFCL: 84.8
- Gorilla Benchmark API Bench: 29.7
- Nexus (0-shot): 56.7

**Multilingual:**
- Multilingual MGSM (CoT): 86.9

**Deployment:**
- Transformers >= 4.43.0
- vLLM support (OpenAI-compatible API)
- Tool calling via chat templates (Hermes-inspired format)
- Quantization: bitsandbytes (8-bit/4-bit), GPTQ, AWQ

**Note:** A newer version exists (Llama 3.3 70B Instruct) which may have improved performance

---

### 5. Mistral Mixtral 8x22B (RESEARCH PENDING)

**Status:** Research pending

**Architecture:** Mixture of Experts (MoE)

**Expected Parameters:** 
- Total: ~140B parameters
- Active: ~22B parameters per token

**Preliminary Assessment:** MoE models may fit if only active parameters need to be in memory, but need to verify if all experts must be loaded.

---

### 6. DeepSeek V2/V2.5 (RESEARCH PENDING)

**Status:** Research pending

**Architecture:** Large MoE models

**Preliminary Assessment:** Need to research latest versions and MoE memory requirements.

---

## Memory Budget Analysis

### Memory Components

For a 50B parameter model:

| Component | BF16 | FP8 | INT4 |
|-----------|------|-----|------|
| Model Weights | 100 GB | 50 GB | 25 GB |
| KV Cache (64K ctx, batch=1) | ~20 GB | ~10 GB | ~5 GB |
| Activations | ~5 GB | ~3 GB | ~2 GB |
| **Total** | **~125 GB** | **~63 GB** | **~32 GB** |

**GX10 Available:** 128 GB unified memory

**Conclusion:** 
- BF16: Tight fit, not recommended (no headroom)
- FP8: Comfortable fit, recommended
- INT4: Very comfortable fit, excellent option

### Memory Budget for 70B Parameter Model

| Component | BF16 | FP8 | INT4 |
|-----------|------|-----|------|
| Model Weights | 140 GB | 70 GB | 35 GB |
| KV Cache (64K ctx, batch=1) | ~25 GB | ~12 GB | ~6 GB |
| Activations | ~7 GB | ~4 GB | ~2 GB |
| **Total** | **~172 GB** | **~86 GB** | **~43 GB** |

**GX10 Available:** 128 GB unified memory

**Conclusion:**
- BF16: DOES NOT FIT
- FP8: Comfortable fit, recommended
- INT4: Very comfortable fit, excellent option

---

## Deployment Strategy

### Recommended Serving Stack

#### Option 1: vLLM (Recommended for Qwen3-Next)

**Advantages:**
- Excellent KV cache management (PagedAttention)
- OpenAI-compatible API
- Native Qwen3-Next support (vLLM >= 0.10.2)
- Multi-Token Prediction support
- Active community

**Configuration for Qwen3-Next-80B-A3B-Thinking:**
```bash
# vLLM deployment for GX10 with FP8 quantization
vllm serve Qwen/Qwen3-Next-80B-A3B-Thinking \
  --port 8000 \
  --max-model-len 262144 \
  --reasoning-parser deepseek_r1 \
  --quantization fp8 \
  --gpu-memory-utilization 0.90 \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'
```

**Key Parameters:**
- `--max-model-len 262144`: Native 262K context (reduce if OOM, minimum 131072 recommended)
- `--reasoning-parser deepseek_r1`: Parse thinking content from `<think>` tags
- `--quantization fp8`: FP8 quantization for GX10 (reduces memory to ~95GB)
- `--speculative-config`: Enable Multi-Token Prediction for 2-3x speedup

**Note:** vLLM >= 0.10.2 required for Qwen3-Next support

---

#### Option 2: SGLang (Alternative)

**Advantages:**
- Fast serving framework
- Native Qwen3-Next support (SGLang >= 0.5.2)
- Multi-Token Prediction support
- Efficient memory management

**Configuration for Qwen3-Next-80B-A3B-Thinking:**
```bash
# SGLang deployment for GX10 with FP8 quantization
python -m sglang.launch_server \
  --model-path Qwen/Qwen3-Next-80B-A3B-Thinking \
  --port 30000 \
  --tp-size 1 \
  --context-length 262144 \
  --reasoning-parser deepseek-r1 \
  --mem-fraction-static 0.8 \
  --speculative-algo NEXTN \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4
```

**Key Parameters:**
- `--tp-size 1`: Single GPU (integrated GB10)
- `--context-length 262144`: Native 262K context
- `--mem-fraction-static 0.8`: Reserve 80% memory for model
- `--speculative-algo NEXTN`: Enable Multi-Token Prediction

**Note:** SGLang >= 0.5.2 required for Qwen3-Next support

---

#### Option 3: TensorRT-LLM (Future Consideration)

**Advantages:**
- Native NVIDIA hardware optimization
- FP8 quantization support for Blackwell/Hopper
- Excellent throughput and latency
- Unified memory support for Grace Blackwell

**Status:** Need to verify Qwen3-Next and GB10 support in TensorRT-LLM

---

### Quantization Strategy

#### FP8 Quantization (Recommended for GB10)

**Advantages:**
- Native Blackwell/Hopper support
- Minimal accuracy degradation (~1-2% on benchmarks)
- 2x memory reduction vs BF16
- Excellent throughput

**NVIDIA Nemotron-Super-49B-v1.5-FP8:**
- Official FP8 variant available
- Pre-quantized by NVIDIA
- Validated on H100 hardware

**Implementation:**
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained(
    "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5-FP8",
    torch_dtype="auto",
    device_map="auto",
    trust_remote_code=True
)
```

---

#### INT4 Quantization (Maximum Efficiency)

**Advantages:**
- 4x memory reduction vs BF16
- Fits larger models on GX10
- Good for high-throughput scenarios

**Trade-offs:**
- 3-5% accuracy degradation on complex reasoning
- May impact tool-calling precision

**Implementation Options:**
- GPTQ quantization
- AWQ quantization
- bitsandbytes INT4

---

## Architecture Design

### Self-Hosted LLM as Central Orchestrator

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                          │
│                    (Voice, Text, Multi-modal)               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   LLM Orchestrator                          │
│        (Qwen3-Next-80B-A3B-Thinking @ FP8)                 │
│         80B total params, 3B activated (MoE)                │
│                                                             │
│  • Intent Classification                                    │
│  • Tool Selection (72.0% BFCL-v3)                          │
│  • Response Generation                                      │
│  • Reasoning (Thinking mode with <think> tags)             │
│  • Multi-Token Prediction (2-3x speedup)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Context    │  │   Tool      │  │  External   │
│  Builder    │  │  Executor   │  │  Services   │
└─────────────┘  └─────────────┘  └─────────────┘
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  pgvector   │  │  Weather    │  │  Venice.ai  │
│  Postgres   │  │  News       │  │  (Fallback) │
│  Redis      │  │  Calendar   │  │             │
│  TimescaleDB│  │  Finance    │  │             │
│             │  │  Home Asst  │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

### Context Builder Service

**Purpose:** Retrieve relevant context from multiple databases to augment LLM prompts

**Components:**
1. **pgvector**: Vector embeddings for semantic search
2. **Postgres**: Structured data (calendar events, tasks, contacts)
3. **Redis**: Short-term state and session management
4. **TimescaleDB**: Time-series data (weather history, financial data)

**Flow:**
```python
# Pseudo-code for Context Builder
def build_context(user_query: str) -> dict:
    # 1. Generate query embedding
    query_embedding = embed_model.encode(user_query)
    
    # 2. Semantic search in pgvector
    relevant_docs = pgvector.similarity_search(
        query_embedding, 
        top_k=5
    )
    
    # 3. Retrieve structured data from Postgres
    calendar_events = postgres.query(
        "SELECT * FROM events WHERE date >= NOW()"
    )
    
    # 4. Get session state from Redis
    session_state = redis.get(f"session:{user_id}")
    
    # 5. Retrieve time-series data from TimescaleDB
    weather_history = timescaledb.query(
        "SELECT * FROM weather WHERE time > NOW() - INTERVAL '7 days'"
    )
    
    return {
        "relevant_docs": relevant_docs,
        "calendar": calendar_events,
        "session": session_state,
        "weather": weather_history
    }
```

---

### Tool Executor Service

**Purpose:** Execute tool calls generated by LLM

**Supported Tools:**
1. **Weather**: NOAA/NWS API, Open-Meteo
2. **News**: Ground.news (Playwright), RSS feeds
3. **Calendar**: Google Calendar API, Apple Calendar (CalDAV), Joplin
4. **Finance**: yfinance, CoinGecko, Frankfurter
5. **Home Assistant**: REST API, WebSocket
6. **Q&A**: Wikipedia, arXiv, Wikidata, DuckDuckGo

**Tool Calling Flow:**
```python
# Pseudo-code for Tool Executor
def execute_tool(tool_call: dict) -> dict:
    tool_name = tool_call["function"]["name"]
    tool_args = json.loads(tool_call["function"]["arguments"])
    
    if tool_name == "get_weather":
        return weather_api.get_forecast(**tool_args)
    elif tool_name == "search_news":
        return news_api.search(**tool_args)
    elif tool_name == "get_calendar_events":
        return calendar_api.list_events(**tool_args)
    # ... more tools
```

---

## Fallback Strategy

### Venice.ai as Emergency Fallback

**Use Cases:**
- GX10 GPU saturated (high concurrent load)
- Model inference failure
- Maintenance/updates

**Implementation:**
```python
def get_llm_response(prompt: str) -> str:
    try:
        # Primary: Self-hosted LLM on GX10
        response = local_llm.generate(prompt)
        return response
    except (GPUOutOfMemoryError, ModelLoadError) as e:
        logger.warning(f"Local LLM failed: {e}, falling back to Venice.ai")
        # Fallback: Venice.ai
        response = venice_api.generate(prompt)
        return response
```

---

## Performance Targets

### Latency Requirements

| Use Case | Target Latency | Notes |
|----------|----------------|-------|
| Simple Q&A | < 500ms | First token |
| Tool Calling | < 1s | Tool selection |
| Reasoning (ON) | < 3s | First token |
| Long-form generation | < 100ms/token | Streaming |

### Throughput Requirements

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent Users | 1-5 | Personal assistant |
| Requests/second | 10-20 | Burst capacity |
| Tokens/second | 50-100 | Generation speed |

---

## Next Steps

### Completed Research ✅

1. ✅ Verified Nemotron-Ultra-253B does NOT fit on GX10
2. ✅ Identified Nemotron-Super-49B-v1.5 as compatible alternative
3. ✅ Researched LMSys Arena (Chatbot Arena) leaderboard - DeepSeek V3.x and Qwen3 are SOTA
4. ✅ Researched Open LLM Leaderboard (HuggingFace) - Qwen2.5-72B ranks #6
5. ✅ Researched AlpacaEval 2.0 leaderboard - Llama 3.1 405B ranks #7
6. ✅ Researched BFCL (Berkeley Function Calling Leaderboard) - GLM-4.5 and Qwen3 dominate
7. ✅ Identified Qwen3-Next-80B-A3B-Thinking as recommended model (72.0% BFCL-v3, Apache 2.0, GX10 compatible)
8. ✅ Documented vLLM deployment for Qwen3-Next-80B-A3B-Thinking on GX10
9. ✅ Documented SGLang deployment for Qwen3-Next-80B-A3B-Thinking on GX10
10. ✅ Created comprehensive leaderboard snapshot (LEADERBOARD_SNAPSHOT.md)

### Pending Implementation Tasks

1. ⏳ Update QA_RESEARCH.md to pivot from Venice.ai to self-hosted LLM as primary
2. ⏳ Design Context Builder service with pgvector/Postgres/Redis/TimescaleDB
3. ⏳ Design Orchestrator service with tool calling implementation
4. ⏳ Test Qwen3-Next-80B-A3B-Thinking deployment on GX10 hardware
5. ⏳ Benchmark FP8 vs INT4 accuracy on tool-calling tasks
6. ⏳ Test 262K context handling on GX10 memory constraints
7. ⏳ Implement tool-calling integration for weather/news/calendar/finance/Home Assistant
8. ⏳ Verify TensorRT-LLM support for Qwen3-Next and GB10

### Key Findings Summary

**Leaderboard Research:**
- **LMSys Arena (Human Preference):** DeepSeek-V3.1 (1416 ELO), Qwen3-235B (1418 ELO), GLM-4.6 (1422 ELO) are top open-source
- **BFCL (Tool-Calling):** GLM-4.5 (70.85%), Qwen3-Next-80B-A3B-Thinking (72.0%), Qwen3-235B (54.37%)
- **Llama Models:** Rank poorly on tool-calling (17-31% BFCL) despite good chat performance

**Model Selection:**
- **Winner:** Qwen3-Next-80B-A3B-Thinking (80B total, 3B activated MoE)
- **BFCL-v3:** 72.0% (top tool-calling performance for GX10-compatible models)
- **License:** Apache 2.0 (fully permissive)
- **Memory:** 95GB with FP8 quantization (fits GX10's 128GB)
- **Context:** 262K native, 1M with YaRN
- **Speedup:** 2-3x with Multi-Token Prediction

---

## References

1. [Qwen3-Next-80B-A3B-Thinking Model Card](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking)
2. [LMSys Chatbot Arena Leaderboard](https://lmarena.ai/leaderboard/text)
3. [Berkeley Function Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html)
4. [Open LLM Leaderboard (HuggingFace)](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard)
5. [AlpacaEval 2.0 Leaderboard](https://tatsu-lab.github.io/alpaca_eval/)
6. [NVIDIA Nemotron-Ultra-253B Model Card](https://huggingface.co/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1)
7. [NVIDIA Nemotron-Super-49B-v1.5 Model Card](https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1_5)
8. [Qwen2.5-72B-Instruct Model Card](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
9. [ASUS Ascent GX10 Technical Specifications](https://www.asus.com/networking-iot-servers/desktop-ai-supercomputer/ultra-small-ai-supercomputers/asus-ascent-gx10/techspec/)
10. [Qwen3 Technical Report (arXiv:2505.09388)](https://arxiv.org/abs/2505.09388)
11. [Qwen2.5-1M Technical Report (arXiv:2501.15383)](https://arxiv.org/abs/2501.15383)

---

**Document Status:** COMPLETE - Qwen3-Next-80B-A3B-Thinking identified as recommended model for PASSFEL
