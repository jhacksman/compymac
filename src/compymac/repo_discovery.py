"""
Repo Command Discovery - Phase 2

Automatically detect build, test, lint, and format commands from repository
configuration files. This enables the agent to understand how to work with
any repository without manual configuration.

Supported config files:
- package.json (Node.js/JavaScript)
- pyproject.toml (Python with Poetry/PDM/Hatch)
- setup.py / setup.cfg (Python with setuptools)
- Makefile (Make-based projects)
- Cargo.toml (Rust)
- go.mod (Go)
- .github/workflows/*.yml (GitHub Actions)
- Dockerfile (Docker)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class RepoCommand:
    """A discovered command with metadata."""

    name: str
    command: str
    category: str  # build, test, lint, format, run, deploy
    source: str  # Which config file it came from
    confidence: float = 1.0  # How confident we are this is correct
    description: str = ""


@dataclass
class RepoConfig:
    """Discovered configuration for a repository."""

    repo_path: Path
    language: str | None = None
    package_manager: str | None = None
    commands: list[RepoCommand] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    ci_config: dict[str, Any] = field(default_factory=dict)

    def get_commands_by_category(self, category: str) -> list[RepoCommand]:
        """Get all commands of a specific category."""
        return [c for c in self.commands if c.category == category]

    def get_test_command(self) -> RepoCommand | None:
        """Get the primary test command."""
        test_cmds = self.get_commands_by_category("test")
        return test_cmds[0] if test_cmds else None

    def get_lint_command(self) -> RepoCommand | None:
        """Get the primary lint command."""
        lint_cmds = self.get_commands_by_category("lint")
        return lint_cmds[0] if lint_cmds else None

    def get_build_command(self) -> RepoCommand | None:
        """Get the primary build command."""
        build_cmds = self.get_commands_by_category("build")
        return build_cmds[0] if build_cmds else None

    def get_format_command(self) -> RepoCommand | None:
        """Get the primary format command."""
        format_cmds = self.get_commands_by_category("format")
        return format_cmds[0] if format_cmds else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "repo_path": str(self.repo_path),
            "language": self.language,
            "package_manager": self.package_manager,
            "commands": [
                {
                    "name": c.name,
                    "command": c.command,
                    "category": c.category,
                    "source": c.source,
                    "confidence": c.confidence,
                    "description": c.description,
                }
                for c in self.commands
            ],
            "entry_points": self.entry_points,
            "dependencies": self.dependencies,
            "ci_config": self.ci_config,
        }


class RepoDiscovery:
    """Discovers repository configuration and commands."""

    def __init__(self, repo_path: Path | str):
        self.repo_path = Path(repo_path)
        self.config = RepoConfig(repo_path=self.repo_path)

    def discover(self) -> RepoConfig:
        """Run all discovery methods and return the config."""
        self._discover_package_json()
        self._discover_pyproject_toml()
        self._discover_makefile()
        self._discover_cargo_toml()
        self._discover_go_mod()
        self._discover_github_actions()
        self._infer_language()
        return self.config

    def _discover_package_json(self) -> None:
        """Parse package.json for Node.js projects."""
        pkg_path = self.repo_path / "package.json"
        if not pkg_path.exists():
            return

        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        self.config.language = "javascript"

        # Detect package manager
        if (self.repo_path / "pnpm-lock.yaml").exists():
            self.config.package_manager = "pnpm"
            run_prefix = "pnpm"
        elif (self.repo_path / "yarn.lock").exists():
            self.config.package_manager = "yarn"
            run_prefix = "yarn"
        else:
            self.config.package_manager = "npm"
            run_prefix = "npm run"

        # Parse scripts
        scripts = pkg.get("scripts", {})
        script_categories = {
            "test": [
                "test",
                "test:unit",
                "test:e2e",
                "test:integration",
                "jest",
                "vitest",
                "mocha",
            ],
            "lint": ["lint", "eslint", "lint:fix", "lint:check"],
            "format": ["format", "prettier", "fmt"],
            "build": ["build", "compile", "bundle", "webpack", "vite:build"],
            "run": ["start", "dev", "serve", "watch"],
            "deploy": ["deploy", "publish", "release"],
        }

        for script_name, script_cmd in scripts.items():
            category = "other"
            for cat, keywords in script_categories.items():
                if any(kw in script_name.lower() for kw in keywords):
                    category = cat
                    break

            self.config.commands.append(
                RepoCommand(
                    name=script_name,
                    command=f"{run_prefix} {script_name}",
                    category=category,
                    source="package.json",
                    description=f"npm script: {script_cmd[:50]}..."
                    if len(script_cmd) > 50
                    else f"npm script: {script_cmd}",
                )
            )

        # Parse dependencies
        self.config.dependencies["production"] = list(pkg.get("dependencies", {}).keys())
        self.config.dependencies["development"] = list(pkg.get("devDependencies", {}).keys())

        # Entry points
        if "main" in pkg:
            self.config.entry_points.append(pkg["main"])
        if "bin" in pkg:
            if isinstance(pkg["bin"], str):
                self.config.entry_points.append(pkg["bin"])
            elif isinstance(pkg["bin"], dict):
                self.config.entry_points.extend(pkg["bin"].values())

    def _discover_pyproject_toml(self) -> None:
        """Parse pyproject.toml for Python projects."""
        pyproject_path = self.repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            return

        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
        except Exception:
            return

        self.config.language = "python"

        # Detect build system / package manager
        build_system = pyproject.get("build-system", {})
        build_backend = build_system.get("build-backend", "")

        if (
            "poetry" in build_backend
            or "tool" in pyproject
            and "poetry" in pyproject.get("tool", {})
        ):
            self.config.package_manager = "poetry"
            self._add_poetry_commands(pyproject)
        elif "pdm" in build_backend or "tool" in pyproject and "pdm" in pyproject.get("tool", {}):
            self.config.package_manager = "pdm"
            self._add_pdm_commands(pyproject)
        elif "hatchling" in build_backend or "hatch" in build_backend:
            self.config.package_manager = "hatch"
            self._add_hatch_commands(pyproject)
        else:
            self.config.package_manager = "pip"
            self._add_pip_commands()

        # Check for common Python tools in [tool] section
        tool = pyproject.get("tool", {})

        if "pytest" in tool or "pytest-ini-options" in tool:
            self.config.commands.append(
                RepoCommand(
                    name="pytest",
                    command="pytest",
                    category="test",
                    source="pyproject.toml",
                    confidence=0.9,
                )
            )

        if "ruff" in tool:
            self.config.commands.append(
                RepoCommand(
                    name="ruff-check",
                    command="ruff check .",
                    category="lint",
                    source="pyproject.toml",
                )
            )
            self.config.commands.append(
                RepoCommand(
                    name="ruff-format",
                    command="ruff format .",
                    category="format",
                    source="pyproject.toml",
                )
            )

        if "black" in tool:
            self.config.commands.append(
                RepoCommand(
                    name="black",
                    command="black .",
                    category="format",
                    source="pyproject.toml",
                )
            )

        if "mypy" in tool:
            self.config.commands.append(
                RepoCommand(
                    name="mypy",
                    command="mypy .",
                    category="lint",
                    source="pyproject.toml",
                    description="Type checking",
                )
            )

        if "isort" in tool:
            self.config.commands.append(
                RepoCommand(
                    name="isort",
                    command="isort .",
                    category="format",
                    source="pyproject.toml",
                )
            )

        # Parse dependencies
        project = pyproject.get("project", {})
        self.config.dependencies["production"] = project.get("dependencies", [])
        self.config.dependencies["development"] = project.get("optional-dependencies", {}).get(
            "dev", []
        )

        # Entry points
        scripts = project.get("scripts", {})
        self.config.entry_points.extend(scripts.keys())

    def _add_poetry_commands(self, pyproject: dict) -> None:
        """Add Poetry-specific commands."""
        self.config.commands.append(
            RepoCommand(
                name="install",
                command="poetry install",
                category="build",
                source="pyproject.toml (poetry)",
            )
        )
        self.config.commands.append(
            RepoCommand(
                name="test",
                command="poetry run pytest",
                category="test",
                source="pyproject.toml (poetry)",
            )
        )

        # Check for poetry scripts
        poetry_scripts = pyproject.get("tool", {}).get("poetry", {}).get("scripts", {})
        for name, _cmd in poetry_scripts.items():
            category = "other"
            if "test" in name.lower():
                category = "test"
            elif "lint" in name.lower():
                category = "lint"
            elif "format" in name.lower() or "fmt" in name.lower():
                category = "format"

            self.config.commands.append(
                RepoCommand(
                    name=name,
                    command=f"poetry run {name}",
                    category=category,
                    source="pyproject.toml (poetry scripts)",
                )
            )

    def _add_pdm_commands(self, pyproject: dict) -> None:
        """Add PDM-specific commands."""
        self.config.commands.append(
            RepoCommand(
                name="install",
                command="pdm install",
                category="build",
                source="pyproject.toml (pdm)",
            )
        )
        self.config.commands.append(
            RepoCommand(
                name="test",
                command="pdm run pytest",
                category="test",
                source="pyproject.toml (pdm)",
            )
        )

        # Check for pdm scripts
        pdm_scripts = pyproject.get("tool", {}).get("pdm", {}).get("scripts", {})
        for name, _script in pdm_scripts.items():
            category = "other"
            if "test" in name.lower():
                category = "test"
            elif "lint" in name.lower():
                category = "lint"

            self.config.commands.append(
                RepoCommand(
                    name=name,
                    command=f"pdm run {name}",
                    category=category,
                    source="pyproject.toml (pdm scripts)",
                )
            )

    def _add_hatch_commands(self, pyproject: dict) -> None:
        """Add Hatch-specific commands."""
        self.config.commands.append(
            RepoCommand(
                name="install",
                command="hatch env create",
                category="build",
                source="pyproject.toml (hatch)",
            )
        )
        self.config.commands.append(
            RepoCommand(
                name="test",
                command="hatch run test",
                category="test",
                source="pyproject.toml (hatch)",
            )
        )

    def _add_pip_commands(self) -> None:
        """Add pip-based commands."""
        if (self.repo_path / "requirements.txt").exists():
            self.config.commands.append(
                RepoCommand(
                    name="install",
                    command="pip install -r requirements.txt",
                    category="build",
                    source="requirements.txt",
                )
            )
        if (self.repo_path / "requirements-dev.txt").exists():
            self.config.commands.append(
                RepoCommand(
                    name="install-dev",
                    command="pip install -r requirements-dev.txt",
                    category="build",
                    source="requirements-dev.txt",
                )
            )

        # Default pytest if tests directory exists
        if (self.repo_path / "tests").exists() or (self.repo_path / "test").exists():
            self.config.commands.append(
                RepoCommand(
                    name="test",
                    command="pytest",
                    category="test",
                    source="inferred (tests directory exists)",
                    confidence=0.7,
                )
            )

    def _discover_makefile(self) -> None:
        """Parse Makefile for make-based projects."""
        makefile_path = self.repo_path / "Makefile"
        if not makefile_path.exists():
            return

        try:
            with open(makefile_path) as f:
                content = f.read()
        except OSError:
            return

        # Find all targets (lines that match "target:" pattern)
        target_pattern = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", re.MULTILINE)
        targets = target_pattern.findall(content)

        target_categories = {
            "test": ["test", "tests", "check", "unittest"],
            "lint": ["lint", "check-style", "pylint", "flake8", "eslint"],
            "format": ["format", "fmt", "style", "prettier", "black"],
            "build": ["build", "compile", "all", "dist"],
            "run": ["run", "start", "serve", "dev"],
            "deploy": ["deploy", "release", "publish"],
            "clean": ["clean", "distclean"],
        }

        for target in targets:
            if target.startswith(".") or target in ["PHONY"]:
                continue

            category = "other"
            for cat, keywords in target_categories.items():
                if target.lower() in keywords or any(kw in target.lower() for kw in keywords):
                    category = cat
                    break

            self.config.commands.append(
                RepoCommand(
                    name=target,
                    command=f"make {target}",
                    category=category,
                    source="Makefile",
                )
            )

    def _discover_cargo_toml(self) -> None:
        """Parse Cargo.toml for Rust projects."""
        cargo_path = self.repo_path / "Cargo.toml"
        if not cargo_path.exists():
            return

        self.config.language = "rust"
        self.config.package_manager = "cargo"

        # Standard cargo commands
        self.config.commands.extend(
            [
                RepoCommand(
                    name="build", command="cargo build", category="build", source="Cargo.toml"
                ),
                RepoCommand(
                    name="test", command="cargo test", category="test", source="Cargo.toml"
                ),
                RepoCommand(
                    name="check", command="cargo check", category="lint", source="Cargo.toml"
                ),
                RepoCommand(
                    name="clippy", command="cargo clippy", category="lint", source="Cargo.toml"
                ),
                RepoCommand(
                    name="fmt", command="cargo fmt", category="format", source="Cargo.toml"
                ),
                RepoCommand(name="run", command="cargo run", category="run", source="Cargo.toml"),
            ]
        )

        try:
            with open(cargo_path, "rb") as f:
                cargo = tomllib.load(f)
            deps = cargo.get("dependencies", {})
            self.config.dependencies["production"] = list(deps.keys())
            dev_deps = cargo.get("dev-dependencies", {})
            self.config.dependencies["development"] = list(dev_deps.keys())
        except Exception:
            pass

    def _discover_go_mod(self) -> None:
        """Parse go.mod for Go projects."""
        go_mod_path = self.repo_path / "go.mod"
        if not go_mod_path.exists():
            return

        self.config.language = "go"
        self.config.package_manager = "go"

        # Standard go commands
        self.config.commands.extend(
            [
                RepoCommand(
                    name="build", command="go build ./...", category="build", source="go.mod"
                ),
                RepoCommand(name="test", command="go test ./...", category="test", source="go.mod"),
                RepoCommand(name="vet", command="go vet ./...", category="lint", source="go.mod"),
                RepoCommand(name="fmt", command="go fmt ./...", category="format", source="go.mod"),
                RepoCommand(name="run", command="go run .", category="run", source="go.mod"),
            ]
        )

        # Check for golangci-lint config
        if (self.repo_path / ".golangci.yml").exists() or (
            self.repo_path / ".golangci.yaml"
        ).exists():
            self.config.commands.append(
                RepoCommand(
                    name="golangci-lint",
                    command="golangci-lint run",
                    category="lint",
                    source=".golangci.yml",
                )
            )

    def _discover_github_actions(self) -> None:
        """Parse GitHub Actions workflows for CI commands."""
        workflows_dir = self.repo_path / ".github" / "workflows"
        if not workflows_dir.exists():
            return

        import yaml

        for workflow_file in workflows_dir.glob("*.yml"):
            try:
                with open(workflow_file) as f:
                    workflow = yaml.safe_load(f)
            except Exception:
                continue

            if not workflow:
                continue

            workflow_name = workflow.get("name", workflow_file.stem)
            self.config.ci_config[workflow_name] = {
                "file": str(workflow_file.relative_to(self.repo_path)),
                "triggers": list(workflow.get("on", {}).keys())
                if isinstance(workflow.get("on"), dict)
                else [workflow.get("on")],
            }

            # Extract run commands from jobs
            jobs = workflow.get("jobs", {})
            for job_name, job in jobs.items():
                steps = job.get("steps", [])
                for step in steps:
                    if "run" in step:
                        run_cmd = step["run"]
                        step_name = step.get("name", "unnamed")

                        # Try to categorize based on step name or command
                        category = "ci"
                        if any(
                            kw in step_name.lower() or kw in run_cmd.lower()
                            for kw in ["test", "pytest", "jest"]
                        ):
                            category = "test"
                        elif any(
                            kw in step_name.lower() or kw in run_cmd.lower()
                            for kw in ["lint", "ruff", "eslint", "mypy"]
                        ):
                            category = "lint"
                        elif any(
                            kw in step_name.lower() or kw in run_cmd.lower()
                            for kw in ["format", "fmt", "prettier"]
                        ):
                            category = "format"
                        elif any(
                            kw in step_name.lower() or kw in run_cmd.lower()
                            for kw in ["build", "compile"]
                        ):
                            category = "build"

                        # Only add if it's a simple command (not multi-line scripts)
                        if "\n" not in run_cmd and len(run_cmd) < 100:
                            self.config.commands.append(
                                RepoCommand(
                                    name=f"ci:{job_name}:{step_name}",
                                    command=run_cmd,
                                    category=category,
                                    source=f".github/workflows/{workflow_file.name}",
                                    confidence=0.8,
                                )
                            )

    def _infer_language(self) -> None:
        """Infer the primary language if not already set."""
        if self.config.language:
            return

        # Check for language-specific files
        if (self.repo_path / "package.json").exists():
            self.config.language = "javascript"
        elif (self.repo_path / "pyproject.toml").exists() or (self.repo_path / "setup.py").exists():
            self.config.language = "python"
        elif (self.repo_path / "Cargo.toml").exists():
            self.config.language = "rust"
        elif (self.repo_path / "go.mod").exists():
            self.config.language = "go"
        elif (self.repo_path / "pom.xml").exists() or (self.repo_path / "build.gradle").exists():
            self.config.language = "java"
        elif (self.repo_path / "Gemfile").exists():
            self.config.language = "ruby"


def discover_repo(repo_path: Path | str) -> RepoConfig:
    """Convenience function to discover repo configuration."""
    discovery = RepoDiscovery(repo_path)
    return discovery.discover()
