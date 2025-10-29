# LLM Architecture for PASSFEL

**Last Updated:** 2025-10-29

## Executive Summary

PASSFEL (Personal ASSistant For Everyday Life) requires a self-hosted LLM as the central orchestrator for all user interactions and data sources. This document evaluates SOTA models for deployment on the ASUS Ascent GX10 (NVIDIA GB10 Grace Blackwell, 128GB unified memory).

**Critical Finding:** NVIDIA Nemotron-Ultra-253B does NOT fit on GX10 hardware. Recommended models are in the 50-70B parameter range with FP8/INT4 quantization.

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

### 1. NVIDIA Nemotron-Ultra-253B-v1 ❌ NOT COMPATIBLE

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

#### Option 1: TensorRT-LLM (NVIDIA-optimized)

**Advantages:**
- Native NVIDIA hardware optimization
- FP8 quantization support for Blackwell/Hopper
- Excellent throughput and latency
- Unified memory support for Grace Blackwell

**Configuration:**
```bash
# TensorRT-LLM deployment for GB10
# Single GPU (integrated GB10)
trtllm-build \
  --checkpoint_dir ./model_checkpoint \
  --output_dir ./trt_engine \
  --gemm_plugin auto \
  --max_batch_size 8 \
  --max_input_len 32768 \
  --max_output_len 8192 \
  --use_fp8 \
  --strongly_typed
```

**Status:** Need to verify GB10 support in TensorRT-LLM

---

#### Option 2: vLLM (Baseline)

**Advantages:**
- Excellent KV cache management (PagedAttention)
- OpenAI-compatible API
- Wide model support
- Active community

**Configuration:**
```bash
# vLLM deployment for single GPU
python3 -m vllm.entrypoints.openai.api_server \
  --model "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5" \
  --trust-remote-code \
  --seed=1 \
  --host="0.0.0.0" \
  --port=5000 \
  --tensor-parallel-size=1 \
  --max-model-len=32768 \
  --gpu-memory-utilization 0.90 \
  --enforce-eager \
  --dtype=float16
```

**Note:** vLLM 0.9.2+ recommended for Nemotron models

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
│          (Nemotron-Super-49B-v1.5 @ FP8/INT4)              │
│                                                             │
│  • Intent Classification                                    │
│  • Tool Selection                                           │
│  • Response Generation                                      │
│  • Reasoning (ON/OFF modes)                                 │
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

### Immediate Actions

1. ✅ Verify Nemotron-Ultra-253B does NOT fit on GX10
2. ✅ Identify Nemotron-Super-49B-v1.5 as compatible alternative
3. ⏳ Research Qwen2.5-72B-Instruct tool-calling benchmarks
4. ⏳ Research Meta Llama 3.1 70B tool-calling benchmarks
5. ⏳ Research Mistral Mixtral 8x22B MoE memory requirements
6. ⏳ Research DeepSeek V2/V2.5 latest versions
7. ⏳ Create comprehensive model comparison table with benchmarks
8. ⏳ Document TensorRT-LLM deployment for GB10
9. ⏳ Document vLLM deployment for GB10
10. ⏳ Update QA_RESEARCH.md to pivot from Venice.ai to self-hosted LLM

### Research Priorities

1. **Tool-Calling Benchmarks**: BFCL, AgentBench, ToolBench for all candidate models
2. **GB10 Compatibility**: Verify TensorRT-LLM and vLLM support for GB10
3. **Quantization Impact**: Benchmark FP8 vs INT4 accuracy on tool-calling tasks
4. **Context Length**: Test 128K context handling on GX10 memory constraints

---

## References

1. [NVIDIA Nemotron-Ultra-253B Model Card](https://huggingface.co/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1)
2. [NVIDIA Nemotron-Super-49B-v1.5 Model Card](https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1_5)
3. [Qwen2.5-72B-Instruct Model Card](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
4. [ASUS Ascent GX10 Technical Specifications](https://www.asus.com/networking-iot-servers/desktop-ai-supercomputer/ultra-small-ai-supercomputers/asus-ascent-gx10/techspec/)
5. [Llama-Nemotron: Efficient Reasoning Models (arXiv:2505.00949)](https://arxiv.org/abs/2505.00949)
6. [Puzzle: Distillation-Based NAS for Inference-Optimized LLMs (arXiv:2411.19146)](https://arxiv.org/abs/2411.19146)

---

**Document Status:** IN PROGRESS - Continuing research on Qwen2.5, Llama 3.x, Mistral, DeepSeek models
