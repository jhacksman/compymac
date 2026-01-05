# Single-Machine Distributed Orchestrator

## Practical Implementation: Start Local, Scale Later

This document describes how to implement distributed agent orchestration **on a single machine** using Celery + Redis, while using **API calls** for heavy LLM inference.

---

## Why Single-Machine First?

1. **Simpler debugging** - all workers on one machine
2. **No network issues** - localhost communication only
3. **Same code** - can scale to multi-machine later
4. **Real benefits** - still get async execution, fault tolerance, monitoring

---

## Architecture (Single Machine)

```
┌─────────────────────────────────────────────────┐
│           Your Development Machine              │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │  Orchestrator (Python process)           │  │
│  │  - Receives user tasks                   │  │
│  │  - Routes to Celery queues              │  │
│  └────────────┬─────────────────────────────┘  │
│               │                                 │
│  ┌────────────▼─────────────────────────────┐  │
│  │  Redis (localhost:6379)                  │  │
│  │  - Message broker for Celery             │  │
│  │  - Artifact store (shared data)          │  │
│  └────────────┬─────────────────────────────┘  │
│               │                                 │
│       ┌───────┴────────┬─────────────┐        │
│       │                │             │        │
│  ┌────▼──────┐   ┌────▼──────┐ ┌───▼─────┐  │
│  │  Worker 1 │   │  Worker 2 │ │ Worker 3│  │
│  │  (Planner)│   │  (Executor)│ │(Reviewer)│ │
│  └────┬──────┘   └────┬──────┘ └───┬─────┘  │
│       │               │             │        │
│       └───────────────┴─────────────┘        │
│                       │                       │
│                       ▼                       │
│              ┌─────────────────┐              │
│              │ External APIs   │              │
│              │ - Venice.ai LLM │              │
│              │ - OpenAI        │              │
│              │ - locale2b      │              │
│              └─────────────────┘              │
└─────────────────────────────────────────────────┘
```

**Key Point:** Workers call **external APIs** for heavy work (LLM inference, sandboxing), so your machine just orchestrates - it doesn't need GPUs!

---

## Step-by-Step Implementation

### **Phase 0: Prerequisites** (5 minutes)

```bash
# Install Redis
# macOS:
brew install redis
brew services start redis

# Linux:
sudo apt-get install redis-server
sudo systemctl start redis

# Verify
redis-cli ping  # Should respond: PONG

# Install Python dependencies
pip install celery redis
```

### **Phase 1: Convert Artifact Store to Redis** (30 minutes)

**Current:** In-memory Python dict
**New:** Redis-backed distributed store

```python
# src/compymac/distributed/artifact_store.py

import pickle
from typing import Any, Optional
from datetime import timedelta
from redis import Redis

class DistributedArtifactStore:
    """
    Redis-backed artifact store for sharing data between workers.

    Works on single machine (localhost:6379) or distributed (redis cluster).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = Redis.from_url(redis_url, decode_responses=False)

    def store(
        self,
        artifact_id: str,
        data: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """
        Store artifact with optional TTL.

        Args:
            artifact_id: Unique identifier
            data: Any picklable Python object
            ttl: Time to live (default: 24 hours)
        """
        key = f"artifact:{artifact_id}"
        serialized = pickle.dumps(data)

        if ttl:
            self.redis.setex(key, ttl, serialized)
        else:
            self.redis.setex(key, timedelta(hours=24), serialized)

    def get(self, artifact_id: str) -> Optional[Any]:
        """Retrieve artifact by ID."""
        key = f"artifact:{artifact_id}"
        data = self.redis.get(key)

        if data is None:
            return None

        return pickle.loads(data)

    def delete(self, artifact_id: str) -> None:
        """Delete artifact."""
        key = f"artifact:{artifact_id}"
        self.redis.delete(key)

    def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists."""
        key = f"artifact:{artifact_id}"
        return self.redis.exists(key) > 0


# Usage example:
store = DistributedArtifactStore()

# Store a plan
plan = {"steps": ["localize", "fix", "verify"], "status": "in_progress"}
store.store("plan-123", plan)

# Retrieve from another worker
retrieved_plan = store.get("plan-123")
```

