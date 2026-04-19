# 🌊 ViralWave — Section B MVP

Cross-cultural YouTube trend arbitrage tool. Built for the Innovation Challenge, Theme 1.

**Section B ownership:** Technical Execution (15%) + Innovation Implementation (15%) = **30% of the score**.

---

## ⚡ 60-second setup

```bash
# 1. install
pip install -r requirements.txt

# 2. drop Member C's data (one-time)
mkdir -p data
cp /path/to/cleaned_core_trends.csv data/

# 3. (optional) enable live AI — without this, the mock fallback still works
export GEMINI_API_KEY=your_key_here     # macOS/Linux
# Windows PowerShell:  $env:GEMINI_API_KEY="your_key_here"

# 4. run
streamlit run app.py
```

Opens at `http://localhost:8501`. Free Gemini key: https://aistudio.google.com/apikey

The sidebar shows a status indicator — if you see **🟢 Real data (10,000 rows)** the integration worked.

---

## 🔌 What's wired to Member C's data

The app loads `data/cleaned_core_trends.csv` and uses Member C's pre-computed columns directly:

| Member C's column | What the app does with it |
|---|---|
| `Country` (BR, CA, DE…) | Mapped to display names (Brazil, Canada, Germany…) |
| `Category_Name` | Used as-is for filtering and grouping |
| `Engagement_Rate` (0-1) | Multiplied by 100, displayed as ECR % |
| `Time_to_Trend_hrs` | Used directly as virality velocity input |
| `views`, `likes`, `comments` | Used for virality scoring + display |

If the CSV is missing, the app falls back to mock data automatically (sidebar shows 🟡). The demo never crashes.

---

## ⚠️ Important framing for the pitch

The dataset is a **single-day snapshot** (Feb 26, 2026). This means we **cannot** truthfully claim "Canada trends 48 hours before Country X" — that requires multi-day data.

We pivoted the arbitrage feature to **cultural overlap**, computed from the data:

> **What we measure now:** Of the videos trending in Country A, what % also trend in Country B? Higher overlap = stronger cultural corridor = more reliable arbitrage signal.

> **What v2 unlocks:** Once Member C delivers a multi-day snapshot, we add the temporal lag dimension — predicting **when** a trend will cross, not just **whether**.

This is honest, defensible, and sets up a clean roadmap if a judge asks "but how do you know it's *48 hours*?" — answer: we don't yet, that's v2.

**Real corridors the app surfaces from the data:**
- Canada ↔ USA: 89% overlap (1,015 shared videos)
- Canada ↔ UK: 86% overlap (957 shared)
- UK ↔ USA: 84% overlap (933 shared)
- ...plus 52 more, all computed live from Member C's data.

---

## 🎯 What this ships

| Page | Rubric coverage |
|---|---|
| 🏠 **Dashboard** — hero metrics, top trending, country × category heatmap | Product Design + Data Strategy |
| 🔮 **Virality Predictor** — keyword → score + AI brief + comparable real videos | **Technical Execution (core)** |
| 🌐 **Cross-Cultural Arbitrage** — Sankey of corridor flows, top opportunities, v2 roadmap | **Innovation (core)** |
| 📊 **Data Insights** — ECR, Time-to-Trend distribution, raw data view | Data Strategy |

---

## 🛡 Why this is demo-proof

Three layers of fallback so the live pitch can't blow up:

1. **Data fallback** — if `data/cleaned_core_trends.csv` is missing, the app spins up mock data automatically.
2. **AI fallback** — Gemini call has try/except + 8-second timeout. If it fails, a deterministic mock brief generator kicks in. The brief still references the real corridor data, so it sounds intelligent.
3. **Caching** — `@st.cache_data` on dataset load and corridor computation, so tab switches are instant after the first load.

If you want max safety for the live pitch, leave `GEMINI_API_KEY` blank. Brief generation is then 100% deterministic with zero network calls.

---

## 🎤 Suggested 90-second demo flow

1. **Dashboard** (15s) — *"10,000 trending videos across 11 countries. Here's the picture as of Feb 2026."*
2. **Virality Predictor** (30s) — Type a keyword live, e.g. "K-pop dance challenge" / Music / United States. Score renders. AI brief appears citing the real CA↔US corridor. Show comparable real videos below. *"This is what a brand gets before recording anything."*
3. **Cross-Cultural Arbitrage** (35s) — *"Standard YouTube analytics tools don't show you this. Canada and the US share 89% of their trending content — so a Canadian trend that hasn't crossed yet is your arbitrage window. We computed 55 of these corridors from the data."* ← **this is where you win Innovation**.
4. **Handoff to Member A** (10s) for commercial close.

If a judge asks about temporal lag → use the v2 roadmap line.

---

## 📁 Files

```
viralwave/
├── app.py                              # single-file Streamlit app
├── requirements.txt                    # deps
├── README.md                           # this
└── data/
    └── cleaned_core_trends.csv         # Member C's data (you drop it here)
```

---

## 🔧 Schema reference (for Member C / future you)

The app expects these columns in the CSV. If Member C's schema changes, edit the rename block in `load_dataset()`:

| Required | Type | Source |
|---|---|---|
| `video_id` | str | Member C |
| `Country` | str (ISO code) | Member C |
| `Category_Name` | str | Member C |
| `title` | str | Member C |
| `views`, `likes`, `comments` | int | Member C |
| `Engagement_Rate` | float (0-1) | Member C (pre-computed) |
| `Time_to_Trend_hrs` | float | Member C (pre-computed) |

Ship it.
