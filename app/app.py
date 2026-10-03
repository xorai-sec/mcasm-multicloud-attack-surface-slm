
import json, collections
from pathlib import Path
import pandas as pd, streamlit as st

st.set_page_config(page_title="Multi-Cloud Attack Surface Prioritisation",
                   layout="wide", initial_sidebar_state="expanded")

DATA = Path(__file__).parent / "app_data.json"
D = json.loads(DATA.read_text())
CLS_ORDER = {"Act":0, "Attend":1, "Track*":2, "Track":3}
CLS_COLOUR = {"Act":"#D62728", "Attend":"#F58518", "Track*":"#4C78A8", "Track":"#8C8C8C"}

st.title("Multi-Cloud Attack Surface Prioritisation")
st.caption("Qwen2.5-3B fine-tuned with LoRA · findings normalised to the Unified Finding Schema")

with st.sidebar:
    st.header("Instance")
    inst = st.selectbox("Ranking set", list(D.keys()))
    rec = D[inst]
    st.divider()
    st.header("Filters")
    classes = st.multiselect("SSVC class", ["Act","Attend","Track*","Track"],
                             default=["Act","Attend","Track*","Track"])
    show_ungrounded = st.checkbox("Only unsupported explanations", value=False)
    st.divider()
    st.header("Model performance")
    st.metric("Agreement with experts", "0.848", help="Kendall's tau-b, 6 sets, 2 raters")
    st.metric("Rank stability", "0.680", help="Mean pairwise tau across shuffled input orders")
    st.metric("Grounding precision", "0.595", help="Share of explanation claims supported by input")
    st.caption("Rule-based baseline reaches 0.800 against the same experts "
               "(difference not statistically significant, p = 0.51).")

rows = []
for i, f in enumerate(rec["ranking"], 1):
    rows.append({"rank": i,
                 "class": rec["ssvc"].get(f, "Track"),
                 "finding": f,
                 "indicators": rec["indicators"].get(f, "none"),
                 "explanation": rec["why"].get(f, ""),
                 "grounded": rec["grounded"].get(f, None)})
df = pd.DataFrame(rows)
view = df[df["class"].isin(classes)]
if show_ungrounded:
    view = view[view["grounded"].notna() & (view["grounded"] < 1.0)]

c1, c2, c3, c4 = st.columns(4)
counts = collections.Counter(df["class"])
for col, cls in zip((c1,c2,c3,c4), ["Act","Attend","Track*","Track"]):
    col.metric(cls, counts.get(cls, 0))

tab1, tab2, tab3 = st.tabs(["Prioritised queue", "Explanation audit", "Export"])

with tab1:
    st.dataframe(view[["rank","class","finding","indicators"]],
                 use_container_width=True, hide_index=True,
                 column_config={"rank": st.column_config.NumberColumn(width="small"),
                                "class": st.column_config.TextColumn(width="small")})
    st.subheader("Detail")
    for _, r in view.head(10).iterrows():
        colour = CLS_COLOUR.get(r["class"], "#8C8C8C")
        with st.expander(f"#{r['rank']}  [{r['class']}]  {r['finding']}"):
            a, b = st.columns(2)
            a.markdown("**Input indicators**")
            a.code(r["indicators"], language=None)
            b.markdown("**Model assessment**")
            if r["explanation"]:
                b.info(r["explanation"])
                if r["grounded"] is not None:
                    if r["grounded"] >= 0.99: b.success(f"Fully supported by input ({r['grounded']:.2f})")
                    elif r["grounded"] >= 0.5: b.warning(f"Partly supported ({r['grounded']:.2f})")
                    else: b.error(f"Largely unsupported ({r['grounded']:.2f}) — verify manually")
            else:
                b.caption("No explanation generated for this finding.")

with tab2:
    st.markdown("Explanations are generated for the top-ranked findings only. "
                "A claim counts as supported when the indicator it references is present in the input.")
    g = df[df["grounded"].notna()]
    if len(g):
        st.bar_chart(g.set_index("finding")["grounded"])
        st.metric("Mean grounding precision", f"{g['grounded'].mean():.3f}")
        bad = g[g["grounded"] < 0.5]
        if len(bad):
            st.error(f"{len(bad)} explanation(s) largely unsupported by the input")
            st.dataframe(bad[["rank","finding","explanation","grounded"]],
                         use_container_width=True, hide_index=True)
    else:
        st.info("No gradeable explanations in this set.")

with tab3:
    st.download_button("Download ranking (CSV)", df.to_csv(index=False),
                       f"{inst}_ranking.csv", "text/csv")
    st.download_button("Download full record (JSON)", json.dumps(rec, indent=2),
                       f"{inst}.json", "application/json")
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.caption("Rankings are advisory. Rank stability is 0.68 under input reordering and "
           "40% of explanation claims were unsupported. Analyst review is required before action.")