**Test it:**

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Test the store
python -c "
from compymac.distributed.artifact_store import DistributedArtifactStore

store = DistributedArtifactStore()
store.store('test-123', {'message': 'Hello from worker!'})
print('Stored artifact')
"

# Terminal 3: Verify it's in Redis
redis-cli
> GET artifact:test-123
# Should see pickled data
```

---

### **Phase 2: Create Celery Workers** (1 hour)

**New file:** `src/compymac/distributed/celery_app.py`

```python
"""
Celery application for distributed task execution.

Run workers with:
    celery -A compymac.distributed.celery_app worker --loglevel=info
"""

from celery import Celery
from kombu import Queue

# Create Celery app
app = Celery(
    'compymac',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

# Configure Celery
app.conf.update(
    task_serializer='pickle',  # Support complex Python objects
    accept_content=['pickle', 'json'],
    result_serializer='pickle',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'compymac.distributed.tasks.plan_task': {'queue': 'planning'},
        'compymac.distributed.tasks.execute_step': {'queue': 'execution'},
        'compymac.distributed.tasks.review_result': {'queue': 'review'},
    },

    # Define queues
    task_queues=(
        Queue('planning', routing_key='planning'),
        Queue('execution', routing_key='execution'),
        Queue('review', routing_key='review'),
        Queue('default', routing_key='default'),
    ),
)
```

**New file:** `src/compymac/distributed/tasks.py`

```python
"""
Celery tasks for distributed agent operations.
"""

from celery import Task
from typing import Any, Dict
import logging

