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
# Light styling (clean & modern)
# ----------------------------
st.markdown("""
<style>
/* Hide Streamlit default chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
/* Page padding & font */
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}

/* Card */
.card {
  background: #ffffff;
  border: 1px solid #eee;
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

/* Metric number */
.kpi-number {font-size: 28px; font-weight: 700; line-height: 1;}

/* Buttons row spacing */
.btn-row .stButton > button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# API helpers
# ----------------------------
def api_ok():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=8)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, {"error": str(e)}

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
colA, colB = st.columns([3,1])
with colA:
    st.markdown("<h2 style='margin:0'>MedChain Admin</h2>", unsafe_allow_html=True)
    st.caption(API_BASE_URL)

with colB:
    ok, _ = api_ok()
    if ok:
        st.success("API online", icon="✅")
    else:
        st.error("API unreachable", icon="⚠️")

# ----------------------------
# KPIs
# ----------------------------
def load_df():
    try:
        df = api_list()
        if "createdAt" in df.columns:
            df["createdAt"] = pd.to_datetime(df["createdAt"], unit="ms", errors="coerce")
        return df
    except Exception as e:
        st.error(f"Failed to load records: {e}")
        return pd.DataFrame()

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = time.time()

df = load_df()

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown('<div class="card"><div>Total Records</div><div class="kpi-number">{}</div></div>'.format(len(df)), unsafe_allow_html=True)
with c2:
    today = pd.Timestamp.now().normalize()
    new_today = 0
    if not df.empty and "createdAt" in df.columns:
        new_today = df["createdAt"].dt.normalize().eq(today).sum()
    st.markdown('<div class="card"><div>New Today</div><div class="kpi-number">{}</div></div>'.format(int(new_today)), unsafe_allow_html=True)
with c3:
    st.markdown('<div class="card"><div>Status</div><div class="kpi-number">Healthy</div></div>', unsafe_allow_html=True)

st.write("")

# ----------------------------
# Tabs
# ----------------------------
t1, t2, t3 = st.tabs(["➕ Add", "✏️ Edit / Delete", "📥 Upload CSV"])

# --------- TAB 1: Add ----------
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        # Keep fields super simple; no JSON parsing required.
        name = st.text_input("Name")
        note = st.text_area("Note")
    with col2:
        # Optional extra fields as free text key/value pairs
        st.caption("Additional fields (optional)")
        key1 = st.text_input("Field 1 key", placeholder="age")
        val1 = st.text_input("Field 1 value", placeholder="32")
        key2 = st.text_input("Field 2 key", placeholder="city")
        val2 = st.text_input("Field 2 value", placeholder="Vellore")
    add_clicked = st.button("Add Record", type="primary")
    if add_clicked:
        payload = {}
        # Only include fields that have values
        if name.strip(): payload["name"] = name.strip()
        if note.strip(): payload["note"] = note.strip()
        if key1.strip(): payload[key1.strip()] = val1
        if key2.strip(): payload[key2.strip()] = val2
        try:
            api_create(payload if payload else {})
            st.success("Record added.")
        except Exception as e:
            st.error(f"Failed to add: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# --------- TAB 2: Edit / Delete ----------
with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.caption("Tip: edit cells directly; tick rows to delete, then press buttons below.")
    if df.empty:
        st.info("No records yet.")
    else:
        # Add a delete checkbox column for selection
        if "_delete" not in df.columns:
            df["_delete"] = False

        # Make id/createdAt not editable
        disabled_cols = []
        if "id" in df.columns: disabled_cols.append("id")
        if "createdAt" in df.columns: disabled_cols.append("createdAt")

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            height=450,
            disabled=disabled_cols,
            num_rows="dynamic",
            key="editor",
        )

        colx, coly, colz = st.columns([1,1,6], gap="small")
        with colx:
            if st.button("Save edits", type="primary"):
                try:
                    # Find rows whose non-id fields changed
                    orig = df.set_index("id") if "id" in df.columns else df
                    new = edited_df.set_index("id") if "id" in edited_df.columns else edited_df
                    common_ids = list(set(orig.index).intersection(set(new.index)))
                    updates = 0
                    for rid in common_ids:
                        before = orig.loc[rid].to_dict()
                        after = new.loc[rid].to_dict()
                        if before != after:
                            # remove helper column and immutable fields
                            after.pop("_delete", None)
                            after.pop("createdAt", None)
                            api_update(str(rid), after)
                            updates += 1
                    st.success(f"Saved {updates} update(s).")
                except Exception as e:
                    st.error(f"Update failed: {e}")

        with coly:
            if st.button("Delete selected", type="secondary"):
                try:
                    to_del = edited_df[edited_df.get("_delete", False) == True]
                    cnt = 0
                    for rid in to_del.get("id", []):
                        api_delete(str(rid))
                        cnt += 1
                    st.success(f"Deleted {cnt} record(s).")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# --------- TAB 3: Upload CSV ----------
with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    up = st.file_uploader("Choose CSV", type=["csv"])
    if up is not None:
        try:
            csv_df = pd.read_csv(up)
            st.dataframe(csv_df, use_container_width=True, height=400)
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
