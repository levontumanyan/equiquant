# Report Analyst Subagent Specification

The Report Analyst is a specialized agent designed to interpret the output of the `equiquant` tool.
 It transforms raw CSV/TXT data into actionable investment intelligence.

## Core Capabilities

### 1. Multi-Ticker Comparative Synthesis
Instead of looking at one stock in isolation, the analyst identifies:
- **Best in Class**: Which ticker wins on specific key metrics (e.g., "MSFT has the strongest Profit Margin in this set").
- **Valuation Divergence**: Identifying stocks where price-based metrics (P/E, P/B) disagree with fundamental strengths (ROE, Profit Margin).

### 2. Anomaly & Risk Detection
- **Data Gaps**: Flagging metrics that are "N/A" and explaining how this impacts the confidence of the score.
- **Outlier Metrics**: Identifying metrics that are at extreme ends (e.g., TSLA's P/E of 360x) and explaining the potential market sentiment vs. fundamental reality.

### 3. Investment Narrative Generation
- **The "Why" behind the "Score"**: For each "Strong Buy" or "Avoid", provide a 2-sentence rationale based on the top 3 contributing factors.
- **Profile Alignment**: Validating if the results actually align with the chosen profile (e.g., "In this 'dividend' run, MSFT actually has a low yield despite the high total score").

## Integration Workflow

1. **Input**: The agent receives the path to a recently generated CSV report and the original command context (tickers, profile).
2. **Analysis**:
    - Read CSV using `pandas` or `csv` module.
    - Identify top/bottom performers.
    - Cross-reference with `benchmarks.md` to understand *why* a certain value was penalized or rewarded.
3. **Output**: A structured "Executive Summary" in Markdown format.

## Implementation Plan (in this branch)

- [ ] Create `core/analysis/reporting_expert.py` to provide helper functions for the subagent.
- [ ] Add a specific `PROMPT` for this subagent that instructs it to use these helpers.
- [ ] Verify the subagent can correctly identify why TSLA was an "Avoid" (P/E and PEG ratios) while MSFT was a "Strong Buy".
