# Phase 13 — Streamlit Frontend: Full Deep Dive

---

## What is this phase doing conceptually?

All 12 previous phases built a FastAPI backend with 20+ endpoints. Phase 13 wraps them in a user-facing UI so a real investor can go through the complete workflow without touching Swagger docs or curl commands.

The framework choice is **Streamlit** — a Python-only framework that turns Python scripts into interactive web apps. No HTML, no JavaScript, no React. Just Python. This matters for a project that runs locally in PyCharm.

The 5-page flow mirrors the wealth management workflow:

```
1. Home page       → Create or load a user
2. Financial Profile → Enter income/savings/debt → see health metrics
3. Risk Assessment  → Answer questionnaire → compute risk score
4. Allocation       → Run compliance agent → see equity/debt/gold split
5. Simulation       → Enter SIP/goal → see success probability
6. Explanation      → Ollama narrates everything in plain English
```

---

## Project Structure

```
frontend/
├── app.py                        ← Home page + multi-page entry point
├── api_client.py                 ← All HTTP calls to FastAPI backend
├── utils.py                      ← Shared helpers: sidebar, formatting, charts
├── requirements.txt              ← streamlit, requests, matplotlib
└── pages/
    ├── 1_Financial_Profile.py
    ├── 2_Risk_Assessment.py
    ├── 3_Allocation.py
    ├── 4_Simulation.py
    └── 5_Explanation.py
```

**How Streamlit multi-page works**: Any `.py` file in `pages/` becomes a page in the sidebar automatically. The prefix `1_`, `2_` controls the sort order. The underscore and number are stripped for display: `1_Financial_Profile.py` → "Financial Profile" in the sidebar.

---

## Concept 1: Streamlit Execution Model

Unlike Flask or FastAPI, Streamlit is **not a web server that waits for requests**. Instead, every time a user interacts with a widget (clicks a button, changes a slider), the entire Python script runs from top to bottom again.

```python
# This runs EVERY TIME the user interacts with anything:
st.title("Financial Profile")
user_id = utils.require_user()
...
if submitted:
    profile = api_client.create_financial_profile(...)
    health = api_client.get_financial_health(user_id)
    st.metric("Net Worth", ...)
```

This is called the **reactive model**. Streamlit re-runs the script and re-renders the UI on each interaction. This means:

1. No explicit event handlers — just `if submitted:` checks
2. Variables don't persist between reruns by default
3. All state that needs to persist goes in `st.session_state`

---

## Concept 2: st.session_state — Cross-Rerun Persistence

`st.session_state` is a dict-like object that persists across script reruns for the same browser session. It's how data flows from one page to another.

```python
# app.py — after creating a user
st.session_state["user_id"] = user["id"]
st.session_state["user_name"] = user["name"]
```

Now when the user navigates to page 2, `st.session_state["user_id"]` is still available.

**Cross-page data flow**:

```
app.py:         session_state["user_id"]
                    ↓ (all pages read this)
2_Risk_Assessment: session_state["risk_tier"] = "Safer"
                   session_state["risk_score"] = 55
                    ↓
3_Allocation:   reads session_state["risk_tier"]
                session_state["equity_pct"] = 40
                session_state["debt_pct"] = 55
                session_state["gold_pct"] = 5
                    ↓
4_Simulation:   reads session_state["equity_pct"] etc.
                session_state["simulation_result"] = {...}
                    ↓
5_Explanation:  reads all session_state fields
                → sends to /explain
```

If the user skips a page (e.g., goes to Allocation without completing Risk Assessment), the missing session state triggers a guard:

```python
# pages/3_Allocation.py
if "risk_tier" not in st.session_state:
    st.warning("Complete **Risk Assessment** first to compute your risk tier.")
    st.stop()
```

`st.stop()` halts script execution — the rest of the page doesn't render.

---

## Concept 3: api_client.py — The HTTP Abstraction Layer

```python
# frontend/api_client.py
import requests

BASE_URL = "http://localhost:8000"

def create_user(name: str, email: str) -> dict:
    resp = requests.post(f"{BASE_URL}/users", json={"name": name, "email": email})
    resp.raise_for_status()
    return resp.json()

def get_financial_health(user_id: int) -> dict:
    resp = requests.get(f"{BASE_URL}/financial-health/{user_id}")
    resp.raise_for_status()
    return resp.json()

def run_compliance_check(user_id: int, goal_horizon_years: int) -> dict:
    resp = requests.post(f"{BASE_URL}/compliance-check", json={
        "user_id": user_id,
        "goal_horizon_years": goal_horizon_years,
    })
    resp.raise_for_status()
    return resp.json()
```

**Why a separate api_client.py?** All HTTP calls are in one place. Pages import functions, not `requests` directly. If the backend URL or an endpoint path changes, you change it in one file, not in every page.

`resp.raise_for_status()` — converts 4xx/5xx HTTP responses into `requests.exceptions.HTTPError`. Every page catches this:

```python
except requests.exceptions.HTTPError as e:
    st.error(f"API error: {e.response.text}")
```

`requests` (not `httpx`) is used here — the frontend is synchronous (Streamlit is not async). `requests` is the right choice for sync Python.

---

## Concept 4: st.form and st.form_submit_button

```python
with st.form("financial_profile_form"):
    annual_income = st.number_input("Annual Income (₹)", ...)
    monthly_expenses = st.number_input("Monthly Expenses (₹)", ...)
    submitted = st.form_submit_button("Save Financial Profile", type="primary")

if submitted:
    profile = api_client.create_financial_profile(...)
```

Without `st.form`, every widget change triggers a rerun. If the user types in the income field, Streamlit immediately reruns the script — and if there's code that calls the API on any number change, you'd make an API call on every keystroke.

