# ExcelGPT — Nigerian Report Templates

ExcelGPT ships with five template families tuned to how Nigerian organisations actually report. The action plan's `nigerian_context.template_type` (`banking`, `sales`, `hr`, `general`) selects the family; LGA/territory features activate when `lga_analysis` is `true`. All currency renders as **NGN (₦)**, and the fiscal calendar honours either a **January** (calendar) or **April** (some government/corporate) year start.

---

## 1. Banking & Finance

For deposit money banks, microfinance banks, and fintechs reporting to management and regulators.

**Use cases**
- **CBN returns** — structured periodic returns to the Central Bank of Nigeria (deposits, loans, liquidity ratios).
- **Branch performance** — deposits, loans, account openings, and growth ranked across branches.
- **Deposit/loan reports** — portfolio mix, par (portfolio-at-risk), loan-to-deposit ratio, NPL trends.

**Typical operations:** `group_sum`, `growth_rate`, `rank`, `forecast`.
**Key dimensions:** `branch_code`, `branch_name`, `region`, `product`, `lga`.
**Output sheets:** Executive Summary, Data, Analysis (ratios + rankings), Forecast.
**Nigerian specifics:** CBN reporting periods, ₦ thousands/millions/billions scaling, prudential ratio thresholds.

---

## 2. Sales Performance

For FMCG, telecoms, pharma, and any field-sales organisation.

**Use cases**
- **FSO/DSA hierarchy ranking** — Field Sales Officers and Direct Sales Agents ranked within their reporting lines.
- **Territory analysis** — performance by region → state → LGA → ward.
- **Target vs actual** — achievement %, variance, and gap-to-target by rep and territory.

**Typical operations:** `group_sum`, `group_avg`, `rank`, `score`, `growth_rate`, `chart`.
**Key dimensions:** `fso_id`, `dsa_id`, `manager`, `territory`, `state`, `lga`, `product`, `target`, `actual`.
**Output sheets:** Executive Summary, Data, Analysis (rankings + achievement), Charts.
**Nigerian specifics:** distributor/territory structures, 36 states + FCT, multi-tier agent hierarchies.

---

## 3. HR & Payroll

For HR and payroll teams handling Nigerian statutory deductions and workforce reporting.

**Use cases**
- **PENCOM** — pension contributions (employee + employer) per the Pension Reform Act.
- **NHF** — National Housing Fund deductions.
- **PAYE** — Pay-As-You-Earn tax computed on the relevant bands.
- **Staff performance** — appraisal scoring and ranking.
- **Headcount** — distribution by department, grade, location, and gender.

**Typical operations:** `group_sum`, `group_avg`, `score`, `rank`, `filter`.
**Key dimensions:** `staff_id`, `department`, `grade`, `location`, `gross_pay`, `deductions`.
**Output sheets:** Executive Summary, Data (payroll register), Analysis (statutory summaries), Charts.
**Nigerian specifics:** PENCOM/NHF/PAYE deduction logic, grade-level structures, state-of-posting breakdowns.

---

## 4. Executive Reports

For board, EXCO, and senior-management consumption.

**Use cases**
- **Board pack** — consolidated, high-polish multi-section report.
- **KPI dashboard** — headline KPI cards with period deltas and direction.
- **Variance analysis** — budget vs actual vs prior period, with explanations.

**Typical operations:** `group_sum`, `growth_rate`, `chart`, `forecast`.
**Key dimensions:** business unit, period, budget, actual, prior.
**Output sheets:** Executive Summary (primary), Analysis, Charts, Forecast.
**Formatting tier:** usually `executive` — premium styling, embedded charts, clean KPI cards.

---

## 5. LGA / Territory Intelligence

Geographic intelligence across Nigeria's administrative hierarchy. Activated by `nigerian_context.lga_analysis = true`.

**Use cases**
- **State-level breakdown** — roll up metrics across the 36 states + FCT.
- **Ward analysis** — drill down below LGA to ward level where data permits.
- **Geographic performance** — heatmaps and rankings by region (North-Central, North-East, North-West, South-East, South-South, South-West).

**Typical operations:** `group_sum`, `group_avg`, `cluster`, `rank`, `chart`.
**Key dimensions:** `geopolitical_zone`, `state`, `lga`, `ward`.
**Output sheets:** Executive Summary, Data, Analysis (geographic rankings), Charts (heatmaps).
**Nigerian specifics:** 6 geopolitical zones, 36 states + FCT, 774 LGAs, ward structures; clustering territories into performance tiers.

---

## Template selection matrix

| `template_type` | LGA-aware | Primary intents | Signature sheets |
|-----------------|:---------:|-----------------|------------------|
| `banking` | optional | aggregation, growth, forecasting | Summary, Analysis, Forecast |
| `sales` | yes | scoring, ranking, growth | Analysis, Charts |
| `hr` | optional | aggregation, scoring | Data, Analysis |
| `general` (executive) | optional | growth, forecasting | Summary, Charts, Forecast |
| `general` (+ `lga_analysis`) | yes | aggregation, clustering | Analysis, Charts |

## Shared conventions

- **Currency:** NGN, symbol ₦, with thousands/millions/billions scaling on KPI cards.
- **Fiscal calendar:** `january` or `april` start, set per report in `nigerian_context.fiscal_calendar`.
- **Geography:** consistent `zone → state → lga → ward` hierarchy across templates.
- **Formatting tiers:** `standard` (clean), `premium` (styled + conditional formatting), `executive` (board-ready, embedded charts).
