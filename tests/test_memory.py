"""Tests for the memory management system."""


from compymac.config import ContextConfig
from compymac.memory import MemoryFacts, MemoryManager, MemoryState
from compymac.types import Message


class TestMemoryFacts:
    """Tests for MemoryFacts extraction and formatting."""

    def test_empty_facts(self):
        facts = MemoryFacts()
        assert facts.to_string() == "No facts recorded yet."

    def test_facts_to_string(self):
        facts = MemoryFacts(
            files_created=["/tmp/test.py"],
            commands_executed=["ls -la"],
            errors_encountered=["File not found"],
        )
        result = facts.to_string()
        assert "Files created: /tmp/test.py" in result
        assert "Commands run: ls -la" in result
        assert "Errors: File not found" in result

    def test_facts_truncation(self):
        facts = MemoryFacts(
            files_read=[f"/tmp/file{i}.txt" for i in range(20)],
        )
        result = facts.to_dict()
        assert len(result["files_read"]) <= 10


class TestMemoryState:
    """Tests for MemoryState."""

    def test_empty_memory_message(self):
        state = MemoryState()
        msg = state.to_memory_message()
        assert "[MEMORY SUMMARY" in msg

    def test_memory_message_with_content(self):
        state = MemoryState(
            summary="Completed file operations",
            facts=MemoryFacts(files_created=["/tmp/test.py"]),
            compression_count=1,
            total_messages_compressed=5,
        )
        msg = state.to_memory_message()
        assert "Completed file operations" in msg
        assert "Files created: /tmp/test.py" in msg
        assert "Compressed 5 earlier messages" in msg


class TestMemoryManager:
    """Tests for MemoryManager."""

    def test_initialization(self):
        config = ContextConfig(token_budget=10000)
        manager = MemoryManager(config=config)
        assert manager.keep_recent_turns == 4
        assert manager.compression_threshold == 0.80

    def test_estimate_tokens(self):
        config = ContextConfig(chars_per_token=4.0)
        manager = MemoryManager(config=config)
        assert manager.estimate_tokens("hello world") == 2  # 11 chars / 4

    def test_should_compress_under_threshold(self):
        config = ContextConfig(token_budget=100000)
        manager = MemoryManager(config=config, compression_threshold=0.80)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        assert not manager.should_compress(messages)

    def test_extract_facts_from_file_message(self):
        manager = MemoryManager()
        message = Message(
            role="assistant",
            content="I created the file `/tmp/test.py` with the code.",
        )
        manager.extract_facts_from_message(message)
        assert "/tmp/test.py" in manager.state.facts.files_created

    def test_extract_facts_from_shell_output(self):
        manager = MemoryManager()
        message = Message(
            role="tool",
            content='<shell-output command="ls -la" return_code="0">output</shell-output>',
        )
        manager.extract_facts_from_message(message)
        assert "ls -la" in manager.state.facts.commands_executed

    def test_extract_facts_from_error(self):
        manager = MemoryManager()
        message = Message(
            role="tool",
            content="Error: File not found at /tmp/missing.txt",
        )
        manager.extract_facts_from_message(message)
        assert len(manager.state.facts.errors_encountered) > 0

    def test_generate_summary_heuristic(self):
        manager = MemoryManager()
        messages = [
            Message(role="user", content="Create a file"),
            Message(role="assistant", content="I'll create the file"),
            Message(role="tool", content="File created"),
            Message(role="assistant", content="Done! The task is completed successfully."),
        ]
        summary = manager.generate_summary_heuristic(messages)
        assert len(summary) > 0

    def test_compress_messages_not_enough(self):
        manager = MemoryManager(keep_recent_turns=4)
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        result = manager.compress_messages(messages)
        assert len(result) == len(messages)

    def test_compress_messages_creates_memory(self):
        manager = MemoryManager(keep_recent_turns=2)
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="First task"),
            Message(role="assistant", content="Done first"),
            Message(role="user", content="Second task"),
            Message(role="assistant", content="Done second"),
            Message(role="user", content="Third task"),
            Message(role="assistant", content="Done third"),
            Message(role="user", content="Fourth task"),
            Message(role="assistant", content="Done fourth"),
        ]
        result = manager.compress_messages(messages)

        # Should have: system + memory + recent turns
        assert len(result) < len(messages)

        # Check memory message exists
        memory_msgs = [m for m in result if m.content.startswith("[MEMORY SUMMARY")]
        assert len(memory_msgs) == 1

    def test_process_messages_no_compression_needed(self):
        config = ContextConfig(token_budget=1000000)  # Very large budget
        manager = MemoryManager(config=config)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        result = manager.process_messages(messages)
        assert len(result) == len(messages)

    def test_reset(self):
        manager = MemoryManager()
        manager.state.summary = "Some summary"
        manager.state.compression_count = 5
        manager.reset()
        assert manager.state.summary == ""
        assert manager.state.compression_count == 0


class TestMemoryManagerIntegration:
    """Integration tests for memory manager with realistic scenarios."""

    def test_multi_turn_conversation(self):
        config = ContextConfig(token_budget=50000)
        manager = MemoryManager(config=config, keep_recent_turns=2)

        messages = [Message(role="system", content="You are a coding assistant")]

        # Simulate a multi-turn conversation
        for i in range(10):
            messages.append(Message(role="user", content=f"Task {i}: Do something"))
            messages.append(Message(role="assistant", content=f"Completed task {i}"))

        # Process should extract facts and potentially compress
        result = manager.process_messages(messages, force_compress=True)

        # Should be compressed
        assert len(result) < len(messages)

        # Memory state should have info
        state = manager.get_memory_state()
        assert state.compression_count > 0

    def test_file_operations_tracking(self):
        manager = MemoryManager()

        messages = [
            Message(role="user", content="Create a Python file"),
            Message(role="assistant", content="I'll create `/tmp/app.py`"),
            Message(role="tool", content="Successfully wrote 100 characters to /tmp/app.py"),
            Message(role="assistant", content="Created the file. Now modifying `/tmp/config.json`"),
            Message(role="tool", content="Modified /tmp/config.json"),
        ]

        for msg in messages:
            manager.extract_facts_from_message(msg)

        facts = manager.state.facts
        assert "/tmp/app.py" in facts.files_created or "/tmp/app.py" in facts.files_modified
