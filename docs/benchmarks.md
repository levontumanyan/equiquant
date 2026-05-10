# Market Analysis Benchmarks

This document explains the scoring logic and benchmark configuration used to evaluate company fundamentals.

# Insider Ownership (`heldPercentInsiders`)

Insider ownership is a critical fundamental metric that represents the percentage of a company's stock owned by its management, directors, and other key individuals within the company.

## Why use a Bell Curve?

A **Bell Curve** (Gaussian distribution) is used for this metric because insider ownership is a "goldilocks" indicator. A simple linear or sigmoid (monotonic) scale—where more is always better—fails to capture the risks associated with extremely high ownership levels.

- **Low Ownership (< 5%)**: Management has little "skin in the game." This can lead to a lack of alignment between management and shareholders, as executives may not be personally invested in the long-term stock performance.
- **Optimal Range (10-25%)**: This is the "sweet spot." It demonstrates that management has significant personal wealth tied to the company's success, which strongly aligns their interests with those of public shareholders.
- **High/Extreme Ownership (> 50%)**: While management is highly aligned, this creates "control risk" or "entrenchment." Insiders can make decisions without needing to consider minority shareholders, and the stock often suffers from low liquidity (fewer shares available for the public to trade).

## Scoring Logic

The scoring function uses a Gaussian curve centered on a target value:

$$ \text{Score} = e^{-0.5 \cdot \left(\frac{\text{val} - \text{target}}{\text{width}}\right)^2} $$

### Parameters:
- **Target (`0.15`)**: A 15% ownership level is considered the ideal balance between alignment and control.
- **Width (`0.10`)**: Determines how quickly the score decays.

# PEG Ratio (`pegRatio`)

The PEG (Price/Earnings-to-Growth) Ratio is a key metric that balances valuation (P/E) with earnings growth.

## Why use a Bell Curve?

A **Bell Curve** is used to better capture the risks associated with extreme valuation outliers.

- **Suspiciously Low (< 0.3)**: Can be a "value trap" or unsustainable spike.
- **Optimal Range (0.5 – 1.0)**: The "sweet spot" for growth-at-a-reasonable-price (GARP).
- **High/Overvalued (> 2.0)**: Suggests you are paying too much for growth.

## Parameters:
- **Target (`0.7`)**: Ideal target for growth value.
- **Width (`0.6`)**: Determines how quickly the score drops off.

| PEG Value | Score | Interpretation |
| :--- | :--- | :--- |
| **0.1** | **~61%** | Suspiciously Low (Caution/Value Trap) |
| **0.4** | **~88%** | Excellent Value |
| **0.7** | **100%** | The "Sweet Spot" (Ideal) |
| **1.0** | **~88%** | Fair Value (Good) |
| **1.5** | **~41%** | Slightly Expensive (Weak) |
| **2.5** | **~1%** | Overvalued (Fail) |

# Scoring Functions Reference

The following mathematical functions are used to convert raw metrics into a standardized 0-100% score.

## 1. Sigmoid Curve (`sigmoid`)
The sigmoid function is used for "more is better" or "less is better" metrics that have a natural saturation point.

- **Formula**: $ \text{Score} = \frac{1}{1 + e^{k \cdot (\text{val} - \text{midpoint})}} $
- **Characteristics**: Smoothly transitions from 0 to 1. Great for metrics where once you hit a certain "excellent" threshold, additional improvements offer diminishing returns.
- **Examples**:
    - **Return on Equity (ROE)**: Higher is better, but anything over 30% is generally "excellent."
    - **P/E Ratio**: Lower is better, but there's a limit to how cheap a quality company gets.

## 2. Bell Curve (`bell_curve`)
A Gaussian distribution used for "Goldilocks" metrics where there is an ideal central target.

- **Formula**: $ \text{Score} = e^{-0.5 \cdot \left(\frac{\text{val} - \text{target}}{\text{width}}\right)^2} $
- **Characteristics**: Penalizes values that are either too high or too low.
- **Examples**:
    - **Insider Ownership**: Too little means no alignment; too much means control risk.
    - **PEG Ratio**: Too low is suspicious; too high is overvalued.
    - **Debt to Equity**: You want some leverage for growth, but not too much to be risky.

## 3. Linear Scale (`linear`)
A simple straight-line interpolation between a `best` and `worst` value.

- **Characteristics**: Consistent change in score for every unit of change in the metric.
- **Examples**:
    - **Profit Margins**: Useful when every percentage point of margin improvement is equally valued.

## 4. Threshold (`threshold`)
A binary pass/fail binary check.

- **Characteristics**: Returns 100% if the value meets the threshold, 0% otherwise.
- **Examples**:
    - **Dividend Yield**: Used when you simply want to filter for companies that pay at least *X*%.

# Analyst Recommendation (`recommendationMean`)

The Analyst Recommendation metric represents the consensus view of Wall Street analysts, typically ranging from 1.0 (Strong Buy) to 5.0 (Sell).

## Why use a Sigmoid Curve?

A **Sigmoid Curve** is used for analyst recommendations because it accurately reflects the non-linear significance of consensus changes.

- **Saturation at Excellence**: A "Strong Buy" (1.0) and a high "Buy" (1.5) are both extremely positive signals. The sigmoid curve stays relatively flat near the "best" value, ensuring both receive high scores without pedantic differentiation.
- **The "Hold" Cliff**: The most significant change in investor sentiment occurs between "Buy" (2.0) and "Hold" (3.0). The sigmoid curve is steepest at its midpoint (2.5), causing the score to drop rapidly as the consensus moves toward "Hold."
- **Diminishing Penalty**: Once a stock reaches "Underperform" (4.0) or "Sell" (5.0), it is already considered a failure from a recommendation standpoint. The curve flattens out at the "worst" end, assigning near-zero points to any score 4.0 or higher.
