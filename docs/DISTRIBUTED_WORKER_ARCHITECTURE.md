# Distributed Worker Architecture: Heterogeneous Global Worker Pool

## Overview

This document describes how CompyMac's distributed agent orchestrator routes tasks to specialized workers based on **hardware capabilities** and **geographic location**.

---

## Worker Types and Capabilities

### 1. **GPU Workers** (DGX/Spark Boxes with A100/H100)

**Location:** Tokyo, London, San Francisco
**Hardware:**
- 8x NVIDIA A100 80GB (or 4x H100)
- 512GB+ RAM
- 2TB NVMe SSD

**Capabilities:**
```python
@dataclass
class GPUWorkerProfile:
    worker_id: str = "dgx-tokyo-01"
    capabilities: list[AgentCapability] = [
        AgentCapability.CODING,          # Code generation with local LLM
        AgentCapability.PLANNING,        # Plan generation with local LLM
        AgentCapability.REVIEWING,       # Code review with local LLM
        AgentCapability.RESEARCH,        # Information synthesis with local LLM
    ]

    # Hardware-specific capabilities
    hardware_capabilities: dict = {
        "llm_inference": {
            "model": "qwen3-235b",
            "max_context": 128_000,
            "tokens_per_second": 50,
            "concurrent_requests": 8
        },
        "vision_models": {
            "model": "qwen2-vl-72b",
            "supports_ocr": True,
            "supports_image_gen": False
        },
        "code_analysis": {
            "tool": "jedi",
            "language_support": ["python", "javascript", "typescript"]
        }
    }

    # Geographic info
    location: str = "Tokyo, Japan"
    latency_to_orchestrator_ms: int = 45
```

**Workloads:**
- LLM inference (code generation, planning, review)
- Multimodal vision tasks (screenshot analysis, PDF OCR)
- Heavy code analysis (AST parsing, dependency graphs)

---

### 2. **Browser Workers** (Cloud VMs with Playwright + VNC)

**Location:** AWS us-east-1, GCP europe-west1, Azure eastasia
**Hardware:**
- 16 vCPU
- 64GB RAM
- No GPU needed

**Capabilities:**
```python
@dataclass
class BrowserWorkerProfile:
    worker_id: str = "browser-aws-useast-03"
    capabilities: list[AgentCapability] = [
        AgentCapability.BROWSER_OPERATIONS,  # Playwright automation
        AgentCapability.RESEARCH,            # Web scraping
    ]

    hardware_capabilities: dict = {
        "browser_automation": {
            "tool": "playwright",
            "headless": False,
            "vnc_port": 5900,
            "recording": True,
            "concurrent_sessions": 4
        },
        "network": {
            "bandwidth_mbps": 1000,
            "proxy_support": True,
            "captcha_solving": True
        }
    }

    location: str = "Virginia, USA"
    latency_to_orchestrator_ms: int = 12
```

**Workloads:**
- Web automation (form filling, data extraction)
- Visual testing (screenshot comparison)
- Interactive debugging (VNC access to live browser)

---

### 3. **Sandbox Workers** (Firecracker microVM hosts)

**Location:** On-prem data centers, cloud regions
**Hardware:**
- 64 vCPU (AMD EPYC or Intel Xeon)
- 256GB RAM
- Fast SSD for VM snapshots

**Capabilities:**
```python
@dataclass
class SandboxWorkerProfile:
    worker_id: str = "sandbox-onprem-01"
    capabilities: list[AgentCapability] = [
        AgentCapability.SHELL_OPERATIONS,   # Bash commands in isolated VMs
        AgentCapability.TESTING,            # Test execution
        AgentCapability.FILE_OPERATIONS,    # Safe file operations
    ]

    hardware_capabilities: dict = {
        "virtualization": {
            "platform": "firecracker",  # CompyMac already uses this via locale2b!
            "concurrent_vms": 32,
            "boot_time_ms": 125,
            "snapshot_support": True
        },
        "isolation": {
            "network_isolation": True,
            "filesystem_isolation": True,
            "resource_limits": {
                "max_memory_mb": 2048,
                "max_vcpu": 2,
                "max_disk_mb": 10240
            }
        }
    }

    location: str = "On-premises DC"
    latency_to_orchestrator_ms: int = 8
```

**Workloads:**
- Running untrusted code (user-submitted scripts)
- Test suite execution (CI/CD)
- Shell command execution (git, npm, pip, etc.)

---

### 4. **Orchestrator** (Central coordinator)

**Location:** Primary region (e.g., us-east-1)
**Hardware:**
- 8-16 vCPU
- 32GB RAM
- High-bandwidth network

