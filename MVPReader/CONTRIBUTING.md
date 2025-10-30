# Contributing to MVPReader

Thank you for your interest in contributing to MVPReader! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/compymac.git`
3. Navigate to MVPReader: `cd compymac/MVPReader`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a branch: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git

### Configuration
1. Copy example config: `cp config/config.example.json config/config.json`
2. Add your API credentials to `config/config.json`
3. Or set environment variables (see README.md)

### Running Tests
```bash
python -m pytest tests/
```

### Running Examples
```bash
python examples/basic_usage.py
python examples/custom_filtering.py
```

## Code Style

### Python Style Guide
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes

### Docstring Format
```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of function
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this exception is raised
    """
    pass
```

### Naming Conventions
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

## Project Structure

```
MVPReader/
├── config/           # Configuration management
├── core/             # Core business logic
├── fetchers/         # Platform-specific fetchers
├── tests/            # Unit and integration tests
├── examples/         # Usage examples
└── cli.py            # Command-line interface
```

## Adding New Features

### Adding a New Platform Fetcher

1. Create new file in `fetchers/` directory:
```python
# fetchers/newplatform_fetcher.py
from .base import BaseFetcher
from ..core.models import FeedEvent, Source, EventType

class NewPlatformFetcher(BaseFetcher):
    def __init__(self, credentials: dict):
        super().__init__(credentials)
        # Initialize API client
    
    def test_connection(self) -> bool:
        # Test API connection
        pass
    
    def fetch_events(self, since=None) -> List[FeedEvent]:
        # Fetch and convert events
        pass
```

2. Add to `fetchers/__init__.py`:
```python
from .newplatform_fetcher import NewPlatformFetcher
__all__ = [..., 'NewPlatformFetcher']
```

3. Update `core/aggregator.py` to initialize new fetcher

4. Add credentials to `config/settings.py`

5. Update documentation

### Adding New Filtering Logic

1. Extend `InterestFilter` class in `core/interest_filter.py`
2. Add new configuration options to `config/settings.py`
3. Update example config file
4. Add tests for new filtering logic

### Improving AI Analysis

1. Modify prompt in `core/ai_analyzer.py`
2. Test with various event types
3. Update documentation with prompt changes
4. Consider token usage implications

## Testing Guidelines

### Writing Tests

1. Create test file in `tests/` directory
2. Use unittest framework
3. Mock external API calls
4. Test edge cases and error conditions

Example:
```python
import unittest
from MVPReader.core.models import FeedEvent

class TestNewFeature(unittest.TestCase):
    def setUp(self):
        # Setup test fixtures
        pass
    
    def test_feature_works(self):
        # Test normal operation
        pass
    
    def test_feature_handles_errors(self):
        # Test error handling
        pass
```

### Test Coverage
- Aim for >80% code coverage
- All public APIs should have tests
- Test both success and failure cases

## Documentation

### Code Documentation
- Add docstrings to all public functions/classes
- Include type hints
- Explain complex logic with comments

### User Documentation
- Update README.md for user-facing changes
- Add examples for new features
- Update ARCHITECTURE.md for structural changes

## Pull Request Process

1. **Before submitting:**
   - Run tests: `python -m pytest tests/`
   - Check code style
   - Update documentation
   - Add examples if applicable

2. **PR Description should include:**
   - What changes were made
   - Why the changes were needed
   - How to test the changes
   - Any breaking changes
   - Screenshots (if UI changes)

3. **PR Title format:**
   - `feat: Add new platform fetcher for Discord`
   - `fix: Handle rate limiting in Slack fetcher`
   - `docs: Update installation instructions`
   - `test: Add tests for interest filtering`

4. **Review process:**
   - Maintainers will review your PR
   - Address any feedback
   - Once approved, PR will be merged

## Areas for Contribution

### High Priority
- Additional platform integrations (Discord, Email, GitHub)
- Improved error handling and retry logic
- Better prompt engineering for AI analysis
- Performance optimizations

### Medium Priority
- Web dashboard UI
- Real-time streaming support
- Vector database integration
- Multi-user support

### Low Priority
- Additional output formats (JSON, HTML)
- Notification system
- Scheduled updates
- Analytics dashboard

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing issues before creating new ones

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).
