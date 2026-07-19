#!/bin/bash
# validate-helm.sh — Catch YAML/Helm template errors BEFORE Fleet does
# Usage: ./scripts/validate-helm.sh [values-file]
#   e.g.  ./scripts/validate-helm.sh main/sky/chart/talos.yaml
#         ./scripts/validate-helm.sh main/sky/chart/eu.yaml
#         ./scripts/validate-helm.sh --all   (validate all values files)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

validate_values() {
    local values_file="$1"
    local chart_dir="main/sky/chart"

    echo "=== Validating with $values_file ==="

    # Render all templates (allow Helm template errors, we want to catch YAML ones)
    local rendered
    rendered=$(helm template sky "$chart_dir" -f "$values_file" 2>&1) || {
        echo -e "${RED}Helm template error (fix first):${NC}"
        echo "$rendered" | tail -20
        return 1
    }

    # Split rendered output into individual documents and validate each
    echo "$rendered" | python3 -c '
import sys, yaml

docs = sys.stdin.read()
# Split on YAML document separators, keeping the Source comments for context
parts = docs.split("---")
errors = 0
valid = 0

for i, part in enumerate(parts):
    part = part.strip()
    if not part:
        continue
    # Extract source comment
    source = ""
    for line in part.split("\n"):
        if line.startswith("# Source:"):
            source = line.replace("# Source: ", "")
            break
    if not source:
        continue

    try:
        # Parse as YAML (ignore the Source comment line)
        yaml_content = "\n".join(l for l in part.split("\n") if not l.startswith("#"))
        list(yaml.safe_load_all(yaml_content))
        valid += 1
    except yaml.YAMLError as e:
        errors += 1
        print(f"\033[31mFAIL\033[0m: {source}")
        if hasattr(e, "problem_mark"):
            m = e.problem_mark
            lines = yaml_content.split("\n")
            print(f"  Line {m.line+1}: {e.problem}")
            # Show context
            for j, l in enumerate(lines, 1):
                if abs(j - (m.line+1)) <= 2:
                    marker = ">>>" if j == m.line + 1 else "   "
                    print(f"  {marker} {j:3d}: {l.rstrip()}")
        else:
            print(f"  {str(e)[:200]}")
        print()

if errors == 0:
    print(f"\033[32mAll {valid} manifests valid ✅\033[0m")
else:
    print(f"\033[31m{errors} error(s), {valid} valid\033[0m")
    sys.exit(1)
'
    return $?
}

if [ "${1:-}" = "--all" ]; then
    # Validate all values files
    failed=0
    for f in main/sky/chart/talos.yaml main/sky/chart/eu.yaml; do
        if [ -f "$f" ]; then
            validate_values "$f" || failed=1
            echo
        fi
    done
    exit $failed
elif [ $# -ge 1 ]; then
    validate_values "$1"
else
    echo "Usage: $0 <values-file> | --all"
    echo "  e.g. $0 main/sky/chart/talos.yaml"
    exit 1
fi