**Responsibilities:**
```python
class DistributedOrchestrator:
    """
    Central orchestrator that routes tasks to appropriate workers
    based on capabilities, load, and latency.
    """

    def __init__(self):
        self.worker_registry: dict[str, WorkerProfile] = {}
        self.message_queue = Celery(broker="redis://orchestrator:6379")
        self.artifact_store = RedisArtifactStore()

    async def route_task(self, task: Task) -> str:
        """
        Route task to best available worker.

        Decision factors:
        1. Required capabilities (MUST match)
        2. Hardware requirements (GPU, memory, etc.)
        3. Current load (prefer less loaded workers)
        4. Geographic latency (prefer closer workers)
        5. Cost (prefer cheaper workers if capabilities equal)
        """

        # Filter workers with required capabilities
        candidates = [
            w for w in self.worker_registry.values()
            if self._has_capabilities(w, task.required_capabilities)
        ]

        # Filter by hardware requirements
        if task.requires_gpu:
            candidates = [w for w in candidates if w.has_gpu]

        # Sort by composite score
        scored = [
            (worker, self._score_worker(worker, task))
            for worker in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return best worker
        best_worker = scored[0][0]
        return best_worker.worker_id

    def _score_worker(self, worker: WorkerProfile, task: Task) -> float:
        """
        Composite scoring:
        - Capability match: 40%
        - Current load: 30%
        - Latency: 20%
        - Cost: 10%
        """
        capability_score = self._capability_match_score(worker, task)
        load_score = 1.0 - (worker.current_load / worker.max_load)
        latency_score = 1.0 - (worker.latency_ms / 500)  # Normalize to 500ms max
        cost_score = 1.0 - (worker.cost_per_hour / 10.0)  # Normalize to $10/hr max

        return (
            0.4 * capability_score +
            0.3 * load_score +
            0.2 * latency_score +
            0.1 * cost_score
        )
```

---

## Concrete Example: Multi-Step SWE Task

Let's trace a real CompyMac workflow distributed across workers:

### **User Request:** "Fix the authentication bug in the login flow"

```
Step 1: PLANNING
├─ Orchestrator receives task
├─ Routes to: DGX-Tokyo-01 (has LLM for planning)
├─ Worker generates plan:
│  1. Localize bug (read code, run tests)
│  2. Understand root cause
│  3. Implement fix
│  4. Verify with tests
└─ Stores plan in RedisArtifactStore

Step 2: LOCALIZATION (Read files, run tests)
├─ Orchestrator receives PlanStep[0]: "Localize bug"
├─ Requires: FILE_OPERATIONS + SHELL_OPERATIONS
├─ Routes to: Sandbox-OnPrem-01 (Firecracker VM)
├─ Worker executes:
│  - Read src/auth/login.py
│  - Run: pytest tests/test_login.py -v
│  - Capture stack trace
└─ Stores artifacts: {code_snapshot, test_output}

Step 3: UNDERSTANDING (LLM analysis)
├─ Orchestrator receives PlanStep[1]: "Understand root cause"
├─ Requires: CODING + DEBUGGING capabilities
├─ Routes to: DGX-London-02 (closer to user, has GPU)
├─ Worker:
│  - Fetches artifacts from Redis
│  - Runs LLM inference: "Analyze stack trace + code"
│  - Generates diagnosis
└─ Stores artifact: {root_cause_analysis}

Step 4: FIX IMPLEMENTATION (Code generation)
├─ Orchestrator receives PlanStep[2]: "Implement fix"
├─ Requires: CODING capability
├─ Routes to: DGX-London-02 (same worker, keeps context warm)
├─ Worker:
│  - Generates patch using LLM
│  - Validates syntax with Jedi
└─ Stores artifact: {code_patch}

Step 5: VERIFICATION (Browser + Tests)
├─ Orchestrator receives PlanStep[3]: "Verify fix"
├─ Requires: BROWSER_OPERATIONS + SHELL_OPERATIONS
├─ Routes to TWO workers in parallel:
│
│  Worker A: Browser-AWS-USEast-03
│  ├─ Apply patch in isolated workspace
│  ├─ Start local dev server
│  ├─ Open Playwright browser (headless=False)
│  ├─ VNC stream available at vnc://browser-aws-useast-03:5900
│  ├─ Execute: "Navigate to /login, fill form, submit"
│  └─ Capture: screenshot + network logs
│
│  Worker B: Sandbox-OnPrem-01
│  ├─ Apply patch in Firecracker VM
│  ├─ Run: pytest tests/test_login.py -v
│  ├─ Run: pytest tests/test_auth.py -v (regression check)
│  └─ Capture: test results + coverage
│
└─ Orchestrator aggregates results

Step 6: REVIEW (LLM reflection)
├─ Orchestrator receives all verification artifacts
├─ Requires: REVIEWING capability
├─ Routes to: DGX-Tokyo-01 (cheapest idle GPU worker)
├─ Worker:
│  - Reviews: patch quality, test results, browser logs
│  - Generates: final report + recommendations
└─ Returns to user
```

---

