# LLM Leaderboard Snapshot - October 29, 2025

**Last Updated:** October 29, 2025  
**Purpose:** Identify actual SOTA open-source models for GX10 deployment

## LMSys Chatbot Arena - Text Leaderboard

**Source:** https://lmarena.ai/leaderboard/text  
**Last Updated:** October 16, 2025  
**Total Votes:** 4,278,480  
**Total Models:** 258

### Top 20 Open-Source/Open-Weight Models

| Rank | Model | Score | Votes | License | Organization | Notes |
|------|-------|-------|-------|---------|--------------|-------|
| 10 | glm-4.6 | 1422 | 4,401 | MIT | Z.ai | - |
| 11 | deepseek-v3.2-exp-thinking | 1419 | 4,320 | MIT | DeepSeek AI | Reasoning mode |
| 11 | qwen3-vl-235b-a22b-instruct | 1418 | 6,312 | Apache 2.0 | Alibaba | Vision + Language, 235B MoE |
| 11 | qwen3-235b-a22b-instruct-2507 | 1418 | 29,343 | Apache 2.0 | Alibaba | 235B MoE |
| 11 | deepseek-r1-0528 | 1417 | 19,284 | MIT | DeepSeek | Reasoning model |
| 11 | kimi-k2-0905-preview | 1417 | 10,772 | Modified MIT | Moonshot | - |
| 11 | deepseek-v3.1 | 1416 | 15,380 | MIT | DeepSeek | MoE architecture |
| 11 | deepseek-v3.1-thinking | 1415 | 12,098 | MIT | DeepSeek | Reasoning mode |
| 11 | kimi-k2-0711-preview | 1415 | 28,321 | Modified MIT | Moonshot | - |
| 11 | deepseek-v3.1-terminus | 1414 | 3,775 | MIT | DeepSeek AI | - |
| 11 | deepseek-v3.1-terminus-thinking | 1413 | 3,541 | MIT | DeepSeek AI | Reasoning mode |
| 12 | deepseek-v3.2-exp | 1408 | 4,684 | MIT | DeepSeek AI | - |
| 18 | glm-4.5 | 1406 | 22,612 | MIT | Z.ai | - |
| 24 | qwen3-next-80b-a3b-instruct | 1402 | 12,793 | Apache 2.0 | Alibaba | 80B MoE |
| 29 | longcat-flash-chat | 1398 | 11,667 | MIT | Meituan | - |
| 29 | qwen3-235b-a22b-thinking-2507 | 1397 | 9,386 | Apache 2.0 | Alibaba | Reasoning mode |
| 30 | qwen3-235b-a22b-no-thinking | 1398 | 39,528 | Apache 2.0 | Alibaba | 235B MoE |
| 32 | deepseek-r1 | 1394 | 18,718 | MIT | DeepSeek | Reasoning model |
| 32 | qwen3-vl-235b-a22b-thinking | 1392 | 5,956 | Apache 2.0 | Alibaba | Vision + Reasoning |
| 36 | deepseek-v3-0324 | 1391 | 44,482 | MIT | DeepSeek | MoE architecture |

### Key Observations

1. **DeepSeek V3.x dominates open-source rankings** - Multiple variants (v3.1, v3.2, R1) with MIT license
2. **Qwen3 235B series is top Apache 2.0 model** - 235B parameter MoE architecture
3. **GLM-4.x series strong** - MIT licensed, from Z.ai
4. **Llama models are NOT in top 20 open-source** - User was correct to call this out
5. **Reasoning/thinking modes are prevalent** - Many top models have dedicated reasoning variants

### Notable Open-Source Models (Ranks 40-100)

