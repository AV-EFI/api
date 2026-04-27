# AGENTS.md

## Project Overview

**AV-EFI API** - A Python-based REST API backend service for audiovisual entity-feature-integration, providing PID (Persistent Identifier) management, search functionality, authentication, and record matching capabilities.

**Tech Stack:**
- Language: Python 3.11+
- Framework: FastAPI with Uvicorn
- Search: Elasticsearch 8.15+
- Package Manager: `uv`
- Testing: Pytest

## Project Structure

```
app/                    # Main application source code
├── core/              # Configuration and infrastructure
│   ├── config.py      # Application settings (Pydantic BaseSettings)
│   └── elasticsearch.py # ES client setup
├── routers/           # API endpoints (FastAPI routers)
│   ├── auth.py        # OAuth2/Academiccloud authentication
│   ├── health.py      # Health check endpoints
│   ├── matches.py     # Work variant matching
│   ├── frontend/      # Frontend-specific routes
│   │   ├── search.py  # Multi-faceted search
│   │   └── view.py    # Content viewing
│   └── pid/           # PID management (disabled)
├── helpers/           # Business logic and utilities
│   ├── matching.py    # Work variant matching algorithms
│   ├── indexing.py    # Search index management
│   ├── auth.py        # Authentication helpers
│   └── epic_client.py # PID services client
├── schemas/           # Pydantic models
│   ├── efi_schema.py  # AVefi schema models
│   ├── elastic_schema.py # ES response models
│   └── frontend_search.py # Search request/response models
└── efi_agent/         # CLI tool for PID management
    ├── cli.py         # Click-based CLI
    └── push.py        # PID creation commands

tests/                 # Pytest tests (mirrors app/ structure)
config/                # Configuration templates (.ini.tmpl files)
docs/                  # Documentation
scripts/               # Utility scripts
```

## Key Development Commands

### Development
```bash
# Install dependencies
uv sync --no-python-downloads

# Run development server with hot reload
./run.sh

# Access API docs
# http://127.0.0.1:8000/rest/v1/docs
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test
uv run pytest tests/routers/test_auth.py
```

### Code Quality
```bash
# Lint and fix issues
uv run ruff check --fix

# Format code
uv run ruff format

# Run pre-commit hooks
pre-commit run --all-files
```

### Build & Package
```bash
# Bump version
uv version --bump

# Build Docker image (done via CI)
docker build -t avefi-api .
```

## Coding Standards

### General
- **Line Length:** 79 characters (strictly enforced)
- **Docstring Style:** NumPy convention
- **Type Hints:** Required for all functions
- **Error Handling:** Specific exception types with meaningful messages

### API Design
- Versioned API path: `/rest/v1/` (except auth routes)
- Async functions with type hints
- Pydantic models for request/response validation
- CORS support for frontend integration

### Long Lines
- Use `# noqa: E501` to disable length limit
- Use `# fmt: skip` to prevent reformatting of specific lines

### Configuration
- All sensitive data in environment variables
- Use template files (`.tmpl` suffix) for deployment
- Configuration files excluded from version control

## Important Tools & Integration

### External Services
- **Elasticsearch:** Primary data storage and search (indices: `21.11155`, `21.11155-nested`, `21.11155-denormalised-work`)
- **EPIC API:** PID management and handle system
- **Academiccloud:** OAuth2 identity provider
- **AVEFI Schema:** External schema package (Git dependency)

### Dependencies
- `fastapi` >= 0.110.0 - Web framework
- `uvicorn[standard]` >= 0.34.0 - ASGI server
- `elasticsearch` >= 8.15.1 - Search engine
- `pydantic-settings` >= 2.6.0 - Configuration
- `authlib` >= 1.5.0 - OAuth2 integration

### CI/CD Pipeline (GitLab)
- **test:** Gitleaks, Ruff lint/check, Pytest
- **build:** Docker image (non-main branches)
- **release:** Automated version management
- **deploy:** SSH deployment to staging/production

## Commit Message Guidelines

### Assisted Development Trailers

When AI/ML agents assist with code changes, commit messages MUST include an `Assisted-by` trailer following Linux kernel conventions:

```
describe the change in one line

More detailed explanatory text, if necessary. Wrap at 79 chars.

- Fixed issue X in component Y
- Added feature Z with proper error handling

Assisted-by: <agent_name>:<model_version>
```

**Examples:**
```
Add support for new OAuth2 provider in authentication module

Implemented new provider endpoint with token validation and
session management following existing patterns in auth.py.

Assisted-by: opencode:glm-4.7
```

```
Optimize Elasticsearch query performance for frontend search

Refactored multi-faceted search to use bool queries instead
of nested queries. Improved response time by ~40%.

Assisted-by: codex:GPT-4
```

**Format Rules:**
- The `Assisted-by` trailer goes at the **end** of the commit message
- Use format: `<agent_name>:<model_version>`
- Only one `Assisted-by` trailer per commit (use multiple agents separated by commas if needed)
- This aligns with Linux kernel coding-assistant conventions: https://docs.kernel.org/process/coding-assistants.html

### Conventional Commits

Follow this pattern for commit messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** `fix`, `feat`, `refactor`, `test`, `docs`, `chore`, `perf`, `style`, `ci`, `build`

**Examples:**
- `feat(auth): add OAuth2 token refresh support`
- `fix(search): handle empty query parameters gracefully`
- `test(matches): add coverage for edge cases`
- `docs(api): update Swagger documentation`

**When to use `Assisted-by` trailer:**
- Any commit where an AI/ML agent generated or significantly modified code
- Bug fixes suggested by AI tools
- Code refactoring performed by AI agents
- New features implemented with AI assistance

## Architecture Notes

### Separation of Concerns
- **Routers:** HTTP concerns only
- **Helpers:** Business logic
- **Schemas:** Data structures (Pydantic models)
- **Core:** Infrastructure (config, ES client)

### Async Patterns
- Use `async def` for all FastAPI route handlers
- Use `await` for async operations (ES calls, HTTP requests)
- Maintain async context managers where appropriate

### Testing Patterns
- Mirror source code structure in tests/
- Use `conftest.py` for shared fixtures
- Mock external dependencies (ES, APIs)
- Clear test names with descriptive docstrings

## Common Pitfalls

1. **Forgot async/await:** All database and HTTP operations must be async
2. **Long lines:** Line length is strictly 79 characters - wrap or use noqa comments
3. **Missing type hints:** Required for all function signatures
4. **Direct config access:** Settings from `app.core.config`, not environment variables directly
5. **Uncommited secrets:** Never commit `.api_config.env` or actual `config.ini` files
6. **Missing models:** Always define Pydantic models for request/response validation
7. **ESISync errors:** Ensure ES operations use proper async context

## Useful Resources

- **API Documentation:** http://127.0.0.1:8000/rest/v1/docs (Swagger UI)
- **AVEFI Schema:** https://github.com/AV-EFI/av-efi-schema
- **PID Documentation:** docs/pid-based-rights-management.md
- **Pre-commit Hooks:** .pre-commit-config.yaml
- **CI/CD Pipeline:** .gitlab-ci.yml