`st.form` **batches** all widget interactions — changes don't trigger reruns until the form is submitted. `st.form_submit_button` is the trigger. Only when the button is clicked does the script rerun and `submitted = True`.

`type="primary"` — styles the button as the primary action (blue/filled). Secondary buttons have `type="secondary"` (grey/outlined).

---

## Concept 5: Graceful Error Handling Pattern

Every page wraps API calls in the same try/except pattern:

```python
try:
    result = api_client.some_call(...)
    # display results
except requests.exceptions.ConnectionError:
    st.error("Cannot connect to the backend. Is `docker-compose up` running?")
except requests.exceptions.HTTPError as e:
    st.error(f"API error: {e.response.text}")
```

Two different failure modes:
- `ConnectionError` — backend is completely unreachable (Docker not running)
- `HTTPError` — backend is running but returned an error (validation failure, 404, etc.)

`st.error()` renders a red error box. The app doesn't crash — the user sees a friendly message and can fix the issue (start Docker, correct their input, etc.).

---

## Concept 6: utils.py — Shared Helpers

```python
# frontend/utils.py

def require_user() -> int:
    """Returns user_id if set in session_state, else shows warning and stops."""
    if "user_id" not in st.session_state:
        st.warning("Please create or load a user on the **Home** page first.")
        st.stop()
    return st.session_state["user_id"]

def render_sidebar():
    """Renders the sidebar with current user info."""
    with st.sidebar:
        if "user_id" in st.session_state:
            st.success(f"User: {st.session_state.get('user_name', '')}")
            st.caption(f"ID: {st.session_state['user_id']}")

def format_inr(amount: float) -> str:
    """Format a float as Indian currency string."""
    if abs(amount) >= 1e7:
        return f"₹{amount/1e7:.2f} Cr"
    elif abs(amount) >= 1e5:
        return f"₹{amount/1e5:.2f} L"
    return f"₹{amount:,.0f}"

def plot_allocation_pie(equity: float, debt: float, gold: float):
    """Returns a matplotlib figure with the allocation pie chart."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(
        [equity, debt, gold],
        labels=["Equity", "Debt", "Gold"],
        autopct="%1.0f%%",
        colors=["#2196F3", "#4CAF50", "#FFC107"],
        startangle=90,
    )
    return fig
```

`require_user()` is called at the top of every page — the single point of enforcement for "must have a user". If it calls `st.stop()`, nothing below it renders.

`format_inr()` converts raw floats to Indian display conventions:
- ≥ ₹1 crore (10^7) → "₹X.XX Cr"
- ≥ ₹1 lakh (10^5) → "₹X.XX L"
- Below 1 lakh → "₹X,XXX"

This function is called by pages 1 and 5 for displaying financial amounts.

`plot_allocation_pie()` returns a matplotlib figure — Streamlit renders it with `st.pyplot(fig)`. The function is in utils because the same pie chart appears on both page 3 (after running compliance check) and any cached display.

---

## Concept 7: Metrics Display Pattern

```python
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Net Worth", utils.format_inr(health["net_worth"]))
m2.metric("Monthly Surplus", utils.format_inr(health["monthly_surplus"]))
m3.metric(
    "Savings Rate",
    f"{health['savings_rate']:.1f}%",
    delta=health["savings_rate_status"],
)
m4.metric(
    "Debt-to-Income",
    f"{health['debt_to_income_ratio']:.1f}%",
    delta=health["debt_to_income_status"],
    delta_color="inverse",
)
```

`st.columns(n)` creates n equal-width columns. `m1.metric(...)` renders a metric card in that column.

`st.metric(label, value, delta)`:
- `label` — the metric name
- `value` — the main displayed number
- `delta` — a secondary value shown below the main number, typically with a green ↑ or red ↓

`delta="high"` for savings rate → shown in green (high savings is good).
`delta_color="inverse"` for DTI → reverses green/red. "unhealthy" DTI normally shows red ↓, but with `inverse=True` it shows as expected (red = bad).

---

## The Complete User Journey

```
1. Home (app.py):
   st.form → name, email → api_client.create_user() → session_state["user_id"]

2. Financial Profile (1_Financial_Profile.py):
   st.form → income, expenses, savings, debt → api_client.create_financial_profile()
   → api_client.get_financial_health() → 5 metric cards

3. Risk Assessment (2_Risk_Assessment.py):
   GET /risk-assessment/questions → render 5 radio buttons
   st.form → selected answers → api_client.create_risk_assessment()
   → st.form for age/horizon/income → api_client.compute_risk_score()
   → session_state["risk_tier"], session_state["risk_score"]
   → progress bars showing score breakdown

4. Allocation (3_Allocation.py):
   reads session_state["risk_tier"] (guard)
   st.form → goal_horizon → api_client.run_compliance_check()
   → session_state["equity_pct"], ["debt_pct"], ["gold_pct"]
   → matplotlib pie chart + metric cards + compliance status

5. Simulation (4_Simulation.py):
   reads session_state["equity_pct"] etc. (guard)
   st.form → initial investment, monthly SIP, target amount → api_client.run_simulation()
   → session_state["simulation_result"]
   → success probability big number + percentile bar chart

6. Explanation (5_Explanation.py):
   reads all session_state (shows summary)
   "Generate Explanation" button → api_client.generate_explanation()
   → st.markdown renders the LLM's text
   → graceful message if Ollama unavailable
```

---

## Running the Frontend

```bash
# From project root
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

Streamlit starts a local server (default port 8501) and opens the browser automatically. Backend must be running (`docker-compose up`) at `localhost:8000`.

The `sys.path.insert(0, str(Path(__file__).parent))` at the top of each page file adds the `frontend/` directory to Python's module search path — this is how pages import `api_client` and `utils` even though they're in the parent directory of `pages/`.
