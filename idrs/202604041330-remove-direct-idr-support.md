# 2026-04-04: Remove direct IDR support

Owner: Will Lachance <wlach@protonmail.com>

## Overview

### Problem Statement

IDR support has moved to the idr-tools package, having it here is redundant.

### Goals

- Remove confusing and redundant IDR support
- Continue to _use_ IDRs for this package where it makes sense

### Non-Goals

- Remove all traces of IDRs from the project (e.g. the `idrs` directory in this package is still useful)

### Proposed Solution

Update code to remove IDR support. Update docs to remove most mentions of
IDRs

## Cross cutting concerns (as needed)

### Migration

As far as I am aware, repo-parser's idr support was never used by anyone
other than myself so there is no need to make an announcement. The package itself is still in the "experimental" / "unstable" stage. We will just quietly retire support.
