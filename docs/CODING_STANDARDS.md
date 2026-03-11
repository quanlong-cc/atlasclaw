# AtlasClaw-Core Coding Standards

## Table of Contents

1. [General Principles](#general-principles)
2. [Python Code Style](#python-code-style)
3. [Type Hints](#type-hints)
4. [Documentation](#documentation)
5. [Error Handling](#error-handling)
6. [Testing Standards](#testing-standards)
7. [Import Organization](#import-organization)
8. [Naming Conventions](#naming-conventions)
9. [Async/Await Patterns](#asyncawait-patterns)
10. [Security Guidelines](#security-guidelines)

---

## General Principles

### 1. Readability First

Code is read more often than it is written. Prioritize clarity over cleverness.

```python
# Good
async def get_user_by_id(user_id: str) -> User | None:
    """Retrieve a user by their unique identifier."""
    return await user_repository.find_by_id(user_id)

# Bad
async def g(u: str) -> Any:
    return await ur.f(u)
```

### 2. Explicit Over Implicit

Be explicit about behavior, types, and intentions.

```python
# Good
def process_data(data: dict[str, Any]) -> ProcessedResult:
    if not data:
        raise ValueError("Data cannot be empty")
    return ProcessedResult.from_dict(data)

# Bad
def process_data(data):
    return ProcessedResult(data)
```

### 3. Single Responsibility

Each function, class, and module should have one clear purpose.

---

## Python Code Style

### PEP 8 Compliance

Follow [PEP 8](https://peps.python.org/pep-0008/) style guide with these additions:

#### Line Length

- Maximum line length: **100 characters**
- Use parentheses for implicit line continuation

```python
# Good
result = await some_long_function_name(
    first_parameter,
    second_parameter,
    third_parameter,
)

# Bad
result = await some_long_function_name(first_parameter, second_parameter, third_parameter)
```

#### Whitespace

```python
# Good
def my_function(x: int, y: int) -> int:
    return x + y

# Bad
def my_function(x:int,y:int)->int:
    return x+y
```

### String Quotes

- Use double quotes for strings: `"string"`
- Use single quotes for string literals containing double quotes: `'He said "Hello"'`

---

## Type Hints

### Mandatory Type Hints

All function parameters and return types must be annotated.

```python
# Good
async def fetch_user(user_id: str) -> User | None:
    ...

# Bad
async def fetch_user(user_id):
    ...
```

### Generic Types

Use generic types from `typing` module:

```python
from typing import Any, TypeVar

T = TypeVar("T")

def get_first(items: list[T]) -> T | None:
    return items[0] if items else None

def process_data(data: dict[str, Any]) -> None:
    ...
```

### Optional Types

Use `| None` syntax (Python 3.10+) instead of `Optional`:

```python
# Good
def find_user(user_id: str) -> User | None:
    ...

# Acceptable for older compatibility
def find_user(user_id: str) -> Optional[User]:
    ...
```

### Forward References

Use string literals for forward references:

```python
class Node:
    def __init__(self) -> None:
        self.children: list["Node"] = []
```

---

## Documentation

### Docstring Format

Use Google-style docstrings:

```python
def process_user_data(
    user_id: str,
    data: dict[str, Any],
    validate: bool = True,
) -> ProcessedData:
    """Process user data and return structured result.

    This function takes raw user data, validates it if requested,
    and returns a structured ProcessedData object.

    Args:
        user_id: Unique identifier for the user.
        data: Raw user data dictionary.
        validate: Whether to validate the data before processing.
            Defaults to True.

    Returns:
        ProcessedData object containing structured user information.

    Raises:
        ValueError: If data validation fails.
        UserNotFoundError: If user_id does not exist.

    Example:
        >>> result = process_user_data("123", {"name": "John"})
        >>> print(result.name)
        'John'
    """
    ...
```

### Module Docstrings

Every module should have a docstring:

```python
"""Session management module.

This module provides session lifecycle management including creation,
persistence, retrieval, and cleanup of user sessions.

Key components:
    SessionManager: Main class for session operations
    SessionContext: Context manager for session state
"""
```

### Inline Comments

Use inline comments sparingly, only when the code is not self-explanatory:

```python
# Good: Explains WHY, not WHAT
# Compensate for edge case where timezone offset affects date calculation
adjusted_date = raw_date + timedelta(hours=timezone_offset)

# Bad: Restates the obvious
# Add one to count
count += 1
```

---

## Error Handling

### Exception Hierarchy

Define custom exceptions for your module:

```python
class AtlasClawError(Exception):
    """Base exception for all AtlasClaw errors."""
    pass

class SessionError(AtlasClawError):
    """Exception raised for session-related errors."""
    pass

class SessionNotFoundError(SessionError):
    """Exception raised when a session cannot be found."""
    pass
```

### Try/Except Patterns

Be specific about exceptions:

```python
# Good
try:
    user = await fetch_user(user_id)
except UserNotFoundError:
    logger.warning("User not found: %s", user_id)
    return None
except NetworkError as e:
    logger.error("Network error fetching user: %s", e)
    raise

# Bad
try:
    user = await fetch_user(user_id)
except Exception:
    return None
```

### Context Managers

Use context managers for resource management:

```python
# Good
async with httpx.AsyncClient() as client:
    response = await client.get(url)
    return response.json()

# Bad
client = httpx.AsyncClient()
response = await client.get(url)
return response.json()  # Client never closed!
```

---

## Testing Standards

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch

class TestUserService:
    """Test suite for UserService."""

    @pytest.fixture
    def user_service(self):
        """Create a UserService instance for testing."""
        return UserService()

    async def test_get_user_returns_user_when_exists(self, user_service):
        """Test that get_user returns the user when it exists."""
        # Arrange
        user_id = "test-user-123"
        expected_user = User(id=user_id, name="Test User")

        # Act
        result = await user_service.get_user(user_id)

        # Assert
        assert result == expected_user

    async def test_get_user_returns_none_when_not_exists(self, user_service):
        """Test that get_user returns None when user doesn't exist."""
        result = await user_service.get_user("non-existent")
        assert result is None
```

### Test Naming

- Test class names: `Test<ComponentName>`
- Test method names: `test_<action>_<condition>_<expected_result>`

### Mocking

Use `unittest.mock` for mocking:

```python
from unittest.mock import AsyncMock, patch

async def test_fetch_data_with_mock():
    with patch("app.module.client.get") as mock_get:
        mock_get.return_value = AsyncMock(json=lambda: {"data": "test"})
        result = await fetch_data()
        assert result == {"data": "test"}
```

### Test Markers

Use appropriate pytest markers:

```python
@pytest.mark.asyncio
async def test_async_function():
    ...

@pytest.mark.slow  # For tests > 1 second
def test_slow_operation():
    ...

@pytest.mark.integration  # For integration tests
def test_integration():
    ...
```

---

## Import Organization

### Import Order

1. Standard library imports
2. Third-party library imports
3. Local application imports

```python
# Standard library
import asyncio
from pathlib import Path
from typing import Any

# Third-party
import httpx
from pydantic import BaseModel

# Local application
from app.atlasclaw.core.config import get_config
from app.atlasclaw.session.manager import SessionManager
```

### Import Style

```python
# Good
from app.atlasclaw.core.config import get_config

# Bad (avoid wildcard imports)
from app.atlasclaw.core.config import *
```

### TYPE_CHECKING

Use `TYPE_CHECKING` for imports only needed for type hints:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.atlasclaw.agent.runner import AgentRunner
```

---

## Naming Conventions

### Variables

```python
# Good
user_count = 10
is_active = True
user_list = []

# Bad
uc = 10
b = True
lst = []
```

### Functions

Use verb-noun format:

```python
# Good
def fetch_user_data():
    ...

def validate_input():
    ...

# Bad
def user_data():
    ...

def validation():
    ...
```

### Classes

Use PascalCase for class names:

```python
# Good
class SessionManager:
    ...

class UserRepository:
    ...

# Bad
class session_manager:
    ...
```

### Constants

Use UPPER_SNAKE_CASE:

```python
# Good
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

# Bad
max_retry = 3
defaultTimeout = 30
```

---

## Async/Await Patterns

### Async Functions

Mark I/O-bound functions as async:

```python
# Good
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Bad (blocking I/O in async function)
async def fetch_data(url: str) -> dict[str, Any]:
    response = requests.get(url)  # Blocking!
    return response.json()
```

### Running Async Code

Use `asyncio.run()` for entry points:

```python
def main():
    asyncio.run(run_application())
```

### Concurrent Execution

Use `asyncio.gather()` for concurrent operations:

```python
async def fetch_multiple(urls: list[str]) -> list[dict[str, Any]]:
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks)
```

---

## Security Guidelines

### Never Hardcode Secrets

```python
# Good
api_key = os.environ.get("API_KEY")
if not api_key:
    raise ValueError("API_KEY environment variable not set")

# Bad
api_key = "sk-1234567890abcdef"  # Never do this!
```

### Input Validation

Always validate external input:

```python
# Good
def process_user_input(data: dict[str, Any]) -> None:
    if not isinstance(data.get("user_id"), str):
        raise ValueError("user_id must be a string")
    if len(data["user_id"]) > 100:
        raise ValueError("user_id too long")
    ...

# Bad
def process_user_input(data: dict) -> None:
    user_id = data["user_id"]  # No validation!
```

### SQL Injection Prevention

Use parameterized queries:

```python
# Good
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# Bad
cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
```

---

## Code Review Checklist

Before submitting code for review, ensure:

- [ ] All functions have type hints
- [ ] All functions have docstrings
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is appropriate and specific
- [ ] Tests are included for new functionality
- [ ] Code follows naming conventions
- [ ] No print statements (use logging instead)
- [ ] Imports are properly organized
- [ ] No commented-out code
- [ ] Documentation is updated if needed

---

## Tools and Automation

### Recommended Tools

- **Ruff**: Fast Python linter and formatter
- **mypy**: Static type checker
- **pytest**: Testing framework
- **pre-commit**: Git hooks for code quality

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
```

---

## Summary

Following these standards ensures:

1. **Consistency**: Code looks and feels the same across the codebase
2. **Readability**: Code is easy to understand and maintain
3. **Reliability**: Type hints and tests catch errors early
4. **Security**: Sensitive data is properly protected
5. **Collaboration**: Team members can work effectively together

When in doubt, prioritize clarity and simplicity over cleverness.
