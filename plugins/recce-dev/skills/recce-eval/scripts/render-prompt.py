#!/usr/bin/env python3
"""Render a prompt template with variables from a scenario YAML.

Usage: python3 render-prompt.py <template.md> <scenario.yaml> [--var key=value ...]
Outputs rendered prompt to stdout.

Variables from scenario YAML (prompt.vars) are substituted first.
Additional --var overrides (e.g., adapter_description) are applied after.
"""
import sys, yaml, argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("template", help="Path to prompt template file")
    parser.add_argument("scenario", help="Path to scenario YAML file")
    parser.add_argument("--var", action="append", default=[], help="Extra var: key=value")
    args = parser.parse_args()

    with open(args.template) as f:
        template = f.read()
    with open(args.scenario) as f:
        scenario = yaml.safe_load(f)

    vars_dict = scenario.get("prompt", {}).get("vars", {})

    for v in args.var:
        key, _, value = v.partition("=")
        vars_dict[key] = value

    rendered = template
    for key, value in vars_dict.items():
        rendered = rendered.replace("{" + key + "}", str(value))

    print(rendered)

if __name__ == "__main__":
    main()
