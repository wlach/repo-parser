# repo-parser

This is a set of python scripts and tools for extracting metadata and structure
out of a monorepo, for the purposes of generating a service registry, unified documentation, or other types of data out of the contents.

It should be considered an experiment, rather than production software. It is inspired by my experiences in the software industry and being frustrated with current solutions being some combination of:

- Expensive
- Time consuming to configure and maintain
- Requiring the specification of redundant metadata (which is bound to get out of date)

Assumptions:

- The files you want to process fit into memory
- You don't care about history

You can see a demo of a documentation site generated from this repo at:

https://monorepo-parser-demo.netlify.app/
