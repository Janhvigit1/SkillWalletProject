"""Multimodal Construction Intelligence Platform - Skill Wallet Capstone Project 1.
Run:  streamlit run app.py
"""
import io
import json
import re
import urllib.parse

import streamlit as st
from PIL import Image

try:
    from google import genai
    from google.genai import types
except ImportError:  # app still runs in demo mode
    genai = None
    types = None

st.set_page_config(page_title="Construction Intelligence Platform", page_icon="🏗️", layout="wide")

# ----------------------------------------------------------------- styling
st.markdown(
    """
<style>
.block-container{padding-top:1.5rem}
.hero{background:linear-gradient(120deg,#0f2027,#203a43,#2c5364);color:#fff;padding:1.2rem 1.5rem;border-radius:14px;margin-bottom:1rem}
.hero h1{margin:0;font-size:1.7rem}.hero p{margin:.2rem 0 0;opacity:.85}
.card{background:var(--secondary-background-color);border-radius:12px;padding:1rem;text-align:center;border:1px solid rgba(128,128,128,.25)}
.card .v{font-size:1.7rem;font-weight:700}.card .l{font-size:.8rem;opacity:.7;text-transform:uppercase;letter-spacing:.05em}
.pill{display:inline-block;padding:.2rem .75rem;border-radius:999px;font-weight:600;font-size:.8rem;color:#fff}
.Low,.COMPLIANT,.Routine{background:#2e9e5b}.Medium,.PARTIAL,.Monitor{background:#e0a100}
.High,.Soon{background:#e8590c}.Critical,.NON-COMPLIANT,.Immediate{background:#d6293e}
.alert{border-left:5px solid #e8590c;padding:.7rem 1rem;border-radius:8px;background:rgba(232,89,12,.1);margin:.4rem 0}
</style>
<div class="hero"><h1>🏗️ Multimodal Construction Intelligence Platform</h1>
<p>PPE audits · crack diagnostics · cost &amp; valuation in INR · weather-aware site protocols</p></div>
""",
    unsafe_allow_html=True,
)


