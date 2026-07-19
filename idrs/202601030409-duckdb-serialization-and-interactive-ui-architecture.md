# DuckDB serialization

Owner: Will Lachance <wlach@protonmail.com>

## Overview

### Problem Statement

repo-parser extracts metadata and structure from repositories into an in-memory `Resource` tree, but this ephemeral representation must be re-created for each consumer. We need a persistent, queryable serialization format that allows multiple tools to consume the extracted metadata without re-scanning the repository.

### Context

**Current workflow:**

1. `repo-parser` scans repo → `Resource` tree in memory
2. Consumer processes/transforms it (e.g., Sphinx generation)
3. Tree is discarded

**Limitations:**

- Expensive re-scanning for each consumer
- No way to query/filter without custom code
- Can't compose with external data sources
- No standard interface for downstream tools

**What repo-parser extracts (metadata, not code):**

- Repository structure (services, libraries, docs)
- READMEs and documentation content
- Frontmatter and configuration metadata
- Temporal metadata (last_modified)
- Organizational hierarchy

**Not in scope:** Code analysis (functions, imports, symbols) - that's LSP territory.

### Goals

- Serialize the `Resource` tree to DuckDB as a persistent artifact
- Enable data composition (join repo-parser output with CODEOWNERS, deployment data, etc.)
- Allow consumers to use the data without depending on repo-parser's Python API
- Support multiple use cases: search, reporting, enrichment, custom tooling

### Non-Goals

- Code analysis or symbol indexing
- Designing or promising a stable long-term SQL schema in this phase
- Building a general-purpose repo-parser CLI
- Replacing existing Sphinx workflow (it becomes one consumer among many)
- Building complete downstream tools in this phase (search TUI, web UI, etc.)
- Incremental updates (future enhancement)

### Proposed Solution

Add `to_duckdb()` as a DuckDB loading primitive that writes the raw `Resource`
tree into a caller-owned DuckDB connection. The resulting relation becomes:

- **A queryable base relation** that consumers can inspect without re-scanning
- **A composition layer** where external data can be joined in
- **Language agnostic** (any tool with DuckDB bindings can consume it)

Persistence is caller policy. Callers can use an in-memory connection for
immediate augmentation, a file-backed connection for a bronze artifact, or both.

## Detailed Design

### DuckDB Schema

The raw scanned `Resource` tree will be flattened into a single `resources` table.
This first pass should preserve the extracted resource model as directly as possible
and avoid coupling the output to Sphinx-specific post-processing such as README path
rewrites.

```sql
CREATE TABLE resources (
    path VARCHAR PRIMARY KEY, -- source path relative to scanned root, "." for root
    parent_path VARCHAR,      -- NULL for root, enables tree reconstruction
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,    -- 'repo', 'language', 'service', 'library', 'file'
    content TEXT,             -- file content (NULL for non-file resources)
    properties JSON,          -- metadata/properties extracted by processors
    last_modified TIMESTAMP NOT NULL,
    FOREIGN KEY (parent_path) REFERENCES resources(path)
);
```

The schema is intentionally small and provisional. It is useful enough for local
experiments and downstream scripts, but this IDR does not establish it as a
stable contract.

### API Design

**Library usage:**

```python
import duckdb

from repo_parser import scan, get_resources
from repo_parser.outputs import to_duckdb

dir, repo = scan("/path/to/repo", processors)
root_resource = get_resources(repo, dir, processors)

con = duckdb.connect()
to_duckdb(con, root_resource)

con.execute("""
CREATE VIEW docs_resources AS
SELECT *
FROM resources
""")
```

There is no general-purpose CLI in scope for this decision. Callers are expected
to use repo-parser as a Python library and provide their own processors.

### Extraction Pattern (Current)

Users provide processor functions that extract metadata from files:

