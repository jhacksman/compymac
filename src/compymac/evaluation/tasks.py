"""
Task Bank for CompyMac Evaluation.

These are real tasks that CompyMac will solve using Venice.ai.
No mocking, no scripted responses - just real problems.
"""

from dataclasses import dataclass, field
from enum import Enum


class TaskCategory(Enum):
    """Categories of evaluation tasks."""
    CODE_FIX = "code_fix"  # Fix a bug in code
    CODE_REFACTOR = "code_refactor"  # Refactor/improve code
    CODE_FEATURE = "code_feature"  # Add a new feature
    FILE_OPS = "file_ops"  # File system operations
    RESEARCH = "research"  # Web search and synthesis
    ANALYSIS = "analysis"  # Analyze code/data
    MULTI_STEP = "multi_step"  # Complex multi-step tasks


@dataclass
class Task:
    """A single evaluation task."""
    id: str
    category: TaskCategory
    prompt: str
    description: str
    success_criteria: str  # How to verify success (human-readable)
    max_steps: int = 30
    timeout_seconds: int = 300
    tags: list[str] = field(default_factory=list)


# The Task Bank - Real problems for CompyMac to solve
TASK_BANK: list[Task] = [
    # CODE_FIX tasks
    Task(
        id="fix_001",
        category=TaskCategory.CODE_FIX,
        prompt="""Create a Python file at /tmp/eval_fix_001/buggy.py with this code:

def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)

Then fix the bug: it crashes when given an empty list. Add proper error handling.""",
        description="Fix division by zero bug in average function",
        success_criteria="File exists, function handles empty list without crashing",
        tags=["python", "error-handling"],
    ),
    Task(
        id="fix_002",
        category=TaskCategory.CODE_FIX,
        prompt="""Create a Python file at /tmp/eval_fix_002/parser.py with this code:

import json

def parse_config(config_str):
    config = json.loads(config_str)
    return config['database']['host']

Then fix it to handle: 1) Invalid JSON, 2) Missing 'database' key, 3) Missing 'host' key.
Return None for any error case.""",
        description="Fix JSON parsing with missing keys",
        success_criteria="Function returns None for all error cases instead of crashing",
        tags=["python", "json", "error-handling"],
    ),
    Task(
        id="fix_003",
        category=TaskCategory.CODE_FIX,
        prompt="""Create a file at /tmp/eval_fix_003/counter.py with this code:

class Counter:
    count = 0  # Bug: class variable instead of instance variable

    def increment(self):
        self.count += 1
        return self.count

Fix the bug so each Counter instance has its own count.""",
        description="Fix class variable vs instance variable bug",
        success_criteria="Each Counter instance maintains separate count",
        tags=["python", "oop"],
    ),

    # CODE_REFACTOR tasks
    Task(
        id="refactor_001",
        category=TaskCategory.CODE_REFACTOR,
        prompt="""Create a file at /tmp/eval_refactor_001/messy.py with this code:

def process(d):
    if d['type'] == 'A':
        if d['status'] == 'active':
            if d['value'] > 100:
                return d['value'] * 2
            else:
                return d['value']
        else:
            return 0
    else:
        if d['status'] == 'active':
            return d['value'] * 3
        else:
            return d['value']

Refactor to reduce nesting and improve readability. Use early returns.""",
        description="Refactor deeply nested conditionals",
        success_criteria="Code has max 2 levels of nesting, same behavior",
        tags=["python", "refactoring"],
    ),
    Task(
        id="refactor_002",
        category=TaskCategory.CODE_REFACTOR,
        prompt="""Create a file at /tmp/eval_refactor_002/duplicated.py with this code:

def get_user_email(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_name(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

Refactor to eliminate duplication using a helper function or context manager.""",
        description="Refactor duplicated database code",
        success_criteria="No duplicated connection/cursor code",
        tags=["python", "refactoring", "dry"],
    ),

    # CODE_FEATURE tasks
    Task(
        id="feature_001",
        category=TaskCategory.CODE_FEATURE,
        prompt="""Create a Python module at /tmp/eval_feature_001/cache.py that implements a simple LRU cache:

1. Class LRUCache with __init__(capacity: int)
2. Method get(key) -> value or None
3. Method put(key, value) -> None
4. When capacity is exceeded, evict least recently used item

Include a simple test at the bottom that demonstrates it works.""",
        description="Implement LRU cache from scratch",
        success_criteria="LRU cache works correctly, evicts oldest items",
        tags=["python", "data-structures"],
    ),
    Task(
        id="feature_002",
        category=TaskCategory.CODE_FEATURE,
        prompt="""Create a Python file at /tmp/eval_feature_002/retry.py that implements a retry decorator:

1. @retry(max_attempts=3, delay=1.0, exceptions=(Exception,))
2. Retries the decorated function up to max_attempts times
3. Waits delay seconds between attempts
4. Only catches specified exceptions
5. Raises the last exception if all attempts fail

Include a test that shows it working with a function that fails twice then succeeds.""",
        description="Implement retry decorator",
        success_criteria="Decorator retries correctly, respects max_attempts",
        tags=["python", "decorators"],
    ),

    # FILE_OPS tasks
    Task(
        id="file_001",
        category=TaskCategory.FILE_OPS,
        prompt="""Create a directory structure at /tmp/eval_file_001/:
- src/
  - main.py (with print("Hello"))
  - utils/
    - helpers.py (with def greet(): return "Hi")
- tests/
  - test_main.py (empty file)
- README.md (with "# My Project")

Then list all files recursively and report the structure.""",
        description="Create directory structure",
        success_criteria="All files and directories exist with correct content",
        tags=["filesystem"],
    ),
    Task(
        id="file_002",
        category=TaskCategory.FILE_OPS,
        prompt="""Create 5 text files at /tmp/eval_file_002/:
- file1.txt with "apple"
- file2.txt with "banana"
- file3.txt with "cherry"
- file4.txt with "date"
- file5.txt with "elderberry"

Then create a combined.txt that contains all fruits, one per line, sorted alphabetically.""",
        description="Create and combine text files",
        success_criteria="combined.txt exists with sorted fruits",
        tags=["filesystem"],
    ),

    # RESEARCH tasks
    Task(
        id="research_001",
        category=TaskCategory.RESEARCH,
        prompt="""Use web search to find the current Python version (as of late 2024/2025).
Write the version number to /tmp/eval_research_001/python_version.txt.
Include the source URL on the second line.""",
        description="Research current Python version",
        success_criteria="File contains valid Python version and source URL",
        tags=["web-search"],
    ),
    Task(
        id="research_002",
        category=TaskCategory.RESEARCH,
        prompt="""Use web search to find 3 popular Python web frameworks.
Create /tmp/eval_research_002/frameworks.md with:
- Framework name
- One-sentence description
- Official website URL

Format as a markdown list.""",
        description="Research Python web frameworks",
        success_criteria="File contains 3 frameworks with descriptions and URLs",
        tags=["web-search"],
    ),

    # ANALYSIS tasks
    Task(
        id="analysis_001",
        category=TaskCategory.ANALYSIS,
        prompt="""Create a Python file at /tmp/eval_analysis_001/data.py with:

DATA = [
    {"name": "Alice", "age": 30, "dept": "Engineering"},
    {"name": "Bob", "age": 25, "dept": "Marketing"},
    {"name": "Charlie", "age": 35, "dept": "Engineering"},
    {"name": "Diana", "age": 28, "dept": "Sales"},
    {"name": "Eve", "age": 32, "dept": "Engineering"},
]

Then analyze this data and write to /tmp/eval_analysis_001/report.txt:
1. Average age
2. Count per department
3. Oldest and youngest person""",
        description="Analyze data and generate report",
        success_criteria="Report contains correct statistics",
        tags=["python", "data-analysis"],
    ),

    # MULTI_STEP tasks
    Task(
        id="multi_001",
        category=TaskCategory.MULTI_STEP,
        prompt="""Complete these steps in order:

1. Create /tmp/eval_multi_001/config.json with: {"version": "1.0", "debug": true}
2. Create /tmp/eval_multi_001/app.py that reads config.json and prints the version
3. Run app.py and capture the output
4. Create /tmp/eval_multi_001/output.txt with the captured output
5. Update config.json to version "2.0"
6. Run app.py again and append new output to output.txt""",
        description="Multi-step config and execution task",
        success_criteria="output.txt contains both version outputs",
        tags=["multi-step", "python", "json"],
        max_steps=40,
    ),
    Task(
        id="multi_002",
        category=TaskCategory.MULTI_STEP,
        prompt="""Build a simple CLI calculator:

1. Create /tmp/eval_multi_002/calc.py with functions: add, subtract, multiply, divide
2. Add a main() that takes args: python calc.py add 5 3 -> prints 8
3. Handle division by zero gracefully
4. Test all 4 operations by running the script
5. Create /tmp/eval_multi_002/test_results.txt with the test outputs""",
        description="Build and test CLI calculator",
        success_criteria="calc.py works for all operations, test_results.txt has outputs",
        tags=["multi-step", "python", "cli"],
        max_steps=40,
    ),

    # Additional diverse tasks
    Task(
        id="fix_004",
        category=TaskCategory.CODE_FIX,
        prompt="""Create /tmp/eval_fix_004/sort.py with this buggy code:

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - 1):  # Bug: should be n - i - 1
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

Fix the inefficiency bug (inner loop does unnecessary comparisons).
Test with [64, 34, 25, 12, 22, 11, 90] and verify it sorts correctly.""",
        description="Fix bubble sort inefficiency",
        success_criteria="Optimized inner loop, correct sorting",
        tags=["python", "algorithms"],
    ),
    Task(
        id="feature_003",
        category=TaskCategory.CODE_FEATURE,
        prompt="""Create /tmp/eval_feature_003/validator.py with an email validator:

1. Function validate_email(email: str) -> bool
2. Must check: contains @, has text before @, has domain after @, domain has .
3. Return True for valid, False for invalid
4. Test with: "test@example.com" (valid), "invalid" (invalid), "@no.com" (invalid), "no@domain" (invalid)
5. Write test results to /tmp/eval_feature_003/results.txt""",
        description="Implement email validator",
        success_criteria="Validator correctly identifies valid/invalid emails",
        tags=["python", "validation"],
    ),
    Task(
        id="analysis_002",
        category=TaskCategory.ANALYSIS,
        prompt="""Read the CompyMac source code at /home/ubuntu/repos/compymac/src/compymac/llm.py.

Analyze and write to /tmp/eval_analysis_002/llm_analysis.md:
1. What is the main class name?
2. What HTTP client library does it use?
3. What retry logic does it implement?
4. What exceptions can it raise?

Be specific with line numbers where you found each answer.""",
        description="Analyze real codebase",
        success_criteria="Analysis is accurate with correct line references",
        tags=["code-analysis"],
    ),
]