def card(label, value):
    st.markdown(f'<div class="card"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


def pill(text):
    cls = str(text).replace(" ", "-")
    return f'<span class="pill {cls}">{text}</span>'


def fmt_inr(v):
    if v >= 1e7:
        return f"₹{v / 1e7:,.2f} Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:,.2f} Lakh"
    return f"₹{v:,.0f}"


# ----------------------------------------------------------------- Gemini helpers
def get_client():
    key = st.session_state.get("api_key", "").strip()
    if key and genai:
        return genai.Client(api_key=key)
    return None


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def analyze_image(image, prompt, demo_data):
    """Send image + prompt to Gemini expecting JSON; fall back to demo data on any failure."""
    client = get_client()
    if client is None:
        return demo_data, True
    try:
        resp = client.models.generate_content(
            model=st.session_state.model,
            contents=[prompt, image],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        return parse_json(resp.text), False
    except Exception as e:  # network, quota, bad JSON, invalid key...
        st.warning(f"Gemini call failed ({type(e).__name__}: {str(e)[:150]}). Showing demonstration output instead.")
        return demo_data, True


def load_image(file):
    img = Image.open(file).convert("RGB")
    img.thumbnail((1600, 1600))
    return img


# ----------------------------------------------------------------- prompts & demo data
PPE_PROMPT = """You are a certified construction safety auditor (OSHA 1926 and IS 456 / IS 7969 site practice).
Analyze the site photo for worker PPE compliance (helmets, high-visibility vests, steel-toe boots, safety harnesses)
and visible site hazards. Respond ONLY with JSON in exactly this schema:
{"safety_score": int 0-100, "overall_status": "COMPLIANT"|"PARTIAL"|"NON-COMPLIANT",
 "workers_detected": int,
 "ppe_detection": {"helmet": {"detected": bool, "note": str}, "high_vis_vest": {"detected": bool, "note": str},
   "steel_toe_boots": {"detected": bool, "note": str}, "safety_harness": {"detected": bool, "note": str}},
 "hazards": [{"description": str, "severity": "Low"|"Medium"|"High"|"Critical", "remedy": str}],
 "summary": str}
If something cannot be seen, set detected=false and say so in the note."""

CRACK_PROMPT = """You are a senior structural engineer. Analyze the concrete/wall surface photo for cracks and defects.
Respond ONLY with JSON in exactly this schema:
{"defect_type": "Hairline"|"Settlement"|"Structural Shear"|"Thermal Expansion"|"Spalling",
 "severity_score": int 0-100, "estimated_width_mm": float, "pattern": str,
 "root_causes": [str], "recommended_repairs": [str],
 "urgency": "Routine"|"Monitor"|"Soon"|"Immediate", "structural_risk": str,
 "monitoring_advice": str}
Be conservative: if the image is not a concrete/masonry surface, set severity_score 0 and explain in structural_risk."""

DEMO_PPE = {
    "safety_score": 68, "overall_status": "PARTIAL", "workers_detected": 4,
    "ppe_detection": {
        "helmet": {"detected": True, "note": "3 of 4 workers wearing hard hats"},
        "high_vis_vest": {"detected": True, "note": "All visible workers wearing vests"},
        "steel_toe_boots": {"detected": False, "note": "Footwear not verifiable / sneakers suspected"},
        "safety_harness": {"detected": False, "note": "No harness while working at height"},
    },
    "hazards": [
        {"description": "Worker at edge without fall protection", "severity": "Critical", "remedy": "Install guardrails; mandate full-body harness with anchor point (OSHA 1926.501)."},
        {"description": "Unsecured scaffold planks", "severity": "High", "remedy": "Fully plank and tie-in scaffold; inspect daily by competent person."},
        {"description": "Loose rebar ends uncapped", "severity": "Medium", "remedy": "Fit mushroom caps on protruding rebar."},
        {"description": "Debris in walkway", "severity": "Low", "remedy": "Daily housekeeping and designated material stacking zones."},
    ],
    "summary": "DEMO MODE sample: partial compliance; fall protection is the priority gap.",
}
DEMO_CRACK = {
    "defect_type": "Settlement", "severity_score": 62, "estimated_width_mm": 3.5,
    "pattern": "Diagonal stair-step crack running from window corner",
    "root_causes": ["Differential foundation settlement", "Poor soil compaction", "Water seepage near footing"],
    "recommended_repairs": ["Epoxy injection for cracks 0.3-6 mm (IS 15988)", "Structural re-grouting with non-shrink grout", "Install crack gauges and re-check after 4 weeks", "Fix drainage near foundation"],
    "urgency": "Soon", "structural_risk": "Moderate; progressive movement could affect load-bearing capacity.",
    "monitoring_advice": "DEMO MODE sample. Tell-tale gauges, record width fortnightly.",
}

# ----------------------------------------------------------------- planning data
STRUCTURES = {  # build cost Rs/sqft (Tier 2 base), market value Rs/sqft (Tier 2 base), steel kg/sqft, cement bags/sqft
    "Residential House": (2000, 5500, 4.0, 0.40),
    "Apartment Block": (2300, 6500, 4.5, 0.42),
    "Commercial Office": (2900, 8500, 5.5, 0.45),
    "Industrial Warehouse": (1600, 3500, 6.0, 0.38),
}
TIERS = {"Tier 1 (Mumbai, Delhi, Bengaluru)": (1.30, 1.90), "Tier 2 (Indore, Pune, Jaipur)": (1.00, 1.00), "Tier 3 (Smaller cities)": (0.82, 0.55)}
MILESTONES = [(0, "Site prep"), (10, "Foundation"), (30, "Structure / frame"), (55, "Masonry & slabs"), (75, "MEP & finishing"), (95, "Handover")]

WEATHER = {
    "Normal": ["✅ Standard operations permitted. Hold the daily toolbox talk and verify PPE at gate."],
    "High Wind": [
        "🚫 Suspend all crane and hoist operations when sustained wind exceeds 36 km/h (20 knots) or per OEM limits.",
        "🧱 Secure loose materials, formwork panels and sheeting; lower or tie down scaffold netting.",
        "🪜 Stop work at height and on exposed edges; restrict personnel from the swing radius.",
    ],
    "Heavy Rain": [
        "⚡ Electrical hazard: de-energise temporary supply in wet zones, use RCCB-protected GFCI circuits, keep cables off the ground.",
        "🏗️ Concrete: stop pours; cover fresh concrete with tarpaulin, protect from washout and re-check slump before restart.",
        "🕳️ Excavations: inspect for collapse risk, pump out water, review shoring; keep walkways non-slip.",
    ],
    "Extreme Heat": [
        "🥤 Heat stress: mandatory water, shaded rest breaks (e.g. 10 min per hour above 38°C), and shift heavy work to early morning.",
        "🧪 Concrete curing: begin wet curing immediately, use wet burlap/curing compound, avoid pours at midday (IS 456 cl. 13.5 - protect from rapid drying).",
        "👀 Watch for heat exhaustion symptoms; buddy system for all workers.",
    ],
}


def demo_chat_reply(q):
    q = q.lower()
    rules = [
        (("curing", "cure"), "Per IS 456, keep concrete moist for at least 7 days (10 days for mineral-admixture cement, 14 in hot/dry weather)."),
        (("slump",), "Typical slump: 25-75 mm for footings, 75-100 mm for beams/slabs, 100-150 mm for pumped or congested sections."),
        (("harness", "height", "fall"), "Use full-body harnesses anchored to a 15 kN-rated point above the worker whenever working above 1.8 m (OSHA) or 2 m (IS 3696). Inspect before every shift."),
        (("crack",), "Measure crack width with a crack gauge. Hairline (<0.3 mm) is usually cosmetic; >3 mm or growing needs a structural engineer."),
        (("cement", "steel", "estimate"), "Rule of thumb for residential RCC: ~0.4 bags cement and ~4 kg steel per sq ft built-up. Use Tab 3 for a full estimate."),
        (("grade", "m20", "m25", "mix"), "M20 suits general RCC; M25+ is recommended for moderate exposure per IS 456 Table 5."),
    ]
    for keys, ans in rules:
        if any(k in q for k in keys):
            return ans + "\n\n*(Demo mode - add a Gemini API key for full answers.)*"
    return "I'm in demo mode and answer a limited set of topics (curing, slump, fall protection, cracks, material estimates, concrete grade). Add a Gemini API key in the sidebar for open-ended help."


CHAT_SYSTEM = (
    "You are an expert Indian construction site engineering assistant. Follow IS codes (IS 456, IS 800, IS 875, NBC 2016) and "
    "OSHA norms. Give concise, practical, safety-first answers. State assumptions, and recommend a licensed structural engineer "
    "for load-bearing decisions."
)

# ----------------------------------------------------------------- sidebar
ss = st.session_state
ss.setdefault("api_key", "")
ss.setdefault("model", "gemini-2.5-flash")
ss.setdefault("chat", [])

with st.sidebar:
    st.header("⚙️ Configuration")
    ss.api_key = st.text_input("Google Gemini API key", value=ss.api_key, type="password", help="Never stored; kept in session memory only.")
    ss.model = st.text_input("Gemini model", value=ss.model, help="Any multimodal Gemini model name.")
    if get_client():
        st.success("Live mode: Gemini connected")
    else:
        st.info("Demonstration mode: sample outputs are used" + ("" if genai else " (google-genai not installed)"))
    st.divider()
    st.subheader("🧭 Features")
    st.markdown("- 🦺 Site Safety & PPE Audit\n- 🧱 Crack Diagnostics\n- 💰 Planning & Valuation (INR)\n- 🌦️ Weather Advisory & Chatbot")
    st.subheader("🏛️ Architecture")
    st.caption("Streamlit UI → Pillow preprocessing → Gemini multimodal prompt → JSON data contract → validated rendering. "
               "Cost engine and weather protocols are pure Python; no database required.")

tab1, tab2, tab3, tab4 = st.tabs(["🦺 Safety & PPE Audit", "🧱 Crack Diagnostics", "💰 Planning & Valuation", "🌦️ Site Assistant"])

# ----------------------------------------------------------------- tab 1
with tab1:
    st.subheader("Site Safety & PPE Audit")
    f = st.file_uploader("Upload a construction site photo", type=["jpg", "jpeg", "png"], key="ppe")
    if f:
        img = load_image(f)
        c1, c2 = st.columns([1, 1.3])
        c1.image(img, use_container_width=True)
        if c2.button("Run PPE audit", type="primary"):
            with st.spinner("Analyzing site photo..."):
                ss.ppe, ss.ppe_demo = analyze_image(img, PPE_PROMPT, DEMO_PPE)
    if ss.get("ppe"):
        r = ss.ppe
        try:
            if ss.get("ppe_demo"):
                st.caption("⚠️ Demonstration output")
            m1, m2, m3 = st.columns(3)
            with m1: card("Safety score", f'{int(r["safety_score"])}/100')
            with m2: card("Workers detected", r.get("workers_detected", "-"))
            with m3: st.markdown(f'<div class="card"><div class="l">Overall status</div><div style="margin-top:.6rem">{pill(r["overall_status"])}</div></div>', unsafe_allow_html=True)
            st.progress(max(0, min(100, int(r["safety_score"]))) / 100)
            st.markdown("#### PPE checklist")
            cols = st.columns(4)
            for col, (k, v) in zip(cols, r["ppe_detection"].items()):
                col.markdown(f'**{"✅" if v["detected"] else "❌"} {k.replace("_", " ").title()}**')
                col.caption(v.get("note", ""))
            st.markdown("#### Identified hazards")
            for h in r.get("hazards", []):
                st.markdown(f'{pill(h["severity"])} **{h["description"]}**<br><small>🔧 {h["remedy"]}</small>', unsafe_allow_html=True)
                st.write("")
            st.info(r.get("summary", ""))
            st.download_button("⬇️ Download JSON report", json.dumps(r, indent=2), "ppe_safety_report.json", "application/json")
        except (KeyError, TypeError, ValueError) as e:
            st.error(f"Model returned an unexpected structure ({e}). Please retry.")
            st.json(r)

# ----------------------------------------------------------------- tab 2
with tab2:
    st.subheader("Crack Diagnostics & Structural Integrity")
    f = st.file_uploader("Upload a concrete / wall surface photo", type=["jpg", "jpeg", "png"], key="crack")
    if f:
        img = load_image(f)
        c1, c2 = st.columns([1, 1.3])
        c1.image(img, use_container_width=True)
        if c2.button("Diagnose defect", type="primary"):
            with st.spinner("Running structural diagnosis..."):
                ss.crack, ss.crack_demo = analyze_image(img, CRACK_PROMPT, DEMO_CRACK)
    if ss.get("crack"):
        r = ss.crack
        try:
            if ss.get("crack_demo"):
                st.caption("⚠️ Demonstration output")
            m1, m2, m3, m4 = st.columns(4)
            with m1: card("Defect type", r["defect_type"])
            with m2: card("Severity score", f'{int(r["severity_score"])}/100')
            with m3: card("Est. width", f'{float(r["estimated_width_mm"]):.1f} mm')
            with m4: st.markdown(f'<div class="card"><div class="l">Urgency</div><div style="margin-top:.6rem">{pill(r["urgency"])}</div></div>', unsafe_allow_html=True)
            st.write("")
            a, b = st.columns(2)
            a.markdown("#### Root causes\n" + "\n".join(f"- {x}" for x in r["root_causes"]))
            b.markdown("#### Recommended repairs\n" + "\n".join(f"- {x}" for x in r["recommended_repairs"]))
            st.markdown(f"**Pattern:** {r.get('pattern', '-')}  \n**Structural risk:** {r.get('structural_risk', '-')}  \n**Monitoring:** {r.get('monitoring_advice', '-')}")
            st.download_button("⬇️ Download JSON report", json.dumps(r, indent=2), "crack_report.json", "application/json")
            st.caption("AI screening only. A licensed structural engineer must confirm before any repair.")
        except (KeyError, TypeError, ValueError) as e:
            st.error(f"Model returned an unexpected structure ({e}). Please retry.")
            st.json(r)

# ----------------------------------------------------------------- tab 3
with tab3:
    st.subheader("Project Planning & Real Estate Valuation")
    c1, c2 = st.columns(2)
    stype = c1.selectbox("Structure type", list(STRUCTURES))
    tier = c2.selectbox("Location tier", list(TIERS))
    sqft = c1.number_input("Built-up area (sq ft)", 200, 500000, 1500, 100)
    pct = c2.slider("Completion %", 0, 100, 35)

    build_rate, mkt_rate, steel_kg, cement_bags = STRUCTURES[stype]
    cost_mult, val_mult = TIERS[tier]
    budget = sqft * build_rate * cost_mult
    capex = budget * pct / 100
    full_value = sqft * mkt_rate * val_mult
    current_value = full_value * (pct / 100) * 0.9  # 10% under-construction discount

    m = st.columns(4)
    with m[0]: card("Total budget", fmt_inr(budget))
    with m[1]: card("CapEx incurred", fmt_inr(capex))
    with m[2]: card("Current asset value", fmt_inr(current_value))
    with m[3]: card("Value on completion", fmt_inr(full_value))
    n = st.columns(3)
    with n[0]: card("Steel required", f"{sqft * steel_kg / 1000:,.1f} tonnes")
    with n[1]: card("Cement required", f"{sqft * cement_bags:,.0f} bags")
    with n[2]: card("Steel / cement used", f"{sqft * steel_kg * pct / 100000:,.1f} t / {sqft * cement_bags * pct / 100:,.0f} bags")
    st.markdown("#### Milestone progress")
    st.progress(pct / 100)
    current = max(name for p, name in MILESTONES if pct >= p) if pct else MILESTONES[0][1]
    st.write(" → ".join(f"**{n_}**" if n_ == current else n_ for _, n_ in MILESTONES))
    st.caption("Indicative estimates based on average Indian market rates; verify with local quotations and a registered valuer.")

    st.markdown("#### 🎨 Conceptual 3D architectural rendering")
    style = st.selectbox("Style", ["modern minimalist", "contemporary Indian", "glass-facade commercial", "industrial steel"])
    prompt = (f"photorealistic 3D architectural render of a {stype.lower()}, {style}, about {sqft} sq ft, "
              f"Indian city setting, golden hour, high detail")
    st.text_area("Generated prompt (editable)", prompt, key="render_prompt", height=70)
    if st.button("Generate rendering"):
        ss.render_url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(ss.render_prompt)
                         + "?width=1024&height=640&nologo=true&model=flux")
    if ss.get("render_url"):
        st.image(ss.render_url, caption="Pollinations AI (Flux) concept render", use_container_width=True)

# ----------------------------------------------------------------- tab 4
with tab4:
    st.subheader("Daily Site Assistant & Weather-Aware Advisory")
    w = st.radio("Today's weather", list(WEATHER), horizontal=True)
    for a in WEATHER[w]:
        st.markdown(f'<div class="alert">{a}</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("#### 💬 Construction engineering assistant")
    for role, text in ss.chat:
        with st.chat_message(role):
            st.markdown(text)
    if q := st.chat_input("Ask about curing, mix design, safety, estimation..."):
        ss.chat.append(("user", q))
        with st.chat_message("user"):
            st.markdown(q)
        client = get_client()
        reply = None
        if client:
            try:
                history = "\n".join(f"{'User' if r == 'user' else 'Assistant'}: {t}" for r, t in ss.chat[-12:])
                resp = client.models.generate_content(
                    model=ss.model,
                    contents=f"Current weather on site: {w}.\n\n{history}\nAssistant:",
                    config=types.GenerateContentConfig(system_instruction=CHAT_SYSTEM, temperature=0.4),
                )
                reply = resp.text
            except Exception as e:
                st.warning(f"Gemini error ({type(e).__name__}); using demo reply.")
        reply = reply or demo_chat_reply(q)
        ss.chat.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(reply)
    if ss.chat and st.button("Clear chat"):
        ss.chat = []
        st.rerun()