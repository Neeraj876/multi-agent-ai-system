import json
import os

import boto3
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "")

st.set_page_config(page_title="Multi-Agent Research Assistant", layout="wide")

st.title("Multi-Agent Research Assistant")
st.caption(
    "An agentic LangGraph workflow that searches the web, summarizes evidence, "
    "checks confidence, and generates a structured research report."
)

with st.sidebar:
    st.header("Usage Limits")
    st.write("This app is rate-limited to control API costs.")

query = st.text_area(
    "Research question",
    value="What are the benefits of using AWS Cloud Services?",
    height=120,
)

col_a, col_b, col_c = st.columns(3)
with col_a:
    confidence_threshold = st.slider(
        "Confidence threshold",
        0.5,
        0.9,
        0.8,
        0.05,
        help="Minimum fact-check confidence required before the workflow accepts the result.",
    )
with col_b:
    max_retries = st.number_input(
        "Max retries",
        min_value=0,
        max_value=1,
        value=1,
        step=1,
        help="How many times the workflow can search again if confidence is too low.",
    )
with col_c:
    add_max_results = st.number_input(
        "Extra results per retry",
        min_value=1,
        max_value=3,
        value=2,
        step=1,
        help="How many additional search results are added on each retry.",
    )

submitted = st.button("Generate report", type="primary", use_container_width=True)

if submitted:
    if not LAMBDA_FUNCTION_NAME:
        st.error("LAMBDA_FUNCTION_NAME is not configured on the Streamlit server.")
        st.stop()
    if not query.strip():
        st.error("Enter a research question.")
        st.stop()

    payload = {
        "query": query.strip(),
        "confidence_threshold": confidence_threshold,
        "max_retries": int(max_retries),
        "add_max_results": int(add_max_results),
    }

    with st.status("Running the research workflow...", expanded=True) as status:
        st.write("Invoking the Lambda function.")
        try:
            client_kwargs = {"region_name": AWS_REGION}
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                client_kwargs.update(
                    {
                        "aws_access_key_id": AWS_ACCESS_KEY_ID,
                        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
                    }
                )
            lambda_client = boto3.client("lambda", **client_kwargs)
            response = lambda_client.invoke(
                FunctionName=LAMBDA_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )
        except Exception as exc:
            status.update(label="Lambda invocation failed.", state="error")
            st.error(str(exc))
            st.stop()

        st.write("Parsing the response.")
        data = json.loads(response["Payload"].read().decode("utf-8"))
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
