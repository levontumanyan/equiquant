# Data Provider Investigation: OpenBB vs. Polygon.io

This document summarizes the research into alternative data providers to replace or augment the current `yfinance` implementation.

---

## 🏗 Summary Comparison

| Feature | yfinance (Current) | OpenBB Platform | Polygon.io |
| :--- | :--- | :--- | :--- |
| **Type** | Unofficial Scraper | Aggregator / Middleware | Direct Data Provider |
| **Reliability** | Medium (Rate-limits, 404s) | High (Standardized SDK) | Tier 1 (Institutional) |
| **US Fundamentals**| Good (Ticker Info) | Excellent (via FMP/Polygon) | Excellent (vX Financials) |
| **Intraday Data** | Good | Excellent | Best (Tick-level, NBBO) |
| **Pricing** | Free | Free (Platform) + Data Keys | Free (Limited) / Paid |
| **Best For** | Prototyping | Multi-source consistency | High-performance US data |

---

## 🌐 OpenBB Platform (The "Middleware")

OpenBB is an open-source framework that provides a single Python SDK to access hundreds of data sources (Polygon, FMP, Tiingo, Yahoo, FRED, etc.).

### **Why use OpenBB?**
1. **Standardization**: It maps every provider's data into a unified format (`OBBject`). If we switch from Yahoo to Polygon, we don't have to rewrite our `YFinanceProvider` logic.
2. **Breadth**: Access to macro-economic data (FRED), sentiment, and alternative data in the same SDK.
3. **Redundancy**: Easily implement the "Multi-Provider Redundancy" pillar of our roadmap.

---

## 💎 Polygon.io (The "Infrastructure")

Polygon is a direct source for market data, used by professional developers and trading platforms.

### **Key Data Capabilities:**
1. **vX Financials**: Provides deep, normalized financial statements (Balance Sheet, Income, Cash Flow) extracted from XBRL (SEC filings). This is perfect for calculating **ROIC**, **FCF Yield**, and **Piotroski Scores**.
2. **Ticker Details**: Extremely reliable metadata (Sector, Industry, Market Cap, Share Class).
3. **Ticker News**: High-quality, ticker-specific news feed with summaries, ideal for our future "Sentiment Analysis" pillar.

---

## 📈 Integration Strategy

### **Scenario A: OpenBB as the "Unified Provider"**
We replace `yfinance` with the `openbb` SDK. We can then configure it to use Yahoo Finance for free, but easily upgrade to Polygon or Financial Modeling Prep (FMP) by just adding an API key to our `.env`.

### **Scenario B: Polygon as the "Direct Failover"**
We keep the current architecture but add a `PolygonProvider`.
1. **Primary**: `yfinance` (Free/Scraped).
2. **Failover/Advanced**: `Polygon` (Reliable/API).
   - Use Polygon for the advanced quantitative metrics that `yfinance` info lacks (like detailed 10-year historical statements).

---

## 🛠 Recommendation for the Roadmap

1. **Short-term**: Continue using `yfinance` for basic metrics but implement the **Provider Registry** pattern (Pillar 1.2).
2. **Medium-term**: Integrate the **OpenBB Platform SDK**. This gives us instant access to both Polygon and Yahoo Finance through a single interface, significantly reducing the "mapping" work we have to do.
