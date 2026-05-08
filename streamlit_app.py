import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "")
API_GATEWAY_API_KEY = os.getenv("API_GATEWAY_API_KEY", "")

st.set_page_config(page_title="Multi-Agent Research", layout="wide")

st.title("Multi-Agent Research")
st.caption("Search, summarize, fact-check, and generate a report.")

with st.sidebar:
    st.header("Demo Limits")
    st.write("This public demo is rate-limited to control API costs.")

query = st.text_area(
    "Research question",
    value="What are the benefits of using AWS Cloud Services?",
    height=120,
)

col_a, col_b, col_c = st.columns(3)
with col_a:
    confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0, 0.8, 0.05)
with col_b:
    max_retries = st.number_input("Max retries", min_value=0, max_value=5, value=1, step=1)
with col_c:
    add_max_results = st.number_input("Extra results per retry", min_value=1, max_value=10, value=2, step=1)

submitted = st.button("Generate report", type="primary", use_container_width=True)

if submitted:
    if not API_GATEWAY_URL:
        st.error("API_GATEWAY_URL is not configured on the Streamlit server.")
        st.stop()
    if not API_GATEWAY_API_KEY:
        st.error("API_GATEWAY_API_KEY is not configured on the Streamlit server.")
        st.stop()
    if not query.strip():
        st.error("Enter a research question.")
        st.stop()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_GATEWAY_API_KEY,
    }
    payload = {
        "query": query.strip(),
        "confidence_threshold": confidence_threshold,
        "max_retries": int(max_retries),
        "add_max_results": int(add_max_results),
    }

    with st.status("Running the research workflow...", expanded=True) as status:
        st.write("Calling the API endpoint.")
        try:
            response = requests.post(API_GATEWAY_URL, headers=headers, json=payload, timeout=320)
            response.raise_for_status()
        except requests.Timeout:
            status.update(label="Request timed out.", state="error")
            st.error("The request timed out. Try a narrower query.")
            st.stop()
        except requests.HTTPError as exc:
            status.update(label="API request failed.", state="error")
            st.error(f"API returned {response.status_code}: {response.text}")
            st.stop()
        except requests.RequestException as exc:
            status.update(label="API request failed.", state="error")
            st.error(str(exc))
            st.stop()

        st.write("Parsing the response.")
        data = response.json()
        body = data.get("body", data)
        if isinstance(body, str):
            body = json.loads(body)

        status.update(label="Report ready.", state="complete")

    errors = body.get("errors", [])
    if errors:
        st.warning("The workflow returned errors.")
        for error in errors:
            st.write(f"- {error}")

    final_report = body.get("final_report", "")
    if final_report:
        st.markdown(final_report)
    else:
        st.info("No final report was returned.")
