import streamlit as st
import requests

st.title("User Policy Generator (MCP)")

query_text = st.text_area("Enter policy request", "")

# MCP_CLIENT_API = "http://mcp-client:8000/generate_policy"
MCP_CLIENT_API = "http://localhost:8000/generate_policy"

if st.button("Fetch User Policy via MCP"):
    if query_text:
        st.info("Sending request via MCP...")
        try:
            response = requests.post(
                MCP_CLIENT_API,
                json={"query": query_text},
                timeout=120
            )
            if response.status_code == 200:
                st.success("Policy fetched successfully!")

                summary = response.json().get("summary", "No summary returned from server.")

                # ✅ 화면에 summary만 표시
                st.subheader("Policy Summary")
                st.write(summary)
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Request failed: {str(e)}")
