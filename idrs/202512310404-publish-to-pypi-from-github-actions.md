# Publish to pypi from GitHub Actions

Owner: Will Lachance <wlach@protonmail.com>

## Overview

### Problem Statement

repo-parser packages can only be published to pypi manually, which is time consuming, error prone and less secure than doing so via GitHub actions.

### Context (as needed)

### Goals

- Make it easier to publish new releases
- Improve security

### Proposed Solution

Use the idiomatic best practice way of doing this, using the official packaging guide:

https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/

In general this means adding a new GitHub workflow which ties uploads to PyPI to new releases.

## Other reading (as needed)

- [Official Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [Stamina's implementation](https://github.com/hynek/stamina/blob/b25d4bc359ff603496aafbb217ab82c5a43715a6/.github/workflows/pypi-package.yml) (likely best practice)

## Implementation (ephemeral)

### Pre-requisites

1. **Configure PyPI Trusted Publishers** (must be done manually by repo owner)

   - Go to https://pypi.org/manage/account/publishing/
   - Add a new pending publisher:
     - PyPI Project Name: `repo-parser` (from `pyproject.toml`)
     - Owner: `wlach`
     - Repository name: `repo-parser`
     - Workflow name: `publish-to-pypi.yml`
     - Environment name: `release-pypi`
   - Go to https://test.pypi.org/manage/account/publishing/
   - Add a new pending publisher with same details but:
     - Environment name: `release-test-pypi`

2. **Configure GitHub Environments** (manual step)
   - Go to repository Settings → Environments
   - Create environment `release-pypi`:
     - Add required reviewers (at least yourself) for manual approval
     - This ensures accidental tags don't immediately publish to PyPI
   - Create environment `release-test-pypi`:
     - No approval required (publishes on every main branch push for testing)

### Implementation Checklist

- [x] Create `.github/workflows/publish-to-pypi.yml` workflow file
- [x] Configure PyPI Trusted Publishers (manual - see pre-requisites above)
- [x] Configure GitHub Environments (manual - see pre-requisites above)
- [ ] Merge this branch to main to test TestPyPI publishing
- [ ] Verify TestPyPI upload works
- [ ] Create a test GitHub release to verify PyPI publishing workflow (without actual approval)

### Workflow File Details

Create `.github/workflows/publish-to-pypi.yml` with:

**Key features:**

- Uses `uv build` instead of `python -m build` (project uses uv)
- Builds on every push to main and on tags
- Publishes to TestPyPI on main branch pushes (no approval needed)
- Publishes to PyPI on GitHub releases (requires manual approval via `release-pypi` environment)
- Uses trusted publishing (OIDC tokens, no API keys needed)
- Includes PEP 740 attestations automatically (v1.11.0+)

**Structure:**

1. **build job**: Checks out code, installs uv, builds dist packages, uploads as artifacts
2. **release-test-pypi job**: Downloads artifacts, publishes to TestPyPI (only on main branch)
3. **release-pypi job**: Downloads artifacts, publishes to PyPI (only on GitHub releases)

**Trigger strategy:**

- `on.push.branches: [main]` → builds and publishes to TestPyPI for smoke testing
- `on.release.types: [published]` → builds and publishes to PyPI when creating a GitHub release
- This is safer than tag-based publishing since releases are explicit actions

### Release Process (for humans)

Once implemented, to publish a new version:

1. Ensure version is updated in `repo_parser/__init__.py` (flit uses `__version__`)
2. Commit and push to main
3. Verify TestPyPI upload succeeded: https://test.pypi.org/project/repo-parser/
4. Create a GitHub Release with a new tag (e.g., `v0.2.0`)
5. Approve the deployment in the Actions tab
6. Verify PyPI upload: https://pypi.org/project/repo-parser/