```python
# Current pattern (example_parser.py)
import frontmatter
import re

from repo_parser import Processor, get_resources, scan
from repo_parser.filesystem import File

def process_markdown(file: File):
    metadata, _ = frontmatter.parse(file.content or "")
    filetype = metadata.get("type", "file")
    metadata.pop("type", None)
    return filetype, metadata, file

processors = [
    Processor(re.compile(r"\.md$"), process_markdown, True),
]

dir, repo = scan("/path/to/repo", processors)
root = get_resources(repo, dir, processors)
```

This pattern is flexible and allows users to extract whatever metadata they need. DuckDB serialization works with any processors users provide.

- Can be revisited later (YAML, plugins, etc.) if needed

### Consumer Pattern

Downstream tools can inspect the generated DuckDB file directly:

```python
import duckdb

con = duckdb.connect('repo.duckdb')

# Standard SQL queries
services = con.execute("""
    SELECT name, last_modified
    FROM resources
    WHERE type = 'service'
    ORDER BY last_modified DESC
""").fetchall()
```

### Data Composition Pattern

External data can be joined with repo-parser's output:

```python
# Add code ownership data
con.execute("""
    CREATE TABLE code_ownership AS
    SELECT service_name, owner, team
    FROM read_csv('codeowners.csv')
""")

# Join with repo-parser data
result = con.execute("""
    SELECT
        r.name,
        r.last_modified,
        co.owner,
        co.team
    FROM resources r
    LEFT JOIN code_ownership co ON r.name = co.service_name
    WHERE r.type = 'service'
""").fetchall()
```

**Example enrichment pipeline:**

```bash
# Base extraction
python scripts/extract_repo_metadata.py ./repo repo.duckdb

# Enrich with external data (custom scripts)
python scripts/add_codeowners.py repo.duckdb
python scripts/add_deploy_history.py repo.duckdb
python scripts/add_opslevel_data.py repo.duckdb

# Query enriched dataset
python scripts/ownership_report.py repo.duckdb
```

### Implementation approach

1. **Create `repo_parser/outputs.py` module**

   - Implement `to_duckdb(con: duckdb.DuckDBPyConnection, resource: Resource, *, table_name: str = "resources", replace: bool = True)`
   - Traverse resource tree depth-first
   - Insert into resources table with parent relationships
   - Use each resource's source-root-relative path as `resources.path`
   - Serialize resource metadata into a `properties` JSON column

2. **Dependencies and testing**
   - Add `duckdb` as a core dependency
   - Add tests for serialization round-trip
   - Verify tree structure preserved
   - Verify metadata preserved
   - Test with example repo

## Rollout plan

This is a backward-compatible addition:

1. **Phase 1**: Add DuckDB serialization

   - Add `outputs.py` module with `to_duckdb()`
   - Update dependencies to include `duckdb`
   - Document the provisional schema in README.md
   - Optionally update example parser to demonstrate usage

2. **Phase 2**: Documentation and examples

   - Document the DuckDB schema as provisional
   - Provide example queries
   - Show data composition examples
   - Document how to write processors for custom metadata extraction

3. **Phase 3** (future): Enable downstream consumers
   - Build reference implementations (search TUI, etc.) as separate packages
   - Document common query patterns
   - Show integration examples (data platform, BI tools, etc.)

## Use Cases Enabled

### Basic usage

```bash
# Use with existing example parser
cd example/
python example_parser.py repo/ docs/ ../output/

# Now also generate DuckDB
# (after implementing to_duckdb in example_parser.py)
```

### Querying extracted metadata

```bash
# Query what was found
duckdb output.duckdb "SELECT name, type FROM resources WHERE type='service'"
duckdb output.duckdb "SELECT path FROM resources WHERE name='README.md'"
```

### Custom extraction (current pattern)

```python
# Users write processor functions as needed
import frontmatter
import re

from repo_parser import Processor
from repo_parser.filesystem import File

def process_markdown(file: File):
    metadata, _ = frontmatter.parse(file.content or "")
    filetype = metadata.get("type", "file")
    metadata.pop("type", None)
    return filetype, metadata, file

processors = [Processor(re.compile(r"\.md$"), process_markdown, True)]

# Then use with to_duckdb
dir, repo = scan("./repo", processors)
root = get_resources(repo, dir, processors)

con = duckdb.connect()
to_duckdb(con, root)
```

