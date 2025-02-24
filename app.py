import streamlit as st
import pandas as pd
import authentication
from dotenv import load_dotenv
import openai
import os
import re
from resume_analysis import resume_analysis_dashboard

# Set page config
st.set_page_config(page_title="TalentIQ", layout="wide")

# Load OpenAI API Key
load_dotenv()
api_key = os.getenv("API_KEY")
if api_key:
    openai.api_key = api_key
else:
    st.error("API Key is missing. Please check your .env file.")
    st.stop()

# -------------------- Authentication --------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_info = None
    st.session_state.role = None
if not st.session_state.authenticated:
    st.session_state.authenticated, st.session_state.user_info = authentication.authenticate()
    if not st.session_state.authenticated:
        st.stop()
if st.session_state.authenticated:
    if st.button("Sign Out"):
        authentication.sign_out()
# -------------------- Dashboard --------------------
if st.session_state.authenticated:
    if st.session_state.role == "user":
        st.markdown(f"<h1 style='text-align: center;'>TalentIQ - User Dashboard</h1>", unsafe_allow_html=True)
        st.write(f"Welcome, {st.session_state.user_info['name']} ({st.session_state.user_info['email']})!")
        resume_analysis_dashboard()
    elif st.session_state.role == "admin":
        st.markdown(f"<h1 style='text-align: center;'>TalentIQ - Admin Dashboard</h1>", unsafe_allow_html=True)
        st.write(f"Welcome, {st.session_state.user_info['name']} ({st.session_state.user_info['email']})!")
        admin_option = st.sidebar.radio("Admin Options", ["Users & Usage Analytics", "Resume Analysis"])
        if admin_option == "Users & Usage Analytics":
            st.subheader("Users & Usage Analytics")
            users_ref = authentication.db.collection("users")
            users = users_ref.stream()
            users_data = [user.to_dict() for user in users]
            usage_ref = authentication.db.collection("usage_logs")
            usage_logs = usage_ref.stream()
            usage_data = [log.to_dict() for log in usage_logs]
            if users_data and usage_data:
                df_users = pd.DataFrame(users_data)
                df_usage = pd.DataFrame(usage_data)
                df_combined = pd.merge(df_users, df_usage, left_on="email", right_on="user_email", how="left")
                df_combined = df_combined[["email", "role", "usage_count", "num_resumes", "timestamp"]]
                df_combined.columns = ["Email ID", "Role", "Usage Count", "Num Resumes Screened", "Timestamp"]
                st.dataframe(df_combined)
            st.write("### Summary Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Resumes Screened", df_usage["num_resumes"].sum())
            with col2:
                st.metric("Unique TAs Using the App", df_usage["user_email"].nunique())
        elif admin_option == "Resume Analysis":
            resume_analysis_dashboard()