# Cross-Model Doubt Adapters

Version-sensitive invocation examples for
[`tgd-core-doubt`](../skills/tgd-core-doubt/SKILL.md). The skill owns the safety
and authorization requirements; this reference helps construct an invocation
after the user chooses a CLI.

## Copyable Doubt Cycle

Use this worksheet for any doubt cycle, including one that remains within a
single model:

```text
Doubt cycle:
- [ ] Step 1: CLAIM — wrote the claim + why-it-matters
- [ ] Step 2: EXTRACT — isolated artifact + contract, stripped reasoning
- [ ] Step 3: DOUBT — invoked fresh-context reviewer with adversarial prompt
- [ ] Step 4: RECONCILE — classified every finding against the artifact text
- [ ] Step 5: STOP — met stop condition (trivial findings, 3 cycles, or user override)
```

A concrete CLAIM names both the decision and its consequence:

```text
CLAIM: "The new caching layer is thread-safe under the
        read-heavy workload described in the spec."
WHY THIS MATTERS: a race here corrupts user data and is
                  hard to detect in QA.
```

## Before Using an Adapter

The mandatory authorization, isolation, stdin, read-only, and failure-handling
rules live only in `tgd-core-doubt` under **Cross-model option — every cycle**.
Apply that section first. The material below is only a prompt and shell-shape
example after those rules authorize a specific adapter invocation.

## Prompt Shape

```text
Adversarial review. Find what is wrong with this artifact.
Assume the author is overconfident. Look for unstated assumptions, unhandled
edge cases, hidden coupling or shared state, contract violations, broken
conventions, and failure modes under unexpected input.

Do not validate or summarize. Report issues, or explicitly state that none were
found after thorough examination.

ARTIFACT:
<artifact only>

CONTRACT:
<contract only>
```

## Adapter Shapes

The following commands are illustrative. Confirm them against the installed
binary before each invocation; similar names can refer to different tools and
flags change across versions.

```bash
# Define this in a subshell-scoped function so cleanup cannot replace the
# caller's traps. Prompt bytes arrive on stdin; they are never shell syntax.
run_doubt_adapter() (
  set -eu
  adapter="$1"
  repo_path="$2"
  umask 077

  if ! doubt_dir="$(mktemp -d "${TMPDIR:-/tmp}/tgd-doubt.XXXXXX")"; then
    echo "failed to create private doubt directory" >&2
    exit 1
  fi
  trap 'rm -rf -- "$doubt_dir"' EXIT HUP INT TERM

  if ! prompt_path="$(mktemp "$doubt_dir/prompt.XXXXXX")"; then
    echo "failed to create private prompt file" >&2
    exit 1
  fi
  cat > "$prompt_path"

  case "$adapter" in
    codex)
      codex exec --sandbox read-only -C "$repo_path" - < "$prompt_path"
      ;;
    gemini)
      gemini --approval-mode plan -p "" < "$prompt_path"
      ;;
    *)
      echo "unsupported adapter: $adapter" >&2
      exit 2
      ;;
  esac
)

# After verifying flags/auth and authorizing exactly ONE adapter invocation:
repo_path="/absolute/path/to/repository"
printf '%s' "$review_prompt" | run_doubt_adapter codex "$repo_path"
```

The load-bearing properties are stdin input and read-only execution, not these
specific flag spellings. If the installed CLI cannot prove both properties,
stop and offer manual review or another tool.
