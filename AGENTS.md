# repo-parser Agent Guide

repo-parser extracts metadata and structure from monorepos for generating service registries, unified documentation, and other data products. It also provides tooling for Implementation Decision Records (IDRs) to aid LLM-assisted development and code archaeology.

Core architecture:

- **Resources**: Extracted entities from the repo (services, libraries, etc.)
- **Processors**: Pattern-based file matchers that extract metadata
- **Templates**: Jinja2 templates in `repo_parser/templates/` for IDRs and output generation

## Howtos (in brief)

- Run any python commands via `uv run python ...`
- Run linting via `uv run ruff check .` from root
- Auto-fix linting issues via `uv run ruff check --fix .` from root
- Run type-checking via `uv run ty check` from root
- Run format checking via `uv run ruff format --check .` from root
- Auto-format code via `uv run ruff format .` from root
- Run tests via `uv run pytest` from root. In general just run all the tests. They are extremely fast.
- Test changes locally via `make example` (live-reloads as you edit `example/repo/`)
- Add dependencies via `uv add <package>` (or `uv add --dev <package>` for dev dependencies)

## Programming Guidelines

- Use idiomatic best-practices Python in 2025. repo-parser requires at least Python 3.11, so safe to use features available only in that version (or later)
- Never throw or catch generic exceptions. Always handle expected errors via specific
  exceptions.
- Always write tests. Keep them concise and readable, over-testing can be almost as harmful as under-testing.

## IDRs

- Larger changes should use an Implementation Decision Record (IDR). You can
  generate one by running `uv run rp idr new "Description of change"`.
- IDRs are stored in the `idrs/` directory with timestamp prefixes.
- See `idrs/202512301631-idrs.md` for the IDR philosophy and format details.
- IDRs are useful for both humans and LLMs: in addition to helping understand _why_ a change was made, they capture implementation details that are too ephemeral for permanent docs but valuable during development.
