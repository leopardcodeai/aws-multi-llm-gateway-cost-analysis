# Contributing to LLM Gateway

Thank you for your interest in contributing! This project follows a standard GitHub flow.

## Development Setup

```bash
# Clone and setup
git clone https://github.com/leopardcodeai/llm-gateway.git
cd llm-gateway

# Install dependencies
make install

# Start local dependencies
make dev
```

## Code Style

- **Formatter**: Ruff (Black-compatible)
- **Linter**: Ruff
- **Type Checker**: MyPy (strict mode)
- **Pre-commit**: Enforced on commit

```bash
# Format code
make format

# Lint
make lint

# Type check
make typecheck
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Run quality checks: `make lint typecheck test`
5. Commit with conventional commits: `git commit -m "feat: add amazing feature"`
6. Push: `git push origin feat/your-feature`
7. Open a Pull Request

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(router): add cascade fallback for medium tier`
- `fix(cache): handle qdrant connection timeout`
- `docs(readme): update architecture diagram`

## Architecture Decisions

Major changes should be discussed in an issue first. For significant architectural changes, create an ADR (Architecture Decision Record) in `docs/adr/`.

## Security

- Never commit secrets or API keys
- All credentials via environment variables or AWS Secrets Manager
- Run `make security-scan` before PR

## Questions?

Open an issue or start a discussion!