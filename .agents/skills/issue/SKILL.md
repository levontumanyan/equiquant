---
name: issue
description: Use when creating structured GitHub issues with explicit labels for criticality and implementation effort.
user_invocable: true
---

# GitHub Issue Creation Skill

Automates the creation of structured GitHub issues, ensuring required metadata labels for prioritization and implementation complexity are generated and applied.

## Key Differences from Standard Creation

* **Automated Labeling** — Enforces classification of business value against technical complexity.
* **Idempotent Setup** — Verifies and creates necessary repository labels before issue instantiation.
* **Structured Scoping** — Collects defined metrics via interactive prompts to prevent poorly defined issues.

## Workflow

**Step 1: Detect repo info**

```bash
REPO_NAME=$(git remote get-url origin | sed -E 's/.*[:\/]([^\/]+\/[^\/.]+)(\.git)?$/\1/')
```

**Step 2: Define and Initialize Labels**

The skill requires two taxonomies: Criticality (Impact) and Easiness (Effort).

| Label Category | Name | Color | Description |
| --- | --- | --- | --- |
| **Criticality** | `criticality:high` | `b60205` | Blockers, severe regressions, or critical path items. |
|  | `criticality:medium` | `e99695` | Important features or bugs with valid workarounds. |
|  | `criticality:low` | `fef2c0` | Nice-to-haves, minor tweaks, or non-blocking debt. |
| **Easiness** | `easiness:easy` | `0e8a16` | Straightforward implementation, low risk, < 1 day. |
|  | `easiness:medium` | `fbca04` | Moderate complexity, requires architecture review. |
|  | `easiness:hard` | `d93f0b` | High risk, complex dependencies, multi-day effort. |

Execute setup checks:

```bash
for label in "criticality:high" "criticality:medium" "criticality:low" "easiness:easy" "easiness:medium" "easiness:hard"; do
	# Check if label exists, create if missing via gh api or gh label create
done

```

**Step 3: Gather Issue Metadata via AskUserQuestion**

Question 1 — Criticality:

```
Question: "What is the criticality of this issue?"
Header: "Criticality"
Options:
  - label: "high"
    description: "Critical path, blocker, or severe regression"
  - label: "medium"
    description: "Standard feature or bug with workaround"
  - label: "low"
    description: "Minor enhancement or non-blocking debt"

```

Question 2 — Easiness of Implementation:

```
Question: "How easy is this to implement?"
Header: "Easiness"
Options:
  - label: "easy"
    description: "Low effort, low risk, quick turnaround"
  - label: "medium"
    description: "Moderate complexity, standard development effort"
  - label: "hard"
    description: "High effort, high risk, or complex dependencies"

```

**Step 4: Input Title and Body**

* Prompt for issue title.
* Prompt for issue body (or use a predefined repository template).

**Step 5: Execute Issue Creation**

```bash
gh issue create \
	--repo "$REPO_NAME" \
	--title "$ISSUE_TITLE" \
	--body "$ISSUE_BODY" \
	--label "criticality:$CRITICALITY_SELECTION,easiness:$EASINESS_SELECTION"

```

**Step 6: Confirm**

Report execution metrics to the user:

* Issue Full URL / Number
* Applied Labels
* Assigned Milestones/Assignees (if applicable)
