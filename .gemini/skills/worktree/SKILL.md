---
name: worktree
description: This skill should be used when creating a git worktree for isolated feature work. Creates a new branch in a separate working directory adjacent to the main checkout, keeping the original checkout clean.
user_invocable: true
---

# Git Worktree Skill

Creates a git worktree for isolated feature work. The new branch lives in a separate working directory adjacent to the main checkout, keeping the original checkout clean.

# Workflow

## Step 1: Detect repo info

```bash
MAIN_WORKTREE=$(git worktree list --porcelain | head -1 | sed 's/^worktree //')
REPO_NAME=$(basename "$MAIN_WORKTREE")
CURRENT_BRANCH=$(git branch --show-current)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
```

Uses `MAIN_WORKTREE` so the skill works correctly even when invoked from an existing worktree.

## Step 2: Create an issue

- `gh issue create` if one doesn't already exist for the work you are doing.

## Step 3: Fetch latest from remote

**CRITICAL**: The local `main` (or `master`) ref is often stale — the user may not have pulled recently, or another worktree may have advanced the ref. Always fetch and branch from the **remote tracking ref**, never the local branch name.

```bash
git fetch origin "$DEFAULT_BRANCH"
```

After this, `origin/$DEFAULT_BRANCH` points at the true HEAD of the default branch on GitHub. The local `$DEFAULT_BRANCH` ref may be behind — **never use it as a base**.

## Step 4: Determine base branch

- If `CURRENT_BRANCH == DEFAULT_BRANCH` → base = `origin/$DEFAULT_BRANCH` (skip question)
- Otherwise → use AskUserQuestion:

```
Question: "Create worktree from `<default>` or from `<current-branch>`?"
Header: "Base"
Options:
  - label: "<default> (Recommended)"
    description: "Branch from the latest origin/<default> (freshly fetched)"
  - label: "<current-branch>"
    description: "Branch from the current working branch"
```

**In both cases where the default branch is chosen, the base MUST be `origin/$DEFAULT_BRANCH`** — the remote tracking ref, not the local branch name. This guarantees the new worktree starts from the actual latest commit on GitHub, regardless of whether the local checkout has been pulled.

## Step 5: Gather branch info via AskUserQuestion

Ask two questions:

**Question 1 — GitHub Issue:**
```
Question: "Associate with a GitHub Issue?"
Header: "Issue"
Options:
  - label: "None"
    description: "No issue prefix"
  (user provides issue number via "Other")
```

**Question 2 — Description:**
```
Question: "Short description for the branch (kebab-case)?"
Header: "Name"
Options:
  (user provides description via "Other" — all options are examples)
  - label: "feature-name"
    description: "Example: use kebab-case, keep it short"
  - label: "fix-bug-name"
    description: "Example: prefix with fix- for bug fixes"
```

## Step 6: Construct branch name

- Naming: Use semantic prefixes: feat/, bug/, improvement/, docs/, refactor/.
- then add a small description.

## Step 7: Construct worktree path

```bash
WORKTREE_PATH="$(dirname "$MAIN_WORKTREE")/${REPO_NAME}--${DESCRIPTION}"
```

Uses the description portion only (strip issue prefix). The `--` separator distinguishes worktrees from regular repo clones.

## Step 8: Pre-flight checks

- **Directory already exists** → error, suggest `git worktree prune` or pick a different name
- **Branch already exists** → offer `git worktree add <path> <existing-branch>` (no `-b` flag)

## Step 9: Create the worktree

```bash
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "$BASE"
```

## Step 10: Confirm

Report to the user:
- Worktree path
- Branch name
- Base branch/commit
- Cleanup instructions: `git worktree remove <path>` and `git branch -d <branch>` after merge
