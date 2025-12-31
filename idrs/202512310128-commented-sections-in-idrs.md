# Commented Sections in IDRs

Owner: Will Lachance <wlach@protonmail.com>

## Overview

### Problem Statement

The IDR template lacks inline guidance, making it unclear what content belongs in each section or how much detail is expected. This creates friction for new users and reduces IDR effectiveness.

### Context (as needed)

The original IDR template (introduced in [202512301631-idrs.md](202512301631-idrs.md)) provided section headings but no guidance on what to put in each section or how much detail was expected.

### Goals

- Provide inline guidance for each section of the IDR template
- Help users understand the expected scope and length of each section
- Make it easy to remove the guidance once the IDR is filled out

### Non-Goals

- Making the comments prescriptive or mandatory to follow
- Adding so many comments that they become overwhelming

### Proposed Solution

Add HTML comments to the IDR template that provide guidance for each section. The comments explain what should go in each section and provide rough length guidelines where appropriate (e.g., "3-5 lines" for problem statement, "ideally under 200 words" for proposed solution).

Include a note at the top of the template that these comments are explanatory and can be deleted, giving users permission to remove the scaffolding once they understand the structure.

To avoid the "form filling" feeling, provide a `--no-comments` flag for `rp idr new` and support an `RP_IDR_NO_COMMENTS` environment variable. This gives users who prefer clean templates an easy way to opt out of the guidance comments.

## Detailed Design (as needed)

Not applicable - the implementation is straightforward template modification.

## Rollout plan (as needed)

No rollout needed. Existing IDRs are unaffected. New IDRs created with `rp idr new` will use the enhanced template.

## Cross cutting concerns (as needed)

Not applicable.

## Alternatives considered (as needed)

**Separate documentation**: Could have written a separate guide to using IDRs instead of inline comments. Rejected because:

- Inline comments are more discoverable
- Users don't need to context-switch between documents
- Comments can be easily removed once no longer needed

**More prescriptive comments**: Could have been more detailed about what goes in each section. Kept it lightweight to avoid being overwhelming and to preserve flexibility.

## Future plans (as needed)

Not applicable.

## Other reading (as needed)

- [202512301631-idrs.md](202512301631-idrs.md) - Original IDR implementation

## Implementation (ephemeral)

### Changes Made

1. **Modified `repo_parser/templates/idr.md`** to add:

   - Top-level comment explaining that commented sections are explanatory and can be deleted
   - Section-specific guidance comments for each section (see git diff for details)
   - All comments use HTML comment syntax (`<!-- -->`) so they don't render in markdown viewers

2. **Modified `repo_parser/cli.py`** to add:

   - `--no-comments` flag to `rp idr new` command
   - Support for `RP_IDR_NO_COMMENTS` environment variable
   - Logic to strip HTML comments from template when either flag is set or env var is truthy

3. **Updated top-level comment in template** to include instructions on how to disable comments (via flag or environment variable), rather than showing a tip message every time the command runs.

### Implementation checklist

- [x] Update IDR template with guidance comments
- [x] Add `--no-comments` flag to CLI
- [x] Add environment variable support
- [x] Strip comments from template when requested
- [x] Add tests for comment stripping logic
- [x] Update documentation if needed
