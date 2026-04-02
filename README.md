# repo-parser

This is a set of python scripts and tools for extracting metadata and structure
out of a monorepo, for the purposes of generating a service registry, unified documentation, or other types of data out of the contents.

It should be considered an experiment, rather than production software. It is inspired by my experiences in the software industry and being frustrated with current solutions being some combination of:

- Time consuming to configure and maintain
- Requiring the specification of redundant metadata (which is bound to get out of date)

Current assumptions:

- The files you want to process fit into memory
- You don't care about history (repo-parser gives a snapshot in time)

You can see a demo of a documentation site generated from this repo at:

https://repo-parser-demo.netlify.app/

> [!NOTE]
> repo-parser is partly created with LLMs (specifically, Claude Code and ChatGPT), with heavy human curation.

## Usage

For documentation generation and metadata extraction, see the example in `example/example_parser.py`.

An early version of repo-parser is available on pypi as https://pypi.org/project/repo-parser. Use at your own risk!

### DuckDB Serialization

repo-parser can serialize the extracted metadata to a DuckDB database file, enabling:

- **Queryable artifacts**: Use SQL to query repository metadata without re-scanning
- **Data composition**: Join with external data sources (deployments, incidents, ownership)
- **Language-agnostic consumption**: Any tool with DuckDB bindings can use the data
- **Portable artifacts**: Share, cache, or version the database file

#### Basic Usage

```python
import duckdb

from repo_parser import scan, get_resources
from repo_parser.outputs import to_duckdb

# Scan repository and extract metadata
dir, repo = scan("/path/to/repo", processors)
root_resource = get_resources(repo, dir, processors)

# Write resources into an in-memory DuckDB connection for augmentation/querying
con = duckdb.connect()
to_duckdb(con, root_resource)

# Or use a file-backed connection if you want to persist the table
con = duckdb.connect("repo.duckdb")
to_duckdb(con, root_resource)
con.close()
```

#### Schema

`to_duckdb()` creates one provisional table:

**`resources` table** - Flattened resource tree:

| Column          | Type      | Description                                                              |
| --------------- | --------- | ------------------------------------------------------------------------ |
| `path`          | VARCHAR   | Primary key: source path relative to scanned root, `.` for root resource |
| `parent_path`   | VARCHAR   | Foreign key to parent resource path, NULL for root                       |
| `name`          | VARCHAR   | Resource name (e.g., "auth-service", "README.md")                       |
| `type`          | VARCHAR   | Resource type: 'repo', 'language', 'service', 'library', 'file'          |
| `content`       | TEXT      | File content (NULL for non-file resources)                               |
| `properties`    | JSON      | Metadata/properties extracted by processors                              |
| `last_modified` | TIMESTAMP | Last modification time from git                                          |

The example documentation build writes `repo.duckdb` with `resources_raw` and a
SQL-derived `resources_derived` table used by the docs renderer.

#### Example Queries

**Find all services:**

```sql
SELECT name, last_modified
FROM resources
WHERE type = 'service'
ORDER BY last_modified DESC;
```

**Services missing READMEs:**

```sql
SELECT name
FROM resources
WHERE type = 'service'
  AND path NOT IN (
    SELECT parent_path
    FROM resources
    WHERE name = 'README.md'
  );
```

**Get metadata for a specific service:**

```sql
SELECT properties
FROM resources
WHERE name = 'auth-service' AND type = 'service';
```

**Reconstruct tree hierarchy:**

```sql
WITH RECURSIVE tree AS (
  -- Start with root
  SELECT path, parent_path, name, 0 as level
  FROM resources
  WHERE parent_path IS NULL

  UNION ALL

  -- Recursively get children
  SELECT r.path, r.parent_path, r.name, t.level + 1
  FROM resources r
  JOIN tree t ON r.parent_path = t.path
)
SELECT repeat('  ', level) || name as tree_view
FROM tree
ORDER BY path;
```

#### Data Composition

Join repo-parser data with external sources:

```python
import duckdb

con = duckdb.connect('repo.duckdb')

# Load external ownership data
con.execute("""
    CREATE TABLE code_ownership AS
    SELECT service_name, owner, team
    FROM read_csv('codeowners.csv')
""")

# Find services without owners
result = con.execute("""
    SELECT r.name, r.last_modified
    FROM resources r
    LEFT JOIN code_ownership co ON r.name = co.service_name
    WHERE r.type = 'service' AND co.owner IS NULL
    ORDER BY r.last_modified DESC
""").fetchall()
```

**Common composition patterns:**

- **Deployment tracking**: Join with deployment history to find undeployed changes
- **Incident correlation**: Link services to incidents to identify reliability issues
- **Ownership mapping**: Combine with CODEOWNERS or team databases
- **Metrics enrichment**: Add performance metrics, error rates, etc.

#### Querying from Command Line

```bash
# Direct SQL queries
duckdb repo.duckdb "SELECT name FROM resources WHERE type='service'"

# Export to CSV
duckdb repo.duckdb "COPY (SELECT * FROM resources) TO 'resources.csv' (HEADER)"

# Export to JSON
duckdb repo.duckdb "COPY (SELECT * FROM resources) TO 'resources.json'"

# Export to Parquet (for data pipelines)
duckdb repo.duckdb "COPY (SELECT * FROM resources) TO 'resources.parquet'"
```

## Local development

You can experiment with the local demo by running `make example`.
It should live-reload as you make changes in the `example/repo` directory.

For other tasks, look at the (very simple) `Makefile` in the root directory.