## Advantages of Geographic Distribution

### **1. Latency Optimization**

```python
# User in Tokyo submits task
user_location = "Tokyo"

# Orchestrator picks geographically close worker for interactive tasks
if task.requires_user_interaction:
    workers = [w for w in workers if w.region == "asia-pacific"]
```

**Example:** User debugging a browser issue gets VNC stream from `browser-tokyo-01` (10ms latency) instead of `browser-virginia-03` (180ms latency)

### **2. Follow-the-Sun Operation**

```python
# Route heavy LLM inference to workers in "night" regions
# where electricity is cheaper and cooling is easier

current_hour_utc = datetime.now(UTC).hour

if 0 <= current_hour_utc < 8:
    # Night in Americas, day in Asia/Europe
    preferred_regions = ["asia-pacific", "europe"]
elif 8 <= current_hour_utc < 16:
    # Night in Asia, day in Europe/Americas
    preferred_regions = ["europe", "americas"]
else:
    # Night in Europe, day in Americas/Asia
    preferred_regions = ["americas", "asia-pacific"]
```

### **3. Fault Tolerance**

```python
# If DGX-Tokyo-01 goes offline, orchestrator automatically
# routes to next best worker

@celery.task(bind=True, max_retries=3)
def execute_llm_inference(self, prompt: str, worker_id: str):
    try:
        return workers[worker_id].generate(prompt)
    except WorkerOffline:
        # Find alternative worker with same capabilities
        alt_worker = orchestrator.find_alternative_worker(
            original=worker_id,
            capabilities=["CODING"]
        )
        # Retry on alternative worker
        return workers[alt_worker].generate(prompt)
```

---

## CompyMac's Current State

CompyMac **already has** the building blocks:

✅ **locale2b integration** (Firecracker sandbox service)
✅ **Playwright browser tools**
✅ **Multi-agent coordination** (Manager/Planner/Executor/Reflector)
✅ **Capability-based routing** (DynamicOrchestrator)
✅ **Artifact handoffs** (agent_handoffs.py)
✅ **Workspace isolation** (Git worktrees)

**What's missing for true distribution:**

❌ Message queue (Redis/Celery) - currently uses ThreadPoolExecutor
❌ Distributed artifact store - currently in-memory Python dict
❌ Worker registration/discovery - currently hardcoded agents
❌ Cross-machine workspace sharing - currently local git worktrees
❌ Hardware capability advertising - currently only software capabilities

---

## Implementation Roadmap

### **Phase 1: Single-Machine Distribution** (Proof of Concept)
1. Replace ThreadPoolExecutor with Celery + Redis
2. Move ArtifactStore to Redis
3. Test with workers on same machine

### **Phase 2: Multi-Machine Distribution** (Local Network)
4. Add worker registration protocol
5. Test with 2-3 machines on LAN
6. Add NFS/S3 for shared workspace

### **Phase 3: Global Distribution** (Production)
7. Deploy workers across regions (AWS, GCP, on-prem)
8. Add geographic routing logic
9. Implement fault tolerance and failover
10. Add monitoring and observability

### **Phase 4: Hardware Specialization**
11. Add GPU worker support (DGX/Spark boxes)
12. Add VNC streaming for browser workers
13. Optimize locale2b for distributed deployment
14. Implement cost-aware routing

---

## Monitoring a Distributed Workflow

```python
# Real-time workflow visualization

{
  "task_id": "fix-auth-bug-12345",
  "status": "in_progress",
  "steps": [
    {
      "step": "planning",
      "worker": "dgx-tokyo-01",
      "status": "completed",
      "duration_ms": 2340,
      "tokens_used": 8234
    },
    {
      "step": "localization",
      "worker": "sandbox-onprem-01",
      "status": "completed",
      "duration_ms": 15670,
      "vm_id": "fc-vm-8a7f3b2c"
    },
    {
      "step": "verification",
      "worker": "browser-aws-useast-03",
      "status": "in_progress",
      "duration_ms": 4523,
      "vnc_url": "vnc://browser-aws-useast-03:5900",
      "screenshot_url": "https://artifacts.compymac.io/screenshots/12345-step3.png"
    }
  ],
  "total_cost_usd": 0.47,
  "estimated_completion_sec": 12
}
```

Users can **watch live** as tasks hop between workers around the world!

---

## Summary

**Your vision is correct!** Distributed agent orchestration means:

- ✅ **DGX/Spark boxes** in different locations handling LLM inference
- ✅ **Cloud VMs** running Playwright with VNC for interactive debugging
- ✅ **Firecracker hosts** executing sandboxed commands safely
- ✅ **Geographic routing** for latency optimization
- ✅ **Capability-based task assignment** to specialized workers
- ✅ **Fault tolerance** across worker failures

CompyMac has the software architecture ready - it just needs the distributed infrastructure layer to connect workers across machines/regions!