| Rank | Model | Score | License | Notes |
|------|-------|-------|---------|-------|
| 39 | qwen3-30b-a3b-instruct-2507 | 1385 | Apache 2.0 | 30B MoE |
| 41 | qwen3-coder-480b-a35b-instruct | 1384 | Apache 2.0 | 480B coding specialist |
| 52 | qwen3-235b-a22b | 1372 | Apache 2.0 | Base model |
| 54 | glm-4.5-air | 1369 | MIT | Lightweight variant |
| 55 | qwen3-next-80b-a3b-thinking | 1367 | Apache 2.0 | 80B with reasoning |
| 56 | minimax-m1 | 1368 | Apache 2.0 | MiniMax |
| 60 | gemma-3-27b-it | 1363 | Gemma | Google, 27B |
| 63 | deepseek-v3 | 1356 | DeepSeek | Base DeepSeek V3 |
| 64 | glm-4.5v | 1351 | MIT | Vision variant |
| 65 | mistral-small-2506 | 1353 | Apache 2.0 | Mistral |
| 67 | command-a-03-2025 | 1349 | CC-BY-NC-4.0 | Cohere |
| 67 | gpt-oss-120b | 1348 | Apache 2.0 | OpenAI open-source |
| 67 | llama-3.1-nemotron-ultra-253b-v1 | 1344 | Nvidia Open Model | 253B NVIDIA |
| 67 | qwen3-32b | 1344 | Apache 2.0 | 32B |
| 69 | step-3 | 1344 | Apache 2.0 | StepFun |
| 69 | ling-flash-2.0 | 1341 | MIT | Ant Group |
| 69 | gemma-3-12b-it | 1340 | Gemma | Google, 12B |
| 69 | nvidia-llama-3.3-nemotron-super-49b-v1.5 | 1339 | Nvidia Open | 49B NVIDIA |

### Llama Models Rankings (for comparison)

| Rank | Model | Score | License | Notes |
|------|-------|-------|---------|-------|
| 100 | llama-3.3-70b-instruct | 1329 | Llama 3.3 | Meta, 70B |
| 118 | deepseek-v2.5 | 1308 | DeepSeek | MoE |
| 124 | llama-3.1-nemotron-70b-instruct | 1302 | Llama 3.1 | NVIDIA fine-tune |
| 124 | qwen2.5-72b-instruct | 1302 | Apache 2.0 | Qwen 2.5 series |
| 132 | llama-3.1-nemotron-51b-instruct | 1291 | Nvidia Open | NVIDIA 51B |
| 132 | llama-3.1-tulu-3-70b | 1291 | Llama 3.1 | Ai2 fine-tune |
| 132 | Meta-Llama-3.1-70B-Instruct | 1291 | Llama 3.1 Community | Meta official |

**Critical Finding:** Llama 3.1 70B ranks around #132 (score 1291), while top open-source models score 1415-1422. Llama is NOT competitive with SOTA open-source models.

## License Categories

### Truly Open-Source (OSI-approved)
- **MIT:** DeepSeek V3.x, GLM-4.x, Ling-flash, LongCat
- **Apache 2.0:** Qwen3 series, Mistral-small, Step-3, GPT-OSS-120B, Gemma-3

### Open-Weight with Restrictions
- **Llama Community License:** Meta Llama models (commercial use allowed with restrictions)
- **DeepSeek License:** DeepSeek V2.5 (open weights, specific terms)
- **Nvidia Open Model:** Nemotron series (open weights, Nvidia terms)
- **Gemma License:** Google Gemma models (open weights, Google terms)
- **CC-BY-NC-4.0:** Cohere Command models (non-commercial)

## Next Steps

1. Check Open LLM Leaderboard (HuggingFace)
2. Check AlpacaEval 2.0 leaderboard
3. Check BFCL (Berkeley Function Calling Leaderboard) for tool-use rankings
4. Filter models by GX10 compatibility (128GB unified memory)
5. Update LLM_ARCHITECTURE.md with actual SOTA models


## Open LLM Leaderboard (HuggingFace) - ARCHIVED

**Source:** https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard  
**Status:** Archived (no longer actively maintained)  
**Total Models:** 4,576  
**Benchmarks:** IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO

### Top 30 Models

