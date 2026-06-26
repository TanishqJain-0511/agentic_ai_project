# User Journey — Agentic Wealth Management Copilot

## Overview
A first-time Indian retail investor comes to the app wanting to know how to invest their savings toward a financial goal.

---

## Step 1: Create Account
- User enters their name and email to create a profile.
- App assigns a `user_id` used across all subsequent steps.

---

## Step 2: Financial Profile
- User fills in their income, monthly expenses, savings, existing investments, and debt.
- App computes **financial health metrics**: net worth, monthly surplus, savings rate, debt-to-income ratio, emergency fund months.
- Each metric gets a status label (e.g. savings rate: *good / okay / low*).

---

## Step 3: Risk Assessment
- User answers a short questionnaire (investment experience, reaction to losses, etc.).
- User also provides: age, income stability, and goal horizon (years).
- App computes a **risk score (0–100)** and assigns a **risk tier**:
  - Safest · Safer · Riskier · Riskiest

---

## Step 4: Investment Goal
- User defines a goal: e.g. *"₹50L for retirement in 20 years"* or *"₹10L for a home down payment in 3 years"*.
- App stores goal name, target amount, target date, and priority.

---

## Step 5: Asset Allocation
- App runs the **compliance agent** (LangGraph loop):
  1. Computes a base allocation from risk tier (equity / debt / gold split).
  2. Applies horizon caps (e.g. short horizon → cap equity at 30%).
  3. Checks allocation against SEBI-inspired policy rules.
  4. Auto-fixes any violations and re-checks until converged.
- User sees a final compliant allocation with a pie chart.
- Any rule violations and how they were fixed are shown transparently.

---

## Step 6: Fund Selection
- App syncs live NAVs from MFAPI.
- User can browse mutual funds filtered by category (equity / debt / gold) and risk grade.
- The **fund research agent** (LangGraph + Ollama) can answer questions like *"Which large-cap funds suit a Safer investor?"*.

---

## Step 7: Monte Carlo Simulation
- User enters SIP amount or lump-sum investment.
- App runs **1000+ scenarios** using historical Indian market return assumptions.
- Output: success probability (%), and portfolio value at p10 / p25 / p50 / p75 / p90 percentiles.
- User sees whether their savings plan is likely to hit the goal.

---

## Step 8: Plain-English Explanation
- App sends all computed results (risk tier, allocation, simulation outcome, compliance status) to a local **Ollama LLM (llama3.2:3b)**.
- LLM narrates a 4–6 sentence plain-English summary tailored for Indian retail investors.
- Example: *"Given your moderate risk profile and 10-year horizon, a 60% equity, 30% debt, and 10% gold split is recommended. Your SIP of ₹15,000/month gives you an 82% chance of reaching your ₹1Cr goal..."*
- **The LLM never makes financial decisions** — it only narrates what the rules already computed.

---

## Step 9 (Future): Monitoring & Rebalancing
- Scheduled Celery tasks check portfolio drift periodically.
- If allocation drifts beyond thresholds, user is alerted to rebalance.

---

## Data Flow Summary

```
User Input
    ↓
Financial Profile → Financial Health Metrics
    ↓
Risk Questionnaire + Age/Horizon → Risk Score + Tier
    ↓
Compliance Agent (compute → check → fix → converge) → Final Allocation
    ↓
Monte Carlo Simulation → Success Probability
    ↓
Ollama LLM → Plain-English Explanation (narrates, never decides)
```