from compymac.distributed.celery_app import app
from compymac.distributed.artifact_store import DistributedArtifactStore
from compymac.llm import LLMClient
from compymac.multi_agent import PlannerAgent, ExecutorAgent, ReflectorAgent

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3)
def plan_task(self, goal: str, context: Dict[str, Any]) -> str:
    """
    Planning task - calls Venice.ai API for LLM inference.

    Args:
        goal: User's goal
        context: Contextual information

    Returns:
        artifact_id: ID of stored plan in Redis
    """
    try:
        logger.info(f"Planning task for goal: {goal}")

        # Create planner (uses LLMClient -> Venice.ai API)
        planner = PlannerAgent(llm=LLMClient())

        # Generate plan (API call to Venice.ai)
        plan = planner.create_plan(goal, context)

        # Store plan in Redis
        store = DistributedArtifactStore()
        artifact_id = f"plan-{self.request.id}"
        store.store(artifact_id, plan)

        logger.info(f"Plan created: {artifact_id}")
        return artifact_id

    except Exception as e:
        logger.error(f"Planning failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@app.task(bind=True, max_retries=3)
def execute_step(self, step: Dict[str, Any], workspace_path: str) -> str:
    """
    Execute a plan step - may use locale2b API for sandboxed execution.

    Args:
        step: Plan step to execute
        workspace_path: Git worktree path

    Returns:
        artifact_id: ID of stored result in Redis
    """
    try:
        logger.info(f"Executing step: {step['description']}")

        # Create executor
        executor = ExecutorAgent(workspace=workspace_path)

        # Execute step (may call locale2b API for sandbox, Venice.ai for LLM)
        result = executor.execute(step)

        # Store result in Redis
        store = DistributedArtifactStore()
        artifact_id = f"result-{self.request.id}"
        store.store(artifact_id, result)

        logger.info(f"Step executed: {artifact_id}")
        return artifact_id

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@app.task(bind=True, max_retries=3)
def review_result(self, result_artifact_id: str) -> Dict[str, Any]:
    """
    Review execution result - calls Venice.ai API for LLM review.

    Args:
        result_artifact_id: ID of result to review

    Returns:
        review: Review decision and feedback
    """
    try:
        logger.info(f"Reviewing result: {result_artifact_id}")

        # Retrieve result from Redis
        store = DistributedArtifactStore()
        result = store.get(result_artifact_id)

        # Create reviewer (uses LLMClient -> Venice.ai API)
        reviewer = ReflectorAgent(llm=LLMClient())

        # Review result (API call to Venice.ai)
        review = reviewer.review(result)

        logger.info(f"Review complete: {review['action']}")
        return review

    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

**Test it:**

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A compymac.distributed.celery_app worker --loglevel=info --queues=planning,execution,review

# Terminal 3: Submit a test task
python -c "
from compymac.distributed.tasks import plan_task

# Submit task (async)
result = plan_task.delay('Fix authentication bug', {})
print(f'Task submitted: {result.id}')

# Wait for result (blocking)
artifact_id = result.get(timeout=30)
print(f'Plan artifact ID: {artifact_id}')
"
```

---

### **Phase 3: Create Distributed Orchestrator** (1 hour)

**New file:** `src/compymac/distributed/orchestrator.py`

```python
"""
Distributed orchestrator - routes tasks to Celery workers.
"""

from typing import Dict, Any, List
from celery import group, chain, chord
import logging

from compymac.distributed.tasks import plan_task, execute_step, review_result
from compymac.distributed.artifact_store import DistributedArtifactStore

logger = logging.getLogger(__name__)


class DistributedOrchestrator:
    """
    Orchestrates multi-agent workflows using Celery workers.

    Works on single machine or distributed cluster - same code!
    """

    def __init__(self):
        self.store = DistributedArtifactStore()

    def execute_workflow(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute complete multi-agent workflow.

        Pipeline:
        1. Planning (async, single worker)
        2. Execution (async, parallel workers)
        3. Review (async, single worker)

        Args:
            goal: User's goal
            context: Contextual information

        Returns:
            Final result with all artifacts
        """
        logger.info(f"Starting workflow for: {goal}")

        # Step 1: Planning (single task)
        plan_result = plan_task.delay(goal, context)
        plan_artifact_id = plan_result.get(timeout=60)

        # Retrieve plan from Redis
        plan = self.store.get(plan_artifact_id)
        logger.info(f"Plan has {len(plan['steps'])} steps")

        # Step 2: Execution (parallel tasks for independent steps)
        execution_tasks = []
        for step in plan['steps']:
            if step.get('can_parallelize', False):
                # Submit parallel
                task = execute_step.delay(step, plan['workspace'])
                execution_tasks.append(task)
            else:
                # Wait for previous to complete
                if execution_tasks:
                    # Block until previous tasks complete
                    for t in execution_tasks:
                        t.get(timeout=300)
                    execution_tasks = []

                # Submit sequential
                task = execute_step.delay(step, plan['workspace'])
                execution_tasks.append(task)

        # Wait for all execution tasks
        execution_results = [t.get(timeout=300) for t in execution_tasks]
        logger.info(f"Executed {len(execution_results)} steps")

        # Step 3: Review (single task, depends on all executions)
        # Use Celery's chord: multiple tasks -> single callback
        review_task = review_result.delay(execution_results[-1])
        review = review_task.get(timeout=60)

        logger.info(f"Workflow complete: {review['action']}")

        return {
            'plan_artifact_id': plan_artifact_id,
            'execution_results': execution_results,
            'review': review
        }

    def execute_parallel_rollouts(
        self,
        goal: str,
        n: int = 3,
        early_termination: bool = True
    ) -> Dict[str, Any]:
        """
        Execute N parallel rollouts (best-of-N sampling).

        With early_termination=True, returns as soon as first succeeds.

        Args:
            goal: User's goal
            n: Number of parallel attempts
            early_termination: Stop when first succeeds

        Returns:
            Best result from N rollouts
        """
        logger.info(f"Starting {n} parallel rollouts")

        # Submit N planning tasks in parallel
        planning_tasks = [plan_task.delay(goal, {}) for _ in range(n)]

        if early_termination:
            # Wait for first success
            from celery.result import allow_join_result
            for task in planning_tasks:
                try:
                    result = task.get(timeout=60)
                    logger.info(f"First rollout succeeded: {result}")

                    # Cancel remaining tasks
                    for t in planning_tasks:
                        if t.id != task.id:
                            t.revoke(terminate=True)

                    return {'winner': result, 'strategy': 'early_termination'}
                except Exception:
                    continue
        else:
            # Wait for all, then pick best
            results = [t.get(timeout=60) for t in planning_tasks]
            # TODO: Implement best-of-N selection logic
            return {'results': results, 'strategy': 'best_of_n'}
```

**Test it:**

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
celery -A compymac.distributed.celery_app worker --loglevel=info

# Terminal 3: Run workflow
python -c "
from compymac.distributed.orchestrator import DistributedOrchestrator

orchestrator = DistributedOrchestrator()
result = orchestrator.execute_workflow(
    goal='Fix authentication bug',
    context={'repo': '/path/to/repo'}
)
print(f'Workflow complete: {result}')
"
```

---

## Benefits (Even on Single Machine!)

### **1. Async Execution**
```python
# Before (blocking):
plan = planner.create_plan(goal)  # Blocks for 5 seconds
result = executor.execute(plan)    # Blocks for 30 seconds

# After (async):
plan_task = plan_task.delay(goal)  # Returns immediately
# Do other work while planning happens...
plan = plan_task.get()  # Block only when you need the result
```

### **2. Fault Tolerance**
```python
# Task fails -> automatic retry with exponential backoff
@app.task(bind=True, max_retries=3)
def execute_step(self, step):
    try:
        return executor.execute(step)
    except TransientError as e:
        # Retries: 2s, 4s, 8s delays
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

### **3. Monitoring**
```bash
# Install Flower (Celery monitoring tool)
pip install flower

# Start Flower
celery -A compymac.distributed.celery_app flower

# Open browser: http://localhost:5555
# See: active tasks, worker status, task history, graphs
```

### **4. Parallel Execution**
```python
# Execute multiple steps in parallel on one machine
from celery import group

job = group(
    execute_step.s(step1),
    execute_step.s(step2),
    execute_step.s(step3),
)
results = job.apply_async()
```

---

## Scaling to Multi-Machine Later

**When you're ready**, just change the Redis URL and start workers on other machines:

```bash
# Machine 1 (orchestrator + Redis):
redis-server --bind 0.0.0.0

# Machine 2 (worker):
export CELERY_BROKER_URL=redis://machine1:6379/0
celery -A compymac.distributed.celery_app worker --queues=execution

# Machine 3 (worker):
export CELERY_BROKER_URL=redis://machine1:6379/0
celery -A compymac.distributed.celery_app worker --queues=planning,review
```

**No code changes needed!** The same `DistributedOrchestrator` works locally or distributed.

---

## Cost-Effective Strategy

Since CompyMac uses **API calls** for heavy work, your local machine just orchestrates:

```
Your Machine (cheap):
├─ Orchestrator (CPU only, ~2GB RAM)
├─ Redis (CPU only, ~1GB RAM)
└─ Celery workers (CPU only, ~2GB RAM each)
    └─ Workers call external APIs:
        ├─ Venice.ai ($0.40/M tokens) - LLM inference
        ├─ locale2b API - Firecracker sandboxes
        └─ Future: Playwright as a service

Total cost for orchestrator: ~$0
Pay only for API usage!
```

Compare to running local LLM:
- DGX box: $40,000+ upfront + electricity
- vs Venice.ai API: Pay per use, no hardware

---

## Next Steps

1. **Implement Phase 1** - Redis artifact store (30 min)
2. **Implement Phase 2** - Celery tasks (1 hour)
3. **Implement Phase 3** - Orchestrator (1 hour)
4. **Test on single machine** (1 hour)
5. **When ready** - Scale to multi-machine (just change Redis URL!)

**Total time to working single-machine distributed orchestrator: ~3-4 hours**

Then you can scale to DGX boxes around the world when needed!