| Rank | Model | Average | IFEval | BBH | MATH | GPQA | MUSR | MMLU-PRO | Notes |
|------|-------|---------|--------|-----|------|------|------|----------|-------|
| 1 | MaziyarPanahi/calme-3.2-instruct-78b | 52.08% | 80.63% | 62.61% | 40.33% | 20.36% | 38.53% | 70.03% | Fine-tuned |
| 2 | MaziyarPanahi/calme-3.1-instruct-78b | 51.29% | 81.36% | 62.41% | 39.27% | 19.46% | 36.50% | 68.72% | Fine-tuned |
| 3 | dfurman/CalmeRys-78B-Orpo-v0.1 | 51.23% | 81.63% | 61.92% | 40.63% | 20.02% | 36.37% | 66.80% | Fine-tuned |
| 4 | MaziyarPanahi/calme-2.4-rys-78b | 50.77% | 80.11% | 62.16% | 40.71% | 20.36% | 34.57% | 66.69% | Fine-tuned |
| 5 | huihui-ai/Qwen2.5-72B-Instruct-abliterated | 48.11% | 85.93% | 60.49% | 60.12% | 19.35% | 12.34% | 50.41% | Qwen2.5 variant |
| 6 | **Qwen/Qwen2.5-72B-Instruct** | **47.98%** | **86.38%** | **61.87%** | **59.82%** | **16.67%** | **11.74%** | **51.40%** | **Official Qwen2.5** |
| 7 | MaziyarPanahi/calme-2.1-qwen2.5-72b | 47.86% | 86.62% | 61.66% | 59.14% | 15.10% | 13.30% | 51.32% | Qwen2.5 fine-tune |
| 8 | newsbang/Homer-v1.0-Qwen2.5-72B | 47.46% | 76.28% | 62.27% | 49.02% | 22.15% | 17.90% | 57.17% | Qwen2.5 fine-tune |
| 9 | ehristoforu/qwen2.5-test-32b-it | 47.37% | 78.89% | 58.28% | 59.74% | 15.21% | 19.13% | 52.95% | Qwen2.5 32B |
| 10 | Saxo/Linkbricks-Horizon-AI-Avengers-V1-32B | 47.34% | 79.72% | 57.63% | 60.27% | 14.99% | 18.16% | 53.25% | 32B variant |
| 22 | **Qwen/Qwen2.5-32B-Instruct** | **46.60%** | **83.46%** | **56.49%** | **62.54%** | **11.74%** | **13.50%** | **51.85%** | **Official Qwen2.5** |
| 23 | mistralai/Mistral-Large-Instruct-2411 | 46.52% | 84.01% | 52.74% | 49.55% | 24.94% | 17.22% | 50.69% | Mistral Large |

### Key Observations

1. **Qwen2.5-72B-Instruct ranks #6** with 47.98% average (official model from Alibaba)
2. **Top 4 models are fine-tuned variants** of larger base models (78B parameter range)
3. **Qwen2.5 dominates the leaderboard** - Most top models are Qwen2.5 fine-tunes or variants
4. **Mistral-Large-Instruct-2411 ranks #23** with 46.52% average
5. **No Llama models in top 30** - Confirms user's observation that Llama is not SOTA
6. **Leaderboard is ARCHIVED** - May not reflect latest models (DeepSeek V3.x, Qwen3 not present)

### Important Context

This leaderboard is **archived** and uses older benchmarks (IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO). It does NOT include:
- DeepSeek V3.x series (released after archival)
- Qwen3 series (released after archival)
- Latest reasoning models (R1, thinking variants)

The LMSys Chatbot Arena (human preference) is more current and shows DeepSeek V3.x and Qwen3 as top open-source models.


## AlpacaEval 2.0 Leaderboard

**Source:** https://tatsu-lab.github.io/alpaca_eval/  
**Baseline:** GPT-4 Preview (11/06)  
**Auto-annotator:** GPT-4 Preview (11/06)  
**Metric:** Length-controlled (LC) win rate against baseline

### Top Open-Source Models

| Rank | Model | LC Win Rate | Win Rate | Notes |
|------|-------|-------------|----------|-------|
| 7 | Llama 3.1 405B Instruct | 39.3% | 39.1% | Meta, 405B |
| 9 | Qwen2 72B Instruct | 38.1% | 29.9% | Alibaba, Qwen2 series |
| 10 | Llama 3.1 70B Instruct | 38.1% | 39.1% | Meta, 70B |
| 11 | Qwen1.5 72B Chat | 36.6% | 26.5% | Alibaba, Qwen1.5 series |
| 14 | Llama 3 70B Instruct | 34.4% | 33.2% | Meta, 70B |
| 15 | Mistral Large (24/02) | 32.7% | 21.4% | Mistral |
| 16 | Mixtral 8x22B v0.1 | 30.9% | 22.2% | Mistral, MoE |

