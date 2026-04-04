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

## Local development

You can experiment with the local demo by running `make example`.
It should live-reload as you make changes in the `example/repo` directory.

For other tasks, look at the (very simple) `Makefile` in the root directory.
