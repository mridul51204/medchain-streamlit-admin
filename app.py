import os
import json
import time
import pandas as pd
import requests
import streamlit as st

# ----------------------------
# Config
# ----------------------------
API_BASE_URL = st.secrets.get("API_BASE_URL", os.environ.get("API_BASE_URL", "https://medchain-mock-api.onrender.com"))
st.set_page_config(page_title="MedChain Admin", page_icon="🩺", layout="wide")

# ----------------------------
# Hospital-styled CSS (teal/green, soft cards)
# ----------------------------
st.markdown("""
<style>
/* Hide default chrome */
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1rem; padding-bottom: 2rem;}

/* Palette */
:root{
  --primary:#0ea5a8;   /* teal */
  --accent:#22c55e;    /* green */
  --bg-soft:#f6fffb;   /* very light mint */
  --text:#0f172a;      /* slate-900 */
  --muted:#64748b;     /* slate-500 */
  --card-border:#e2e8f0;
}

/* Page bg */
body {background: var(--bg-soft);}

/* Cards */
.card {
  background: #ffffff;
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 2px 14px rgba(14,165,168,0.08);
}

/* KPIs */
.kpi-title {font-size:13px;color:var(--muted);margin-bottom:6px;}
.kpi-number {font-size:28px;font-weight:800;color:var(--text);}

/* Buttons */
.stButton > button {
  border-radius: 10px !important;
  padding: 0.5rem 0.9rem;
  border: 1px solid var(--card-border);
}
.stButton > button[kind="primary"]{
  background: var(--primary);
  color: #fff;
  border: none;
}
.stButton > button:hover {filter: brightness(0.98);}

/* Tabs accent */
.stTabs [data-baseweb="tab-list"] {gap: 8px;}
.stTabs [data-baseweb="tab"] {
  background: #fff;
  border: 1px solid var(--card-border);
  border-radius: 10px;
  padding: 10px 14px;
}
.stTabs [aria-selected="true"]{
  border: 1px solid var(--primary) !important;
  box-shadow: 0 0 0 2px rgba(14,165,168,0.15) inset;
}

/* Data editor tweaks */
[data-testid="stTable"] table, [data-testid="stDataFrame"] table{
  border-radius: 12px; overflow:hidden;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# API helpers
# ----------------------------
def api_ok():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=8)
        r.raise_for_status()
        return True
    except Exception:
        return False

def api_list():
    r = requests.get(f"{API_BASE_URL}/records", timeout=15)
    r.raise_for_status()
    data = r.json()
    return pd.DataFrame(data if isinstance(data, list) else [])

def api_create(obj: dict):
    r = requests.post(f"{API_BASE_URL}/records", json=obj, timeout=15)
    r.raise_for_status()
    return r.json()

def api_update(rec_id: str, obj: dict):
    r = requests.put(f"{API_BASE_URL}/records/{rec_id}", json=obj, timeout=15)
    r.raise_for_status()
    return r.json()

def api_delete(rec_id: str):
    r = requests.delete(f"{API_BASE_URL}/records/{rec_id}", timeout=15)
    r.raise_for_status()
    return True

# ----------------------------
# Header
# ----------------------------
h1c, statusc = st.columns([4,1])
with h1c:
    st.markdown("<h2 style='margin:0'>🩺 MedChain Admin</h2>", unsafe_allow_html=True)
    st.caption(API_BASE_URL)
with statusc:
    st.success("API online ✅") if api_ok() else st.error("API unreachable ⚠️")

# ----------------------------
# Load data
# ----------------------------
@st.cache_data(ttl=15)
def load_df_cache(_ts):
    df0 = api_list()
    if "createdAt" in df0.columns:
        df0["createdAt"] = pd.to_datetime(df0["createdAt"], unit="ms", errors="coerce")
    return df0

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = time.time()

df = load_df_cache(st.session_state.refresh_key)

# ----------------------------
# KPIs (cards)
# ----------------------------
k1,k2,k3 = st.columns(3)
with k1:
    st.markdown(f'<div class="card"><div class="kpi-title">Total Records</div><div class="kpi-number">{len(df)}</div></div>', unsafe_allow_html=True)
with k2:
    today = pd.Timestamp.now().normalize()
    new_today = int(df["createdAt"].dt.normalize().eq(today).sum()) if ("createdAt" in df.columns and not df.empty) else 0
    st.markdown(f'<div class="card"><div class="kpi-title">New Today</div><div class="kpi-number">{new_today}</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown('<div class="card"><div class="kpi-title">System</div><div class="kpi-number">Healthy</div></div>', unsafe_allow_html=True)

st.write("")

# ----------------------------
# HOME: Records table (search + inline)
# ----------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
c_top = st.columns([3,1,1,1])
with c_top[0]:
    q = st.text_input("Search (any field)", placeholder="name, note, city, ...")
with c_top[1]:
    if st.button("Refresh"):
        st.session_state.refresh_key = time.time()
        st.cache_data.clear()  # clear cached table
with c_top[2]:
    show_raw = st.toggle("Show raw JSON", value=False)
with c_top[3]:
    st.caption("")  # spacer

view = df.copy()
if q:
    mask = view.astype(str).apply(lambda s: s.str.contains(q, case=False, na=False)).any(axis=1)
    view = view[mask]

# helper delete column
if not view.empty and "_delete" not in view.columns:
    view["_delete"] = False

# id/createdAt not editable
disabled_cols = []
if "id" in view.columns: disabled_cols.append("id")
if "createdAt" in view.columns: disabled_cols.append("createdAt")

edited = st.data_editor(
    view if not show_raw else df,  # toggle raw view
    use_container_width=True,
    height=460,
    disabled=disabled_cols if not show_raw else [],
    num_rows="dynamic",
    key="home_editor",
)
col_save, col_del, _ = st.columns([1,1,6])
with col_save:
    if st.button("Save edits", type="primary"):
        try:
            base = (view if not show_raw else df).set_index("id") if "id" in view.columns else (view if not show_raw else df)
            new = edited.set_index("id") if "id" in edited.columns else edited
            updates = 0
            if "id" in (view if not show_raw else df).columns:
                common = list(set(base.index).intersection(set(new.index)))
                for rid in common:
                    before = base.loc[rid].to_dict()
                    after = new.loc[rid].to_dict()
                    if before != after:
                        after.pop("_delete", None)
                        if "createdAt" in after: after.pop("createdAt", None)
                        api_update(str(rid), after)
                        updates += 1
            st.success(f"Saved {updates} update(s).")
        except Exception as e:
            st.error(f"Update failed: {e}")

with col_del:
    if st.button("Delete selected"):
        try:
            cnt = 0
            if "_delete" in edited.columns and "id" in edited.columns:
                for rid in edited[edited["_delete"] == True]["id"].astype(str).tolist():
                    api_delete(rid)
                    cnt += 1
            st.success(f"Deleted {cnt} record(s).")
        except Exception as e:
            st.error(f"Delete failed: {e}")

st.markdown('</div>', unsafe_allow_html=True)

st.write("")

# ----------------------------
# ACTION TABS (Add / Upload)
# ----------------------------
tab_add, tab_upload = st.tabs(["➕ Add Record", "📥 Upload CSV"])

# ----- Add -----
with tab_add:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name")
        note = st.text_area("Note")
    with c2:
        st.caption("Additional fields (optional)")
        k1 = st.text_input("Field 1 key", placeholder="age")
        v1 = st.text_input("Field 1 value", placeholder="32")
        k2 = st.text_input("Field 2 key", placeholder="city")
        v2 = st.text_input("Field 2 value", placeholder="Vellore")
    if st.button("Add Record", type="primary"):
        payload = {}
        if name.strip(): payload["name"] = name.strip()
        if note.strip(): payload["note"] = note.strip()
        if k1.strip(): payload[k1.strip()] = v1
        if k2.strip(): payload[k2.strip()] = v2
        try:
            api_create(payload if payload else {})
            st.success("Record added.")
        except Exception as e:
            st.error(f"Failed to add: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ----- Upload CSV -----
with tab_upload:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    up = st.file_uploader("Choose CSV", type=["csv"])
    if up is not None:
        try:
            csv_df = pd.read_csv(up)
            st.dataframe(csv_df, use_container_width=True, height=380)
            if st.button("Create records from CSV"):
                created = 0
                for _, row in csv_df.iterrows():
                    d = {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    try:
                        api_create(d)
                        created += 1
                    except Exception:
                        pass
                st.success(f"Created {created} record(s).")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
    st.markdown('</div>', unsafe_allow_html=True)
