import os
import json
import time
import pandas as pd
import streamlit as st
import requests

# --------------------------------
# Config
# --------------------------------
API_BASE_URL = st.secrets.get("API_BASE_URL", os.environ.get("API_BASE_URL", "http://localhost:4000"))

st.set_page_config(page_title="MedChain Admin", page_icon="🩺", layout="wide")
st.title("MedChain – Records Admin")

# --------------------------------
# HTTP helpers
# --------------------------------
def api_health():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=8)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, {"error": str(e)}

def api_get_records():
    try:
        r = requests.get(f"{API_BASE_URL}/records", timeout=15)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            data = []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to fetch records: {e}")
        return pd.DataFrame(columns=["id","name","note","createdAt"])

def api_add_record(payload: dict):
    r = requests.post(f"{API_BASE_URL}/records", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def api_update_record(rec_id: str, payload: dict):
    r = requests.put(f"{API_BASE_URL}/records/{rec_id}", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def api_delete_record(rec_id: str):
    r = requests.delete(f"{API_BASE_URL}/records/{rec_id}", timeout=15)
    r.raise_for_status()
    return {"ok": True}

# --------------------------------
# Header / status
# --------------------------------
c1, c2 = st.columns([2,1])
with c1:
    st.caption(f"Backend URL: `{API_BASE_URL}`")
with c2:
    ok, info = api_health()
    st.success("API: Online") if ok else st.error("API: Unreachable")

tabs = st.tabs(["📥 Upload CSV", "➕ Add Record", "✏️ Edit / Delete"])

# --------------------------------
# TAB 1: Upload CSV → bulk create
# --------------------------------
with tabs[0]:
    st.subheader("Upload CSV")
    st.caption("CSV headers should include at least: name, note (others allowed; id/createdAt ignored).")
    up = st.file_uploader("Select CSV", type=["csv"])

    if up is not None:
        try:
            df = pd.read_csv(up)
            if "name" not in df.columns:
                st.warning("CSV must contain a 'name' column.")
            st.write("Preview:")
            st.dataframe(df, use_container_width=True)
            if st.button("Create records from this CSV"):
                created = 0
                for _, row in df.iterrows():
                    row_dict = row.drop(labels=[c for c in ["id","createdAt"] if c in row.index]).to_dict()
                    # name is required by your API
                    if not isinstance(row_dict.get("name"), str) or not row_dict.get("name"):
                        continue
                    # coerce NaNs to empty strings
                    row_dict = {k: ("" if pd.isna(v) else v) for k, v in row_dict.items()}
                    api_add_record(row_dict)
                    created += 1
                st.success(f"Created {created} records.")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

# --------------------------------
# TAB 2: Add one record
# --------------------------------
with tabs[1]:
    st.subheader("Add New Record")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name *")
        note = st.text_area("Note")
        extra_json = st.text_area("Extra fields (JSON, optional)", placeholder='{"age": 30, "city": "Vellore"}')
        submitted = st.form_submit_button("Add Record")
        if submitted:
            if not name.strip():
                st.error("Name is required.")
                st.stop()
            payload = {"name": name.strip(), "note": note or ""}
            if extra_json.strip():
                try:
                    payload.update(json.loads(extra_json))
                except Exception as e:
                    st.error(f"Invalid JSON in extra fields: {e}")
                    st.stop()
            try:
                api_add_record(payload)
                st.success("Record added.")
            except Exception as e:
                st.error(f"Failed to add record: {e}")

# --------------------------------
# TAB 3: Edit / Delete
# --------------------------------
with tabs[2]:
    st.subheader("Records")
    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0

    if st.button("Refresh"):
        st.session_state.refresh_key = time.time()

    df = api_get_records()
    if df.empty:
        st.info("No records yet.")
    else:
        # normalize
        if "id" not in df.columns:
            st.warning("Backend is not returning 'id'; editing/deleting requires it.")
        # nicer columns
        show_df = df.copy()
        if "createdAt" in show_df.columns:
            show_df["createdAt"] = pd.to_datetime(show_df["createdAt"], unit="ms", errors="coerce")
        st.dataframe(show_df, use_container_width=True, height=420)

        if "id" in df.columns:
            st.markdown("### Edit or Delete a Record")
            rec_id = st.selectbox("Choose record ID", ["-- select --"] + df["id"].astype(str).tolist())
            if rec_id != "-- select --":
                current = df[df["id"].astype(str) == rec_id].iloc[0].to_dict()
                editable_cols = [c for c in df.columns if c not in ["id","createdAt"]]

                with st.form("edit_form"):
                    editors = {}
                    for c in editable_cols:
                        v = current.get(c, "")
                        if isinstance(v, (dict, list)):
                            editors[c] = st.text_area(f"{c} (JSON)", value=json.dumps(v, ensure_ascii=False))
                        else:
                            editors[c] = st.text_input(c, value=str(v) if v is not None else "")

                    col1, col2 = st.columns(2)
                    update_btn = col1.form_submit_button("Update")
                    delete_btn = col2.form_submit_button("Delete", type="primary")

                if update_btn:
                    payload = {}
                    for c, v in editors.items():
                        vs = (v or "").strip()
                        if (vs.startswith("{") and vs.endswith("}")) or (vs.startswith("[") and vs.endswith("]")):
                            try:
                                payload[c] = json.loads(vs)
                            except Exception:
                                payload[c] = v
                        else:
                            payload[c] = v
                    try:
                        api_update_record(rec_id, payload)
                        st.success("Record updated.")
                    except Exception as e:
                        st.error(f"Update failed: {e}")

                if delete_btn:
                    try:
                        api_delete_record(rec_id)
                        st.success("Record deleted.")
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