### Custom reporting

```sql
-- Services with no README
SELECT name FROM resources
WHERE type = 'service'
  AND path NOT IN (
    SELECT parent_path FROM resources
    WHERE name = 'README.md'
  );
```

### Data composition

```sql
-- Services with no owner in CODEOWNERS
SELECT r.name
FROM resources r
LEFT JOIN code_ownership co ON r.name = co.service_name
WHERE r.type = 'service' AND co.owner IS NULL;

-- Undeployed changes (code modified after last deploy)
SELECT r.name, r.last_modified, d.last_deploy
FROM resources r
JOIN deployments d ON r.name = d.service_name
WHERE r.last_modified > d.last_deploy;
```

## Alternatives considered

### Keep DuckDB serialization downstream

Initially considered building this as a separate `repo-parser-duckdb` package to keep the core minimal. However, serialization is fundamental to making the extracted metadata reusable. The DuckDB file IS the artifact - having it as a core output format makes sense.

### Use SQLite instead of DuckDB

SQLite would work but DuckDB offers:

- Better analytics performance (columnar storage)
- Native support for Parquet export
- Modern SQL features (better JSON handling, full-text search extensions)
- Better handling of large text fields (content)
- Growing ecosystem and momentum

### Keep everything in-memory only

Current approach works but requires downstream consumers to:

- Import repo-parser as a Python library
- Re-scan the repository every time
- Implement their own caching/persistence

With DuckDB, consumers can be in any language and don't need repo-parser installed.

### Use JSON/Parquet instead

**JSON**: Simple but no querying without loading everything into memory. DuckDB can export to JSON if needed.

**Parquet**: Great for data pipelines but less convenient for ad-hoc queries. DuckDB can export to Parquet if needed.

DuckDB provides both querying AND export capabilities.

## Future plans

### Full-text search

Add DuckDB full-text search extension for document search:

```sql
CREATE INDEX fts_idx ON resources USING FTS(content);

SELECT path, snippet(content, 'clickhouse', 50)
FROM resources
WHERE content MATCH 'clickhouse'
ORDER BY last_modified DESC;
```

### Built-in extractors (future)

As a convenience, repo-parser could provide reusable extractor implementations:

```python
from repo_parser.extractors import FrontmatterExtractor, PyProjectTomlExtractor

# Instead of writing your own every time
processors = [
    FrontmatterExtractor(),
    PyProjectTomlExtractor(),
]
```

This would:

- Make repo-parser more useful out-of-the-box
- Provide good examples for custom extractors
- Reduce boilerplate for common cases

Could be added after DuckDB serialization is proven useful.

### Config format evolution (future)

The Python config file pattern (like Sphinx) is flexible. Future alternatives could include:

**YAML config (simpler cases):**

```yaml
extractors:
  - frontmatter
  - pyproject-toml
```

**Plugin system (third-party extractors):**

```toml
[project.entry-points."repo_parser.extractors"]
gecko-extractors = "mozilla_repo_parser:gecko_extractors"
```

Start with processor functions, evolve based on user feedback.

### Incremental updates

For long-running applications, support updating only changed files:

- Compare git SHAs to detect changes
- Update only affected resources in DuckDB
- Maintain consistency of parent relationships

### Downstream applications (separate packages)

- **Search TUI**: Fast terminal-based search with Sphinx preview
- **Web dashboard**: Browse/search with metrics and visualizations
- **CI integrations**: Quality checks (missing READMEs, stale docs, etc.)
- **Sync tools**: Keep OpsLevel/Backstage/other catalogs in sync with repo reality

