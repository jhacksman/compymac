"""
locale2b Client - HTTP client for locale2b sandbox service.

locale2b provides isolated Firecracker microVM sandboxes for CLI command execution.
All CLI commands execute through locale2b - there is no local fallback.

See: https://github.com/jhacksman/locale2b
"""

import base64
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 60.0
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 10.0


@dataclass
class Locale2bConfig:
    """Configuration for locale2b sandbox service."""
    base_url: str
    api_key: str
    api_key_header: str = "X-API-Key"
    default_memory_mb: int = 512
    default_vcpu_count: int = 1
    default_template: str = "default"

    @classmethod
    def from_env(cls) -> "Locale2bConfig":
        """Load configuration from environment variables."""
        base_url = os.getenv("LOCALE2B_BASE_URL")
        api_key = os.getenv("LOCALE2B_API_KEY")

        if not base_url:
            raise Locale2bConfigError(
                "LOCALE2B_BASE_URL is not set. Set it to your locale2b server URL.\n"
                "  Example: LOCALE2B_BASE_URL=http://localhost:8080"
            )

        if not api_key:
            raise Locale2bConfigError(
                "LOCALE2B_API_KEY is not set. Set it to your locale2b API key.\n"
                "  Example: LOCALE2B_API_KEY=your-api-key-here"
            )

        return cls(
            base_url=base_url,
            api_key=api_key,
            api_key_header=os.getenv("LOCALE2B_API_KEY_HEADER", "X-API-Key"),
            default_memory_mb=int(os.getenv("LOCALE2B_DEFAULT_MEMORY_MB", "512")),
            default_vcpu_count=int(os.getenv("LOCALE2B_DEFAULT_VCPU_COUNT", "1")),
            default_template=os.getenv("LOCALE2B_DEFAULT_TEMPLATE", "default"),
        )


@dataclass
class SandboxInfo:
    """Information about a locale2b sandbox."""
    sandbox_id: str
    status: str
    memory_mb: int
    vcpu_count: int
    workspace_id: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "SandboxInfo":
        """Parse sandbox info from API response."""
        return cls(
            sandbox_id=data["sandbox_id"],
            status=data.get("status", "unknown"),
            memory_mb=data.get("memory_mb", 512),
            vcpu_count=data.get("vcpu_count", 1),
            workspace_id=data.get("workspace_id"),
        )


@dataclass
class ExecResult:
    """Result of command execution in sandbox."""
    stdout: str
    stderr: str
    exit_code: int
    error: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "ExecResult":
        """Parse exec result from API response."""
        return cls(
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code", 0),
            error=data.get("error"),
        )


@dataclass
class FileInfo:
    """Information about a file in sandbox."""
    path: str
    content: bytes | None = None
    is_directory: bool = False
    size: int = 0

    @classmethod
    def from_api_response(cls, data: dict[str, Any], decode_content: bool = True) -> "FileInfo":
        """Parse file info from API response."""
        content = None
        if decode_content and "content" in data:
            content = base64.b64decode(data["content"])

        return cls(
            path=data.get("path", ""),
            content=content,
            is_directory=data.get("is_directory", False),
            size=data.get("size", 0),
        )


