# repo-parser

This is a set of python scripts and tools for extracting metadata and structure
out of a monorepo, for the purposes of generating a service registry, unified documentation, or other types of data out of the contents. It also contains some
tooling designed around a new concept called "Implementation Decision Records" (idrs), designed to aid both implementation (especially where assisted by LLMs) and later code archaeology efforts.

It should be considered an experiment, rather than production software. It is inspired by my experiences in the software industry and being frustrated with current solutions being some combination of:

- Time consuming to configure and maintain
- Requiring the specification of redundant metadata (which is bound to get out of date)

Current assumptions:

- The files you want to process fit into memory
- You don't care about history (repo-parser gives a snapshot in time)

You can see a demo of a documentation site generated from this repo at:

https://repo-parser-demo.netlify.app/

> [!NOTE]
> repo-parser is partly created with LLMs (specifically, Claude Code and ChatGPT),
> with heavy human curation.

## Usage

### Creating IDRs (Implementation Decision Records)

repo-parser includes a CLI tool (`rp`) for creating Implementation Decision Records (IDRs). IDRs are lightweight documents that capture both the intent and implementation details of code changes, designed to be committed alongside your code.

They are intended to be useful for both humans and computational agents (LLMs).

**Why IDRs?** Traditional design docs are too heavyweight for implementation. ADRs are great for decisions but lack implementation detail. IDRs bridge the gap—detailed enough to guide implementation, ephemeral enough to not become stale documentation.

Create a new IDR:

```bash
rp idr new "Your Feature Title"
```

This will create a new markdown file in the `idrs/` directory with:

- A UTC timestamp prefix (e.g., `202512301600`)
- A slugified version of your title
- Pre-filled template with your git author name

Example:

```bash
rp idr new "Add last modified metadata"
# Creates: idrs/202512301600-add-last-modified-metadata.md
```

The IDR template includes sections for:

- Problem Statement
- Context
- Goals and Non-Goals
- Proposed Solution
- Detailed Design
- Implementation notes (ephemeral)

This feature was itself implemented using an IDR—see [idrs/202512301631-idrs.md](idrs/202512301631-idrs.md) for more about the IDR format and philosophy.

### Using repo-parser as a Library

For documentation generation and metadata extraction, see the example in `example/example_parser.py`.

An early version of repo-parser is available on pypi as https://pypi.org/project/repo-parser. Use at your own risk!

## Local development

You can experiment with the local demo by running `make example`.
It should live-reload as you make changes in the `example/repo` directory.

For other tasks, look at the (very simple) `Makefile` in the root directory.
