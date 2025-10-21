import streamlit as st
import requests

st.title("User Policy Generator (MCP)")

user_id = st.text_input("User ID", "E12345")
query_text = st.text_area("Enter policy request", "")

MCP_CLIENT_API = "http://mcp-client:8000/generate_policy"

if st.button("Fetch User Policy via MCP"):
    if query_text:
        st.info("Sending request via MCP...")
        try:
            response = requests.post(
                MCP_CLIENT_API,
                json={"query": query_text, "emp_id": user_id},
                timeout=10
            )
            if response.status_code == 200:
                st.success("Policy fetched successfully!")
                st.json(response.json())
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Request failed: {str(e)}")
