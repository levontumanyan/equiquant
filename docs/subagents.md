# Subagent Options & Definitions

This document defines specialized subagents tailored to the `market-analysis` architecture and financial domain.

## 1. Financial Expert
| Attribute | Definition |
| :--- | :--- |
| **Focus** | Valuation Logic & Domain Integrity |
| **Primary Files** | `benchmarks.md`, `sectors.json`, `core/scorers.py` |
| **Expertise** | Scoring curves, sector overrides, and financial metric interpretation. |
| **Usage** | Invoke when adjusting scoring weights or validating a new valuation metric. |

## 2. Report Analyst
| Attribute | Definition |
| :--- | :--- |
| **Focus** | Output Analysis & Data Insights |
| **Primary Files** | `reports/*.csv`, `reports/*.txt`, `core/stats.py` |
| **Expertise** | Identifying outliers, summarizing "make run" results, and performance auditing. |
| **Usage** | Invoke after `make run` to interpret CSV data or compare runs. |

## 3. Provider Architect
| Attribute | Definition |
| :--- | :--- |
| **Focus** | Data Ingestion & Scalability |
| **Primary Files** | `core/providers/`, `mappings.py`, `PROVIDERS.md` |
| **Expertise** | API integration, schema mapping, and `BaseProvider` implementation. |
| **Usage** | Invoke when adding new data sources (e.g., Bloomberg, Refinitiv) to the pipeline. |

## 4. Quality Guard
| Attribute | Definition |
| :--- | :--- |
| **Focus** | CI/CD & Compliance |
| **Primary Files** | `Makefile`, `tests/`, `AGENTS.md` |
| **Expertise** | Test coverage (>80%), linting (tabs only), and `make check` orchestration. |
| **Usage** | Invoke before merging to verify code standards and functional correctness. |
