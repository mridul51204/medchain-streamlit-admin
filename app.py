import os
import time
import json
import pandas as pd
import requests
import streamlit as st

# ----------------------------
# Config
# ----------------------------
API_BASE_URL = st.secrets.get(
    "API_BASE_URL",
    os.environ.get("API_BASE_URL", "https://medchain-mock-api.onrender.com")
)
st.set_page_config(page_title="MedChain Admin", page_icon="🩺", layout="wide")

# ----------------------------
# Hospital theme CSS
# ----------------------------
st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
:root{
  --primary:#0ea5a8;   /* teal */
  --bg-soft:#f6fffb;   /* light mint */
  --muted:#64748b;     /* slate-500 */
  --card-border:#e2e8f0;
}
body {background: var(--bg-soft);}
.card {
  background:#fff; border:1px solid var(--card-border);
  border-radius:16px; padding:16px 18px;
  box-shadow:0 2px 14px rgba(14,165,168,0.08);
}
.kpi-title{font-size:13px;color:var(--muted);margin-bottom:6px;}
.kpi-number{font-size:28px;font-weight:800;}
.stButton > button{
  border-radius:10px!important; padding:.5rem .9rem;
  border:1px solid var(--card-border);
}
.stButton > button[kind="primary"]{background:var(--primary);color:#fff;border:none;}
.stTabs [data-baseweb="tab"]{
  background:#fff;border:1px solid var(--card-border);border-radius:10px;padding:10px 14px;
}
.stTabs [aria-selected="true"]{
  border:1px solid var(--primary)!important; box-shadow:0 0 0 2px rgba(14,165,168,.15) inset;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# API helpers
# ----------------------------
def api_ok() -> bool:
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=8)
        r.raise_for_status()
        return True
    except Exception:
        return False

def api_list() -> pd.DataFrame:
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
left, right = st.columns([4,1])
with left:
    st.markdown("<h2 style='margin:0'>🩺 MedChain Admin</h2>", unsafe_allow_html=True)
    st.caption(API_BASE_URL)
with right:
    if api_ok():
        st.success("API online ✅")
    else:
        st.error("API unreachable ⚠️")

# ----------------------------
# Data (cached)
# ----------------------------
@st.cache_data(ttl=15)
def load_df(_ts):
    df0 = api_list()
    if "createdAt" in df0.columns:
        df0["createdAt"] = pd.to_datetime(df0["createdAt"], unit="ms", errors="coerce")
    return df0

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = time.time()

df = load_df(st.session_state.refresh_key)

# ----------------------------
# KPIs
# ----------------------------
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f'<div class="card"><div class="kpi-title">Total Records</div><div class="kpi-number">{len(df)}</div></div>', unsafe_allow_html=True)
with c2:
    today = pd.Timestamp.now().normalize()
    new_today = int(df["createdAt"].dt.normalize().eq(today).sum()) if ("createdAt" in df.columns and not df.empty) else 0
    st.markdown(f'<div class="card"><div class="kpi-title">New Today</div><div class="kpi-number">{new_today}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="card"><div class="kpi-title">System</div><div class="kpi-number">Healthy</div></div>', unsafe_allow_html=True)

st.write("")

# ----------------------------
# HOME: Records table
# ----------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
top_a, top_b = st.columns([3,1])
with top_a:
    query = st.text_input("Search (any field)", placeholder="name, note, city, ...")
with top_b:
    if st.button("Refresh"):
        st.session_state.refresh_key = time.time()
        st.cache_data.clear()

view = df.copy()
if query:
    mask = view.astype(str).apply(lambda s: s.str.contains(query, case=False, na=False)).any(axis=1)
    view = view[mask]

st.dataframe(view, use_container_width=True, height=460)
st.markdown('</div>', unsafe_allow_html=True)

st.write("")

# ----------------------------
# ACTION TABS
# ----------------------------
tab_add, tab_edit, tab_upload = st.tabs(["➕ Add Record", "✏️ Update / Delete", "📥 Upload CSV"])

# ----- Add Record (age & city only as extra fields) -----
with tab_add:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name")
        note = st.text_area("Note")
    with col2:
        age = st.text_input("Age", placeholder="e.g., 32")
        city = st.text_input("City", placeholder="e.g., Vellore")
    if st.button("Add Record", type="primary"):
        payload = {}
        if name.strip(): payload["name"] = name.strip()
        if note.strip(): payload["note"] = note.strip()
        if age.strip(): payload["age"] = age.strip()
        if city.strip(): payload["city"] = city.strip()
        try:
            api_create(payload if payload else {})
            st.success("Record added.")
        except Exception as e:
            st.error(f"Failed to add: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ----- Update / Delete (separate tab) -----
with tab_edit:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if df.empty:
        st.info("No records yet.")
    else:
        ids = df["id"].astype(str).tolist() if "id" in df.columns else []
        selected = st.selectbox("Select a record ID to edit/delete", ["-- select --"] + ids)
        if selected != "-- select --":
            row = df[df["id"].astype(str) == selected].iloc[0].to_dict()

            # Simple editors for the common fields; also allow raw JSON for advanced users if needed.
            e1, e2 = st.columns(2)
            with e1:
                name_e = st.text_input("Name", value=str(row.get("name", "")))
                note_e = st.text_area("Note", value=str(row.get("note", "")))
            with e2:
                age_e = st.text_input("Age", value=str(row.get("age", "")))
                city_e = st.text_input("City", value=str(row.get("city", "")))

            col_u, col_d = st.columns(2)
            if col_u.button("Update", type="primary"):
                payload = {
                    "name": name_e,
                    "note": note_e,
                    "age": age_e,
                    "city": city_e
                }
                # Remove empty keys to avoid overwriting with blanks if you prefer:
                payload = {k:v for k,v in payload.items() if str(v).strip() != ""}
                try:
                    api_update(selected, payload)
                    st.success("Record updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

            if col_d.button("Delete", type="secondary"):
                try:
                    api_delete(selected)
                    st.success("Record deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")
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