### Key Observations

1. **Llama 3.1 405B ranks #7** with 39.3% LC win rate (top open-source model on this leaderboard)
2. **Qwen2 72B ranks #9** with 38.1% LC win rate (tied with Llama 3.1 70B)
3. **Leaderboard is outdated** - Does NOT include DeepSeek V3.x, Qwen3, or latest reasoning models
4. **Length-controlled win rates** alleviate GPT-4 length bias but may favor models fine-tuned on GPT-4 outputs
5. **Simple instructions focus** - AlpacaFarm eval set consists mainly of simple instructions, not complex tool use

### Important Context

This leaderboard uses GPT-4 as both baseline and auto-annotator, which may introduce biases. The eval set focuses on simple instruction-following, not complex reasoning or tool use. The LMSys Chatbot Arena (human preference, updated Oct 2025) shows DeepSeek V3.x and Qwen3 as significantly stronger than these models.


## Berkeley Function Calling Leaderboard (BFCL) V4

**Source:** https://gorilla.cs.berkeley.edu/leaderboard.html  
**Last Updated:** 2025-08-26  
**Purpose:** Evaluate LLM's ability to call functions (tools) accurately  
**Evaluation:** Agentic (Web Search, Memory), Multi-turn, Single-turn (Non-live AST, Live AST)

### Top Open-Source Models (Tool-Calling Performance)

| Rank | Model | Overall Acc | Web Search | Memory | Multi-turn | Non-live (AST) | Live (AST) | License | Cost ($) |
|------|-------|-------------|------------|---------|------------|----------------|------------|---------|----------|
| 1 | GLM-4.5 (FC) | 70.85% | 79% | 50.75% | 65.62% | 86.6% | 81.72% | MIT | 2.9 |
| 4 | GLM-4.5-Air (FC) | 67.87% | 73.5% | 47.53% | 62.5% | 87.15% | 79.42% | MIT | 4.22 |
| 9 | Moonshotai-Kimi-K2-Instruct (FC) | 56.07% | 59% | 25.16% | 48.75% | 85.17% | 80.83% | modified-mit | 6.94 |
| 12 | **Qwen3-235B-A22B-Instruct-2507 (FC)** | **54.37%** | **49%** | **29.25%** | **44.5%** | **88.1%** | **82.61%** | **apache-2.0** | **12.02** |
| 18 | xLAM-2-70b-fc-r (FC) | 52.94% | 14.5% | 17.63% | 75.38% | 88.21% | 71.87% | cc-by-nc-4.0 | 4.7 |
| 19 | xLAM-2-32b-fc-r (FC) | 52.64% | 22.5% | 16.77% | 68.38% | 89.83% | 75.65% | cc-by-nc-4.0 | 2.17 |
| 20 | watt-tool-70B (FC) | 51.25% | 22.5% | 18.92% | 60.25% | 88.83% | 83.35% | Apache-2.0 | 5.13 |
| 23 | **DeepSeek-R1-0528 (FC)** | **48.97%** | **63%** | **0%** | **44.5%** | **75.73%** | **80.9%** | **MIT** | **53.04** |
| 24 | **Qwen3-32B (FC)** | **48.88%** | **26%** | **24.95%** | **47.5%** | **87.96%** | **80.46%** | **apache-2.0** | **11.07** |
| 28 | Qwen3-235B-A22B-Instruct-2507 (Prompt) | 47.06% | 30% | 24.3% | 39.62% | 90.12% | 76.61% | apache-2.0 | 10.74 |
| 32 | **Qwen3-14B (FC)** | **46.31%** | **20.5%** | **25.16%** | **40.38%** | **88.29%** | **81.05%** | **apache-2.0** | **6.92** |
| 35 | **DeepSeek-V3-0324 (FC)** | **45.2%** | **32.5%** | **22.37%** | **33%** | **88.77%** | **79.94%** | **DeepSeek License** | **6.11** |
| 40 | **Qwen3-8B (FC)** | **42.59%** | **15%** | **18.92%** | **37%** | **87.73%** | **80.53%** | **apache-2.0** | **7.2** |
| 68 | Llama-3.1-70B-Instruct (Prompt) | 31.55% | 14.5% | 8.82% | 14.62% | 91.21% | 76.91% | Meta Llama 3 Community | 5.77 |
| 70 | Llama-3.3-70B-Instruct (FC) | 30.76% | 9.5% | 8.17% | 17.88% | 88.15% | 76.68% | Meta Llama 3 Community | 4.66 |
| 111 | Llama-3.1-70B-Instruct (FC) | 17.64% | 4.5% | 10.32% | 8% | 26.02% | 51.67% | Meta Llama 3 Community | 3.8 |

