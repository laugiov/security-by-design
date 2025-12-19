# Contributing to SkyLink

Thank you for your interest in contributing to this Security by Design reference implementation.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry (for dependency management)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/laurentmusic/security-by-design.git
cd security-by-design

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env

# Generate RSA keys for JWT
openssl genrsa -out /tmp/private.pem 2048
openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem

# Add keys to .env (follow instructions in .env.example)

# Run tests
poetry run pytest
```

## Development Workflow

### Branch Naming

- `feat/<description>` — New features
- `fix/<description>` — Bug fixes
- `docs/<description>` — Documentation updates
- `security/<description>` — Security improvements

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add rate limiting to weather endpoint
fix: correct JWT expiration validation
docs: update API documentation
security: add input sanitization for telemetry data
```

### Code Quality

Before submitting a pull request:

```bash
# Format code
poetry run black .
poetry run isort .

# Lint
poetry run ruff check .

# Security scan
poetry run bandit -r skylink

# Run tests with coverage
poetry run pytest --cov=skylink --cov-report=term-missing
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Ensure all tests pass and coverage is maintained
5. Update documentation if needed
6. Submit a pull request

### Pull Request Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No secrets or sensitive data committed
- [ ] Code formatted with Black
- [ ] Linting passes (Ruff, Bandit)
- [ ] Coverage maintained (minimum 75%)

## Security Guidelines

This is a **Security by Design** reference project. When contributing:

1. **Never commit secrets** — Use environment variables
2. **Validate all inputs** — Use Pydantic with `extra="forbid"`
3. **No PII in logs** — Only log trace_id for correlation
4. **Secure defaults** — Fail closed, not open
5. **Short token TTL** — JWT expiration should be minimal

### Reporting Security Issues

If you discover a security vulnerability, please **do not** open a public issue. Instead, contact the maintainer directly.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn

## Questions?

Open an issue for questions about contributing or the codebase.

---

Thank you for helping make this project better!
