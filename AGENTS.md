# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Always run `make check` (format, lint, test, coverage) before finishing any task.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`. `analyze.py` is for CLI orchestration only.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `benchmarks/` and `profiles/` focused. Use `sectors.json` for valuation overrides.

## Environment & Execution
- **Branching Strategy**: **STRICT MANDATE**: Always work in a new branch. NEVER work on `main`.
	1. Research/Implementation in feature branch.
	2. Verify with `make check`.
	3. **Mandatory Functional Check**: Run `make run` in the branch and verify output.
	4. Merge locally only after user approval.
- **Tooling**: ALWAYS use `make` commands. Do NOT use `uv` or `python` directly.

## Testing & Validation
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test.
- **Verification**: Verify scoring changes against curves in `benchmarks.md`.
