---
name: python-pip-ci
description: >
  GitHub Actions workflow steps for Python projects using pip.
  Use this skill when generating CI workflows that need pip-based
  dependency installation with virtual environment.
---

# Python CI with pip

## GitHub Actions Steps

### Setup and Install

```yaml
- uses: actions/checkout@v4

- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "{PYTHON_VERSION}"

- name: Create venv and install dependencies
  run: |
    python -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install {DEPENDENCIES}
```

### Running Commands

After setup, activate the venv before running commands:

```yaml
- name: Run command
  run: |
    source .venv/bin/activate
    {COMMAND}
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `{PYTHON_VERSION}` | Python version | `3.12` |
| `{DEPENDENCIES}` | Space-separated packages | - |
| `{COMMAND}` | Command to run | - |

## Best Practices

- Always upgrade pip first (`pip install --upgrade pip`)
- Use `python -m venv .venv` for consistent venv location
- Each step needs `source .venv/bin/activate` (state doesn't persist between steps)
- For caching, add `cache: 'pip'` to setup-python (requires requirements.txt)