class Locale2bClient:
    """
    Client for locale2b sandbox service.

    Provides methods for:
    - Creating and destroying sandboxes
    - Executing commands in sandboxes
    - Reading and writing files in sandboxes
    - Pausing and resuming sandboxes
    """

    def __init__(self, config: Locale2bConfig | None = None) -> None:
        """Initialize the client with configuration.

        Args:
            config: locale2b configuration. If None, loads from environment.

        Raises:
            Locale2bConfigError: If required configuration is missing.
        """
        self.config = config or Locale2bConfig.from_env()

        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=DEFAULT_READ_TIMEOUT,
            write=DEFAULT_WRITE_TIMEOUT,
            pool=DEFAULT_POOL_TIMEOUT,
        )

        headers = {
            "Content-Type": "application/json",
            self.config.api_key_header: self.config.api_key,
        }

        self._client = httpx.Client(
            base_url=self.config.base_url,
            headers=headers,
            timeout=timeout,
        )

    def health_check(self) -> dict[str, Any]:
        """Check if locale2b service is healthy.

        Returns:
            Health status dict with status, active_sandboxes, memory_available_mb.

        Raises:
            Locale2bConnectionError: If cannot connect to service.
        """
        try:
            response = self._client.get("/health")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise Locale2bConnectionError(
                f"Cannot connect to locale2b at {self.config.base_url}\n"
                f"Check that the service is running and LOCALE2B_BASE_URL is correct."
            ) from e
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Health check failed: {e.response.status_code}") from e

    def create_sandbox(
        self,
        workspace_id: str | None = None,
        memory_mb: int | None = None,
        vcpu_count: int | None = None,
        template: str | None = None,
    ) -> SandboxInfo:
        """Create a new sandbox.

        Args:
            workspace_id: Optional workspace ID for persistence/resume.
            memory_mb: Memory allocation in MB (default from config).
            vcpu_count: Number of vCPUs (default from config).
            template: Sandbox template (default from config).

        Returns:
            SandboxInfo with sandbox_id and status.

        Raises:
            Locale2bError: If sandbox creation fails.
        """
        payload = {
            "memory_mb": memory_mb or self.config.default_memory_mb,
            "vcpu_count": vcpu_count or self.config.default_vcpu_count,
            "template": template or self.config.default_template,
        }
        if workspace_id:
            payload["workspace_id"] = workspace_id

        try:
            response = self._client.post("/sandboxes", json=payload)
            response.raise_for_status()
            return SandboxInfo.from_api_response(response.json())
        except httpx.ConnectError as e:
            raise Locale2bConnectionError(
                f"Cannot connect to locale2b at {self.config.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to create sandbox: {e.response.text}") from e

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy a sandbox.

        Args:
            sandbox_id: ID of sandbox to destroy.

        Returns:
            True if destroyed successfully.

        Raises:
            Locale2bError: If destruction fails.
        """
        try:
            response = self._client.delete(f"/sandboxes/{sandbox_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Sandbox {sandbox_id} not found (already destroyed?)")
                return True
            raise Locale2bError(f"Failed to destroy sandbox: {e.response.text}") from e

    def list_sandboxes(self) -> list[SandboxInfo]:
        """List all active sandboxes.

        Returns:
            List of SandboxInfo for active sandboxes.
        """
        try:
            response = self._client.get("/sandboxes")
            response.raise_for_status()
            data = response.json()
            return [SandboxInfo.from_api_response(s) for s in data.get("sandboxes", [])]
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to list sandboxes: {e.response.text}") from e

    def exec_command(
        self,
        sandbox_id: str,
        command: str,
        working_dir: str = "/workspace",
        timeout_ms: int = 30000,
    ) -> ExecResult:
        """Execute a command in a sandbox.

        Args:
            sandbox_id: ID of sandbox to execute in.
            command: Shell command to execute.
            working_dir: Working directory for command.
            timeout_ms: Command timeout in milliseconds.

        Returns:
            ExecResult with stdout, stderr, exit_code.

        Raises:
            Locale2bError: If execution fails.
        """
        payload = {
            "command": command,
            "working_dir": working_dir,
            "timeout_ms": timeout_ms,
        }

        try:
            response = self._client.post(f"/sandboxes/{sandbox_id}/exec", json=payload)
            response.raise_for_status()
            return ExecResult.from_api_response(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Locale2bError(f"Sandbox {sandbox_id} not found") from e
            raise Locale2bError(f"Command execution failed: {e.response.text}") from e

    def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: bytes | str,
    ) -> bool:
        """Write a file in a sandbox.

        Args:
            sandbox_id: ID of sandbox.
            path: File path in sandbox.
            content: File content (bytes or str).

        Returns:
            True if written successfully.

        Raises:
            Locale2bError: If write fails.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        payload = {
            "path": path,
            "content": base64.b64encode(content).decode("ascii"),
        }

        try:
            response = self._client.post(f"/sandboxes/{sandbox_id}/files/write", json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to write file: {e.response.text}") from e

    def read_file(self, sandbox_id: str, path: str) -> FileInfo:
        """Read a file from a sandbox.

        Args:
            sandbox_id: ID of sandbox.
            path: File path in sandbox.

        Returns:
            FileInfo with content.

        Raises:
            Locale2bError: If read fails.
        """
        try:
            response = self._client.get(
                f"/sandboxes/{sandbox_id}/files/read",
                params={"path": path},
            )
            response.raise_for_status()
            return FileInfo.from_api_response(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Locale2bError(f"File not found: {path}") from e
            raise Locale2bError(f"Failed to read file: {e.response.text}") from e

    def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[FileInfo]:
        """List files in a sandbox directory.

        Args:
            sandbox_id: ID of sandbox.
            path: Directory path in sandbox.

        Returns:
            List of FileInfo for files in directory.

        Raises:
            Locale2bError: If listing fails.
        """
        try:
            response = self._client.get(
                f"/sandboxes/{sandbox_id}/files/list",
                params={"path": path},
            )
            response.raise_for_status()
            data = response.json()
            return [FileInfo.from_api_response(f, decode_content=False) for f in data.get("files", [])]
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to list files: {e.response.text}") from e

    def pause_sandbox(self, sandbox_id: str) -> bool:
        """Pause a sandbox (snapshot state).

        Args:
            sandbox_id: ID of sandbox to pause.

        Returns:
            True if paused successfully.

        Raises:
            Locale2bError: If pause fails.
        """
        try:
            response = self._client.post(f"/sandboxes/{sandbox_id}/pause")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to pause sandbox: {e.response.text}") from e

    def resume_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """Resume a paused sandbox.

        Args:
            sandbox_id: ID of sandbox to resume.

        Returns:
            SandboxInfo with updated status.

        Raises:
            Locale2bError: If resume fails.
        """
        try:
            response = self._client.post(f"/sandboxes/{sandbox_id}/resume")
            response.raise_for_status()
            return SandboxInfo.from_api_response(response.json())
        except httpx.HTTPStatusError as e:
            raise Locale2bError(f"Failed to resume sandbox: {e.response.text}") from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "Locale2bClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class Locale2bError(Exception):
    """Error from locale2b client."""
    pass


class Locale2bConfigError(Locale2bError):
    """Error from missing or invalid locale2b configuration."""
    pass


class Locale2bConnectionError(Locale2bError):
    """Error connecting to locale2b service."""
    pass
