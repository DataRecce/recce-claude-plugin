---
name: python-uv-ci
description: >
  GitHub Actions workflow steps for Python projects using uv.
  Use this skill when generating CI workflows that need uv-based
  dependency installation with virtual environment.
---

# Python CI with uv

## GitHub Actions Steps

### Setup and Install

```yaml
- uses: actions/checkout@v4

- name: Install uv
  uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    python-version: "{PYTHON_VERSION}"

- name: Create venv and install dependencies
  run: |
    uv venv
    uv pip install {DEPENDENCIES}
```

### Running Commands

After setup, use `uv run` to execute commands in the venv:

```yaml
- name: Run command
  run: uv run {COMMAND}
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `{PYTHON_VERSION}` | Python version | `3.12` |
| `{DEPENDENCIES}` | Space-separated packages | - |
| `{COMMAND}` | Command to run | - |

## Best Practices

- `enable-cache: true` caches `~/.cache/uv` automatically
- `uv venv` creates `.venv` in workspace (isolated from system)
- Use `uv run` to execute commands in the venv without explicit activation
- `setup-uv@v7` handles Python installation via `python-version` input