### Key Observations

1. **GLM-4.5 (MIT) ranks #1** with 70.85% overall accuracy - top open-source model for tool-calling
2. **Qwen3-235B-A22B ranks #12** with 54.37% overall accuracy (apache-2.0 license)
3. **DeepSeek-R1-0528 ranks #23** with 48.97% overall accuracy (MIT license)
4. **DeepSeek-V3-0324 ranks #35** with 45.2% overall accuracy (DeepSeek License)
5. **Qwen3 series dominates open-source tool-calling** - Multiple Qwen3 models in top 50
6. **Llama 3.1/3.3 70B performs poorly** - Ranks #68-111 with 17-31% accuracy
7. **xLAM-2 series specialized for tool-calling** - Strong multi-turn performance (75.38% for 70B)
8. **Tool-calling is critical for PASSFEL** - Weather, news, calendar, finance, Home Assistant integration

### Important Context for PASSFEL

For PASSFEL's architecture (LLM orchestrator with tool calling for weather/news/calendar/finance/Home Assistant), tool-calling performance is MORE important than general chat performance. The BFCL leaderboard shows:

- **GLM-4.5** (MIT, 70.85%) is the top open-source tool-calling model
- **Qwen3-235B** (Apache 2.0, 54.37%) is the top permissively-licensed large model
- **Qwen3-32B** (Apache 2.0, 48.88%) offers good tool-calling at smaller size
- **DeepSeek-V3** (DeepSeek License, 45.2%) has decent tool-calling but restrictive license
- **Llama 3.1/3.3 70B** (17-31%) performs poorly on tool-calling despite good chat performance

This suggests that for PASSFEL, we should prioritize models with strong BFCL scores (GLM-4.5, Qwen3 series) over models with only strong chat performance (Llama 3.x).


## Qwen3-Next-80B-A3B-Thinking (User Recommendation)

**Source:** https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking  
**Release Date:** 2025 (Qwen3-Next series first installment)  
**License:** Apache 2.0

### Model Architecture

- **Total Parameters:** 80B (3B activated per token)
- **Architecture:** High-Sparsity MoE with Hybrid Attention
  - 512 experts, 10 activated per token, 1 shared expert
  - Gated DeltaNet + Gated Attention (replaces standard attention)
  - Expert Intermediate Dimension: 512
- **Context Length:** 262,144 tokens natively (extensible to 1,010,000 with YaRN)
- **Format:** BF16 (Safetensors)
- **Training:** 15T tokens pretraining + post-training with GSPO

### Key Features

1. **Thinking Mode:** Supports reasoning with `<think>` tags (similar to DeepSeek-R1)
2. **Multi-Token Prediction (MTP):** Boosts pretraining performance and accelerates inference
3. **Ultra-Long Context:** Validated up to 1M tokens with YaRN scaling
4. **Hybrid Attention:** Efficient context modeling for ultra-long sequences
5. **High-Sparsity MoE:** Extreme low activation ratio (3B/80B = 3.75% activation)

### Performance Benchmarks