## Other reading

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Textual - TUI framework](https://textual.textualize.io/)

## Implementation (ephemeral)

### Tasks

**Phase 1: DuckDB serialization**

- [x] Create `repo_parser/outputs.py` module
- [x] Implement `to_duckdb()` function
  - [x] Tree traversal
  - [x] Resources table population
  - [x] Store processor metadata in a `properties` JSON column
  - [x] Use source-root-relative resource path as `resources.path`
- [x] Add `duckdb` dependency to `pyproject.toml`
- [x] Write tests
  - [x] Round-trip serialization (Resource -> DuckDB -> verify current schema)
  - [x] Verify tree structure preserved
  - [x] Verify properties JSON preserved
  - [x] Test with example repo

**Phase 2: Documentation**

- [x] Document provisional DuckDB schema in README
- [x] Add example queries
- [x] Show data composition examples

### Implementation notes

**Key principles:**

- DuckDB schema is provisional in this phase
- Consumers can query DuckDB directly, but the schema is not yet a compatibility contract
- `to_duckdb()` writes to a caller-owned DuckDB connection; it does not decide
  whether the data is in-memory or persisted
- Enable data composition (joining with external sources)
- Users provide processor functions for metadata extraction (current pattern)
- This is library-only; a general-purpose repo-parser CLI is out of scope

**Tree traversal approach**:

```python
def _flatten_resources(
    resource: Resource,
    root_path: Path,
    parent_path: str | None = None,
) -> list[tuple]:
    """Flatten resource tree into rows for insertion"""
    rows = []
    resource_path = _resource_path(resource, root_path)

    # Add this resource
    rows.append((
        resource_path,
        parent_path,
        resource.name,
        resource.type,
        resource.content,
        json.dumps(resource.metadata),
        resource.last_modified
    ))

    # Recursively add children
    for child in resource.children:
        rows.extend(_flatten_resources(child, root_path, parent_path=resource_path))

    return rows
```

**Properties handling**:

- Store the resource metadata dict as a JSON blob in `resources.properties`
- Preserve simple and complex values using JSON rather than stringifying them into a separate key-value table
- Document that consumers should JSON decode/query the field when needed

**Path handling**:

- Use the resource source path relative to the scanned root as `resources.path`
- Use `"."` for the root resource
- Use the same path values for `parent_path`
- Do not store separate `id` or `src_path` columns in this phase

**Schema documentation**:

- Document all table structures
- Provide common query examples
- Explain tree reconstruction (`parent_path` relationships)
- Show data composition patterns

**Error handling**:

- Existing table exists: drop and recreate by default; callers can pass
  `replace=False` to surface DuckDB's table-exists error
- Invalid table names: reject before interpolating into SQL
- Large content fields: store as-is (DuckDB handles large text well)

### Completed work

**2026-07-01**: DuckDB serialization implemented

- Updated `repo_parser/outputs.py` to match the narrowed design:
  - Single `resources` table only
  - `to_duckdb(con, resource, *, table_name="resources", replace=True)` writes
    into a caller-owned DuckDB connection
  - `path` is the primary key and source-root-relative resource identity
  - `parent_path` stores tree relationships
  - Processor metadata is stored in `properties JSON`
  - In-memory vs file-backed persistence is controlled by the caller
- Updated `tests/test_outputs.py`:
  - Path identity and parent-path relationships
  - JSON properties preservation
  - Table replacement, custom table names, and invalid table name rejection
  - Serialization from a real scan of `example/repo`
- Updated README DuckDB documentation to describe the provisional single-table
  schema and current `get_resources(repo, dir, processors)` call order.
- Verification passed:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run ty check`
  - `uv run pytest`

**2026-07-01**: Example pipeline moved metadata augmentation into DuckDB

- Updated `example/example_parser.py` so the generated `repo.duckdb` contains:
  - `resources_raw`: direct output from `to_duckdb()`
  - `resources_derived`: SQL-derived table with inherited language metadata
- Removed Python-side mutation for metadata augmentation in the example.
- Kept `README.md` to `index.md` translation in the file-writing layer because
  it is a Sphinx output convention, not repository metadata enrichment.
- Updated the example docs writer to query `resources_derived` and render files
  from those rows.
- The Netlify-published `repo.duckdb` now contains both the raw and derived
  datasets.
