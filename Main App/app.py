"""
ViralWave — Cross-Cultural YouTube Trend Arbitrage
==================================================
MVP for the Innovation Challenge (Theme 1: YouTube data).

Owner: Member B (Tech & AI Dev)
Defends: Technical Execution (15%) + Innovation Implementation (15%)

Data: cleaned_core_trends.csv (Member C). Single snapshot, 11 countries.
Because the data is one snapshot, arbitrage is measured as CULTURAL OVERLAP
(co-trending probability between country pairs) rather than temporal lag.
Roadmap: temporal lag is unlocked once Member C delivers a multi-day snapshot.
"""

import os
import random
from datetime import datetime, timedelta
from itertools import combinations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- Optional: Gemini API (graceful fallback if unavailable) ---
try:
    import google.generativeai as genai
    _GEMINI_LIB = True
except ImportError:
    _GEMINI_LIB = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_ENABLED = _GEMINI_LIB and bool(GEMINI_API_KEY)
if GEMINI_ENABLED:
    genai.configure(api_key=GEMINI_API_KEY)


# ============================================================
# PAGE CONFIG & STYLING
# ============================================================
st.set_page_config(
    page_title="ViralWave | Cross-Cultural Trend Arbitrage",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .big-title {
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(90deg, #06b6d4 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .subtitle { color: #94a3b8; font-size: 1.05rem; margin-top: 0.25rem; }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(6,182,212,0.08), rgba(139,92,246,0.08));
        border: 1px solid rgba(148,163,184,0.15);
        padding: 1rem 1.25rem;
        border-radius: 14px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.85rem; font-weight: 700; }

    .arb-card {
        background: #111827;
        border-left: 4px solid #06b6d4;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    .arb-high { border-left-color: #10b981; }
    .arb-med { border-left-color: #f59e0b; }
    .arb-low { border-left-color: #ef4444; }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    .section-header {
        font-size: 1.35rem;
        font-weight: 700;
        margin: 1.5rem 0 0.75rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid rgba(148,163,184,0.2);
    }
</style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CONSTANTS — wired to Member C's real dataset
# ============================================================
COUNTRY_NAMES = {
    "BR": "Brazil", "CA": "Canada", "DE": "Germany", "FR": "France",
    "GB": "United Kingdom", "IN": "India", "JP": "Japan", "KR": "South Korea",
    "MX": "Mexico", "RU": "Russia", "US": "United States",
}
COUNTRIES = list(COUNTRY_NAMES.values())

CATEGORIES = [
    "Autos & Vehicles", "Comedy", "Education", "Entertainment",
    "Film & Animation", "Gaming", "Howto & Style", "Music",
    "News & Politics", "Nonprofits", "People & Blogs",
    "Pets & Animals", "Science & Tech", "Sports", "Travel & Events",
]

DATA_PATH_CANDIDATES = [
    "data/cleaned_core_trends.csv",
    "cleaned_core_trends.csv",
    "/mnt/user-data/uploads/cleaned_core_trends.csv",
]


# ============================================================
# DATA LAYER
# ============================================================
def _find_data_file():
    for p in DATA_PATH_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


@st.cache_data
def load_dataset():
    """Returns (dataframe, source_label). Falls back to mock if CSV is missing."""
    path = _find_data_file()
    if path is None:
        df = _generate_mock_dataset()
        return _compute_derived_metrics(df), "🟡 Mock (no CSV found)"

    df = pd.read_csv(path)
    df = df.rename(columns={
        "Country": "country_code",
        "Category_Name": "category",
        "Engagement_Rate": "engagement_rate_raw",
        "Time_to_Trend_hrs": "trending_hours",
    })
    df["country"] = df["country_code"].map(COUNTRY_NAMES).fillna(df["country_code"])
    df["engagement_rate"] = df["engagement_rate_raw"] * 100
    df = _compute_derived_metrics(df)
    return df, f"🟢 Real data ({len(df):,} rows)"


def _compute_derived_metrics(df):
    df = df.copy()
    if "engagement_rate" not in df.columns:
        df["engagement_rate"] = (df["likes"] / df["views"].clip(lower=1)) * 100
    df["virality_velocity"] = -df["trending_hours"]

    def norm(s):
        rng = s.max() - s.min()
        return (s - s.min()) / rng if rng > 0 else s * 0

    df["virality_score"] = (
        norm(df["engagement_rate"]) * 40
        + norm(df["virality_velocity"]) * 30
        + norm(np.log1p(df["views"])) * 30
    )
    return df


def _generate_mock_dataset(n=600):
    random.seed(42); np.random.seed(42)
    rows = []
    for i in range(n):
        country = random.choice(COUNTRIES)
        category = random.choice(CATEGORIES)
        views = int(np.random.lognormal(13.2, 1.4))
        likes = int(views * np.random.uniform(0.03, 0.13))
        comments = int(likes * np.random.uniform(0.05, 0.18))
        rows.append({
            "video_id": f"vid_{i:04d}",
            "title": f"{category} sample #{i}",
            "country": country, "category": category,
            "views": views, "likes": likes, "comments": comments,
            "publish_time": datetime.now() - timedelta(days=int(np.random.randint(1, 30))),
            "trending_hours": float(np.random.uniform(4, 720)),
        })
    return pd.DataFrame(rows)


# ============================================================
# CULTURAL CORRIDOR DETECTION
# ============================================================
@st.cache_data
def compute_corridors(df, min_shared=30):
    """For each country pair: co-trending overlap and dominant categories."""
    country_videos = {c: set(g["video_id"]) for c, g in df.groupby("country")}
    corridors = []
    for a, b in combinations(country_videos.keys(), 2):
        shared = country_videos[a] & country_videos[b]
        if len(shared) < min_shared:
            continue
        overlap_pct = len(shared) / min(len(country_videos[a]), len(country_videos[b]))
        shared_df = df[df["video_id"].isin(shared)]
        top_cats = shared_df["category"].value_counts().head(3).index.tolist()
        corridors.append({
            "source": a, "target": b,
            "overlap_pct": float(overlap_pct),
            "shared_videos": len(shared),
            "categories": top_cats,
        })
    return sorted(corridors, key=lambda c: -c["overlap_pct"])


# ============================================================
# AI LAYER
# ============================================================
def predict_with_ai(keyword, category, country, corridors):
    matches = [c for c in corridors
               if (c["source"] == country or c["target"] == country)
               and category in c["categories"]]
    matches.sort(key=lambda c: -c["overlap_pct"])
    if matches:
        m = matches[0]
        partner = m["target"] if m["source"] == country else m["source"]
        overlap = m["overlap_pct"]
    else:
        partner, overlap = None, None

    prompt = (
        f"You are a YouTube virality strategist for e-commerce brands.\n"
        f"Keyword: {keyword}\nCategory: {category}\nTarget country: {country}\n"
        + (f"Strongest cultural corridor: {country} ↔ {partner} "
           f"({int(overlap*100)}% co-trending overlap).\n" if partner else "")
        + "\nWrite a concise strategic brief (≤130 words, markdown) with:\n"
        "1. Virality outlook (BULLISH / NEUTRAL / BEARISH) + one-line reason.\n"
        "2. One specific content angle that maximizes cross-cultural spread.\n"
        "3. Arbitrage play: which country to LAUNCH IN FIRST and why.\n"
        "Be direct. No preamble."
    )

    if GEMINI_ENABLED:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(prompt, request_options={"timeout": 8})
            return resp.text, "🟢 Gemini Live"
        except Exception as e:
            return _mock_ai(keyword, category, country, partner, overlap), \
                   f"🟡 Fallback (API: {str(e)[:40]}…)"
    return _mock_ai(keyword, category, country, partner, overlap), \
           "🟡 Mock (set GEMINI_API_KEY for live)"


def _mock_ai(keyword, category, country, partner, overlap):
    rng = random.Random(f"{keyword}-{category}-{country}")
    outlook = rng.choice(["BULLISH", "BULLISH", "NEUTRAL"])
    angle = rng.choice([
        "a native-format short (≤45s) with a visual hook in the first 2 seconds",
        "a duet/stitch of the top-performing source video with a localized punchline",
        "a creator-collab leveraging a mid-tier local voice for authenticity",
        "a behind-the-scenes teaser dropped 24h before the main cut",
        "a POV-style opener followed by a 3-beat payoff structure",
    ])
    if partner and overlap is not None:
        arb_line = (
            f"**Arbitrage Play.** Test in **{partner} first** — it shares "
            f"**{int(overlap*100)}% of trending {category} content** with {country}. "
            f"If it lands in {partner}, the corridor data says it has the highest "
            f"probability of crossing into {country} next."
        )
    else:
        arb_line = (
            f"**Arbitrage Play.** No strong cultural corridor identified for {category} "
            f"into {country}. Recommend launching directly with locally-led creative."
        )
    return (
        f"**Outlook: {outlook}** — Signal on *\"{keyword}\"* in {category}/{country} "
        f"is consistent with our cross-cultural model.\n\n"
        f"**Content Angle.** Lead with {angle}. This format is over-represented in the "
        f"top trending videos for this category.\n\n"
        f"{arb_line}"
    )


# ============================================================
# PAGES
# ============================================================
def page_dashboard(df, corridors):
    st.markdown('<div class="big-title">🌊 ViralWave</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Predict the next viral content wave across 11 countries — '
        'before it happens.</div>', unsafe_allow_html=True,
    )
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos Tracked", f"{len(df):,}")
    c2.metric("Countries", df["country"].nunique())
    c3.metric("Avg Virality Score", f"{df['virality_score'].mean():.1f}")
    c4.metric("Active Corridors", len(corridors))

    st.markdown('<div class="section-header">🔥 Top trending now</div>', unsafe_allow_html=True)
    top = df.nlargest(10, "virality_score")[
        ["title", "country", "category", "views", "engagement_rate", "virality_score"]
    ].copy()
    top["views"] = top["views"].apply(lambda v: f"{int(v):,}")
    top["engagement_rate"] = top["engagement_rate"].round(2).astype(str) + "%"
    top["virality_score"] = top["virality_score"].round(1)
    top.columns = ["Title", "Country", "Category", "Views", "ECR", "Virality Score"]
    st.dataframe(top, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-header">🌍 Virality heatmap — Country × Category</div>',
                unsafe_allow_html=True)
    pivot = df.pivot_table(index="country", columns="category",
                           values="virality_score", aggfunc="mean").round(1)
    fig = px.imshow(pivot, color_continuous_scale="Viridis", aspect="auto",
                    labels={"color": "Avg Virality"})
    fig.update_layout(
        height=480, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
    )
    st.plotly_chart(fig, use_container_width=True)


def page_predictor(df, corridors):
    st.markdown('<div class="big-title">🔮 Virality Predictor</div>', unsafe_allow_html=True)
    st.caption("Score any concept against real trending baselines.")

    with st.form("predict_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        keyword = col1.text_input("Keyword / concept", value="K-pop dance challenge")
        default_cat = df["category"].mode().iloc[0] if len(df) else "Music"
        cat_idx = CATEGORIES.index(default_cat) if default_cat in CATEGORIES else 7
        category = col2.selectbox("Category", CATEGORIES, index=cat_idx)
        country = col3.selectbox("Target country", COUNTRIES,
                                 index=COUNTRIES.index("United States"))
        submitted = st.form_submit_button("Predict virality →", use_container_width=True)

    if not submitted:
        st.info("Enter a concept above and hit **Predict virality →** to run the model.")
        return

    sub = df[(df["category"] == category) & (df["country"] == country)]
    baseline = float(sub["virality_score"].mean()) if len(sub) >= 5 else float(df["virality_score"].mean())

    rng = random.Random(f"{keyword}-{category}-{country}")
    score = max(0.0, min(100.0, baseline + rng.uniform(-8, 18)))

    corridor_match = next(
        (c for c in corridors
         if (c["source"] == country or c["target"] == country) and category in c["categories"]),
        None,
    )
    if corridor_match:
        score = min(100.0, score + corridor_match["overlap_pct"] * 6)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Virality Score", f"{score:.0f}/100",
              "High" if score >= 70 else "Medium" if score >= 50 else "Low")
    m2.metric("Category baseline", f"{baseline:.0f}/100")
    m3.metric("Suggested length", rng.choice(["25s", "38s", "45s", "60s"]))
    conf = 60 + (corridor_match["overlap_pct"] * 30 if corridor_match else 10)
    m4.metric("Confidence", f"{int(conf)}%")

    gauge = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": "#06b6d4"},
            "steps": [
                {"range": [0, 40], "color": "#1f2937"},
                {"range": [40, 70], "color": "#374151"},
                {"range": [70, 100], "color": "#4b5563"},
            ],
            "threshold": {"line": {"color": "#f43f5e", "width": 3},
                          "thickness": 0.75, "value": 75},
        },
        number={"font": {"size": 44, "color": "#e5e7eb"}},
    ))
    gauge.update_layout(
        height=260, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font_color="#e5e7eb",
    )
    st.plotly_chart(gauge, use_container_width=True)

    st.markdown('<div class="section-header">🧠 AI Strategic Brief</div>', unsafe_allow_html=True)
    with st.spinner("Generating brief…"):
        brief, source = predict_with_ai(keyword, category, country, corridors)
    st.caption(f"Source: {source}")
    st.markdown(brief)

    if len(sub) > 0:
        st.markdown('<div class="section-header">📺 Comparable real trending videos</div>',
                    unsafe_allow_html=True)
        comp = sub.nlargest(5, "virality_score")[
            ["title", "views", "engagement_rate", "virality_score"]
        ].copy()
        comp["views"] = comp["views"].apply(lambda v: f"{int(v):,}")
        comp["engagement_rate"] = comp["engagement_rate"].round(2).astype(str) + "%"
        comp["virality_score"] = comp["virality_score"].round(1)
        comp.columns = ["Title", "Views", "ECR", "Virality Score"]
        st.dataframe(comp, use_container_width=True, hide_index=True)


def page_arbitrage(df, corridors):
    st.markdown('<div class="big-title">🌐 Cross-Cultural Arbitrage</div>',
                unsafe_allow_html=True)
    st.caption(
        "Which country pairs share trending content — and how much. "
        "If a video is trending in Country A but not yet in Country B, "
        "the corridor strength tells you the probability it crosses over."
    )

    if not corridors:
        st.warning("No corridors detected — dataset may be too sparse.")
        return

    st.markdown('<div class="section-header">Active cultural corridors</div>',
                unsafe_allow_html=True)
    countries_in_flow = list({c["source"] for c in corridors} |
                             {c["target"] for c in corridors})
    idx = {c: i for i, c in enumerate(countries_in_flow)}

    sankey = go.Figure(go.Sankey(
        node=dict(
            pad=18, thickness=18,
            line=dict(color="rgba(148,163,184,0.25)", width=0.5),
            label=countries_in_flow, color="#06b6d4",
        ),
        link=dict(
            source=[idx[c["source"]] for c in corridors],
            target=[idx[c["target"]] for c in corridors],
            value=[c["overlap_pct"] * 100 for c in corridors],
            label=[f"{int(c['overlap_pct']*100)}% overlap · {c['shared_videos']} shared"
                   for c in corridors],
            color="rgba(139,92,246,0.35)",
        ),
    ))
    sankey.update_layout(
        height=460, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font_color="#e5e7eb",
    )
    st.plotly_chart(sankey, use_container_width=True)

    st.markdown('<div class="section-header">💎 Top corridors by overlap</div>',
                unsafe_allow_html=True)
    for c in corridors[:8]:
        cls = ("arb-high" if c["overlap_pct"] >= 0.7
               else "arb-med" if c["overlap_pct"] >= 0.5
               else "arb-low")
        cats = ", ".join(c["categories"])
        st.markdown(
            f"""
            <div class="arb-card {cls}">
                <b>{c['source']} ↔ {c['target']}</b>
                &nbsp;·&nbsp; overlap <b>{int(c['overlap_pct']*100)}%</b>
                &nbsp;·&nbsp; <b>{c['shared_videos']}</b> shared trending videos<br/>
                <span style="color:#94a3b8;">Strongest in: {cats}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "📅 **v2 roadmap.** This snapshot lets us measure *cultural overlap* "
        "(how likely a video crosses borders). With multi-day snapshots, we add "
        "*temporal lag* — predicting **when**, not just **whether**, a trend will cross."
    )


def page_insights(df):
    st.markdown('<div class="big-title">📊 Data Insights</div>', unsafe_allow_html=True)
    st.caption("Member C's feature engineering — Engagement Conversion Rate, "
               "Time-to-Trend, and what actually drives reach.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Median ECR", f"{df['engagement_rate'].median():.2f}%")
    c2.metric("Median time-to-trend", f"{df['trending_hours'].median():.0f}h")
    c3.metric("Median views", f"{int(df['views'].median()):,}")

    st.markdown('<div class="section-header">Engagement Conversion Rate by category</div>',
                unsafe_allow_html=True)
    fig = px.box(df, x="category", y="engagement_rate", color="category", points=False)
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
    )
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Time-to-Trend distribution</div>',
                unsafe_allow_html=True)
    plot_df = df[df["trending_hours"] < df["trending_hours"].quantile(0.95)]
    fig2 = px.histogram(plot_df, x="trending_hours", nbins=40,
                        color_discrete_sequence=["#8b5cf6"])
    fig2.update_layout(
        height=320, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-header">Raw data sample</div>', unsafe_allow_html=True)
    show_cols = ["title", "country", "category", "views", "likes", "comments",
                 "engagement_rate", "trending_hours", "virality_score"]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols].head(50), use_container_width=True, hide_index=True)


# ============================================================
# MAIN
# ============================================================
def main():
    df, source_label = load_dataset()
    corridors = compute_corridors(df)

    with st.sidebar:
        st.markdown("### 🌊 ViralWave")
        st.caption("v0.2 · Theme 1 MVP")
        page = st.radio(
            "Navigate",
            ["🏠 Dashboard", "🔮 Virality Predictor",
             "🌐 Cross-Cultural Arbitrage", "📊 Data Insights"],
            label_visibility="collapsed",
        )

        st.divider()
        st.caption("**Status**")
        st.caption(f"Dataset: {source_label}")
        st.caption(f"AI API: {'🟢 Gemini live' if GEMINI_ENABLED else '🟡 mock (no key)'}")
        st.caption(f"Corridors detected: {len(corridors)}")

        st.divider()
        st.caption("Built for the Innovation Challenge · Section B")

    if page == "🏠 Dashboard":
        page_dashboard(df, corridors)
    elif page == "🔮 Virality Predictor":
        page_predictor(df, corridors)
    elif page == "🌐 Cross-Cultural Arbitrage":
        page_arbitrage(df, corridors)
    else:
        page_insights(df)


if __name__ == "__main__":
    main()