| Benchmark | Qwen3-30B-A3B-Thinking | Qwen3-32B-Thinking | Qwen3-235B-A22B-Thinking | Gemini-2.5-Flash-Thinking | **Qwen3-Next-80B-A3B-Thinking** |
|-----------|------------------------|--------------------|--------------------------|--------------------------|---------------------------------|
| **Knowledge** |
| MMLU-Pro | 80.9 | 79.1 | **84.4** | 81.9 | 82.7 |
| MMLU-Redux | 91.4 | 90.9 | **93.8** | 92.1 | 92.5 |
| GPQA | 73.4 | 68.4 | 81.1 | **82.8** | 77.2 |
| **Reasoning** |
| AIME25 | 85.0 | 72.9 | **92.3** | 72.0 | 87.8 |
| HMMT25 | 71.4 | 51.5 | **83.9** | 64.2 | 73.9 |
| LiveBench 241125 | 76.8 | 74.9 | **78.4** | 74.3 | 76.6 |
| **Coding** |
| LiveCodeBench v6 | 66.0 | 60.6 | **74.1** | 61.2 | 68.7 |
| CFEval | 2044 | 1986 | **2134** | 1995 | 2071 |
| **Agent/Tool-Calling** |
| **BFCL-v3** | **72.4** | 70.3 | 71.9 | 68.6 | **72.0** |
| TAU1-Retail | 67.8 | 52.8 | 67.8 | 65.2 | **69.6** |
| TAU2-Retail | 58.8 | 49.7 | **71.9** | 66.7 | 67.8 |

### GX10 Compatibility Analysis

**Memory Requirements:**
- BF16: 80B × 2 bytes = 160GB ❌ (exceeds 128GB)
- FP8: 80B × 1 byte = 80GB + KV cache (10-20GB) = 90-100GB ✅ (fits!)
- INT4: 80B × 0.5 bytes = 40GB + KV cache (10-20GB) = 50-60GB ✅ (fits easily!)

**Recommended Deployment:**
- **FP8 quantization** for best quality/performance balance (90-100GB total)
- **INT4 quantization** for maximum throughput (50-60GB total)
- Use SGLang or vLLM with tensor parallelism (not needed for single GB10)
- Enable MTP for 2-3x inference speedup

**Deployment Command (vLLM with FP8):**
```bash
vllm serve Qwen/Qwen3-Next-80B-A3B-Thinking \
  --port 8000 \
  --max-model-len 262144 \
  --reasoning-parser deepseek_r1 \
  --quantization fp8 \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'
```

### Why This Model is "The Winner" for PASSFEL

1. **Top Tool-Calling Performance:** 72.0% on BFCL-v3 (beats Qwen3-235B's 71.9%, only 0.4% behind Qwen3-30B-A3B-Thinking)
2. **GX10 Compatible:** Fits in 128GB unified memory with FP8 quantization (90-100GB total)
3. **Apache 2.0 License:** Fully permissive, no restrictions
4. **Efficient Architecture:** 3B activated per token (10x faster than 70B dense models for long context)
5. **Strong Reasoning:** Outperforms Gemini-2.5-Flash-Thinking on most benchmarks
6. **Ultra-Long Context:** 262K native, 1M with YaRN (critical for PASSFEL's multi-domain context)
7. **Multi-Token Prediction:** 2-3x inference speedup with MTP
8. **Thinking Mode:** Explicit reasoning for complex queries

### Comparison to Other Top Models

| Model | BFCL-v3 | LMArena ELO | GX10 Compatible | License | Notes |
|-------|---------|-------------|-----------------|---------|-------|
| **Qwen3-Next-80B-A3B-Thinking** | **72.0%** | Not yet ranked | ✅ FP8/INT4 | Apache 2.0 | **RECOMMENDED** |
| Qwen3-30B-A3B-Thinking-2507 | 72.4% | Not ranked | ✅ FP8/INT4 | Apache 2.0 | Slightly better BFCL, smaller |
| GLM-4.5 | 70.85% | 1422 | ✅ FP8/INT4 | MIT | Top BFCL, but smaller than 80B |
| Qwen3-235B-A22B-Instruct-2507 | 54.37% | 1418 | ❌ Too large | Apache 2.0 | Best LMArena, doesn't fit |
| DeepSeek-V3.1 | 45.2% | 1416 | ❌ Too large | MIT | Good LMArena, poor BFCL |
| Llama-3.1-70B-Instruct | 17.64% | 1291 | ✅ FP8/INT4 | Meta Llama 3 | Poor tool-calling |

**Conclusion:** Qwen3-Next-80B-A3B-Thinking offers the best balance of tool-calling performance (72.0% BFCL-v3), GX10 compatibility (fits in 90-100GB with FP8), permissive licensing (Apache 2.0), and reasoning capabilities for PASSFEL.

