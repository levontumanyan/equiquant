---
name: copilot-feedback-reviewer
description: Fetches, analyzes, and applies or validates inline review comments left by github-copilot[bot] on a Pull Request. Use this skill whenever the user wants to review, address, or apply Copilot's PR feedback, check what Copilot found, see automated review comments, or process Copilot suggestions. Trigger on phrases like "check copilot feedback", "what did copilot say", "apply copilot suggestions", "review copilot comments", or any mention of Copilot bot findings on a PR.
tools:
  - gh-cli
user_invocable: true
---

# Copilot Feedback Reviewer

Review, triage, fix, and reply inline to all unresolved feedback left by `github-copilot[bot]` on a GitHub Pull Request.

# Workflow

# Step 1 — Detect the PR

Infer the repo and open PR from git context:

```bash
gh repo view --json owner,name   # → owner.login, name
gh pr view --json number,url,headRefName
```

If no open PR exists on the current branch, tell the user and stop.

# Step 2 — Fetch all unresolved Copilot threads

The REST API has no resolved/unresolved distinction, so use GraphQL. Fetch both the thread `id` (to resolve the thread later) and each comment's `databaseId` (to post inline replies).

```bash
gh api graphql -f query='
	query($owner: String!, $repo: String!, $pr: Int!) {
		repository(owner: $owner, name: $repo) {
			pullRequest(number: $pr) {
				reviewThreads(first: 100) {
					nodes {
						id
						isResolved
						path
						line
						comments(first: 10) {
							nodes {
								databaseId
								author { login }
								body
								createdAt
								url
							}
						}
					}
				}
			}
		}
	}
' -f owner=OWNER -f repo=REPO -F pr=NUMBER
```

Keep threads where `isResolved: false` AND at least one comment has `author.login == "github-copilot[bot]"`.

For each kept thread, record:
- The thread `id` (GraphQL ID)
- The comment `databaseId` of the Copilot comment

If `reviewThreads` returns exactly 100 nodes, paginate using `pageInfo.endCursor`.

If there are zero matching threads, tell the user there's nothing unresolved from Copilot and stop.

# Step 3 — Classify findings by criticality

For each unresolved Copilot comment, assign one of three buckets based on actual impact — not Copilot's phrasing:

**Critical** (must fix before merge):
- Security vulnerabilities: injection, credential exposure, insecure defaults, broken auth
- Logic bugs that produce incorrect behavior
- Data corruption or loss risks
- Missing error handling on paths that can fail at runtime
- Race conditions or concurrency hazards

**Medium** (should fix, won't break immediately):
- Performance problems: N+1 queries, blocking calls on hot paths, unnecessary allocations
- Missing input validation at system boundaries (user input, external APIs)
- Error messages that hide root causes
- Non-obvious complexity or duplication

**Low** (nice to fix when convenient):
- Style and naming improvements
- Documentation or docstring gaps
- Minor readability tweaks
- Preference-based or pedantic feedback

When in doubt, round up. Copilot sometimes phrases high-severity issues mildly.

# Step 4 — Present the analysis

Use this structure:

```
## Copilot Review — PR #<number>

**<N> unresolved findings** · <X> critical  <Y> medium  <Z> low

---

## Critical (<X>)

1. `path/to/file.py` · line <N>
   > <Copilot's comment, quoted verbatim>

   **Impact**: <one sentence — what actually breaks or risks if ignored>
   **Fix**: <Copilot's suggested change, or your interpretation if none was given>

---

## Medium (<Y>)
...

## Low (<Z>)
...
```

The "Impact" line is your synthesis — turn Copilot's technical observation into a plain consequence statement. Don't just restate the comment.

# Step 5 — Offer to apply fixes

After the report, ask:

> "Want me to apply fixes? Options: all findings, critical only, or pick specific numbers. If you choose to skip, I will still reply and mark them resolved."

Wait for the user's response before touching any files.

# Step 6 — Apply fixes

For each finding the user wants fixed:

1. Read the file at the relevant path and surrounding lines for context
2. Apply the minimal change that resolves the finding — don't reformat unrelated code or expand scope
3. If the fix requires broader refactoring or the comment is genuinely ambiguous, describe the approach and ask before touching anything

Keep a log of what was done for each finding (fixed / skipped / needs discussion), since you'll use it in Step 7.

# Step 7 — Reply inline and resolve every Copilot thread

You must post an inline reply to **every** Copilot comment and resolve the thread, even for the comments where you applied no code fixes. This closes the loop and keeps the PR review history clean.

First, post the reply comment using the REST API with the `databaseId` collected in Step 2:

```bash
gh api repos/OWNER/REPO/pulls/NUMBER/comments/COMMENT_DATABASE_ID/replies \
	-X POST \
	-f body="Your reply here"
```

Tailor each reply to its outcome:
- **Fixed**: "Fixed — [one sentence describing exactly what changed and why it resolves the issue]."
- **Skipped / Acknowledged**: "Acknowledged — this is a minor [style/naming/readability] concern. Not addressing it in this PR to keep the diff focused."
- **Skipped by user choice**: "Noted — [brief reason the user gave, or a neutral acknowledgment]."
- **Needs discussion**: "Flagged for discussion — [explain why the fix isn't straightforward and what would need to happen]."

Second, immediately mark the thread as resolved using the GraphQL API with the thread `id` collected in Step 2:

```bash
gh api graphql -f query='
	mutation($threadId: ID!) {
		resolveReviewThread(input: {threadId: $threadId}) {
			thread {
				id
				isResolved
			}
		}
	}
' -f threadId=THREAD_ID
```

After replying and resolving all threads, present a final summary to the user detailing how many findings were resolved and if any require further discussion.
