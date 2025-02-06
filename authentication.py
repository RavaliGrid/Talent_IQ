import os
import json
import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from datetime import datetime
# - Firebase Setup -
FIREBASE_CREDENTIALS_PATH = "talent-iq-firebase.json"
if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
    raise FileNotFoundError(f"Firebase credentials file not found: {FIREBASE_CREDENTIALS_PATH}")
cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()
# - OAuth 2.0 Setup -
CLIENT_SECRET_PATH = "client_secret.json"
if not os.path.exists(CLIENT_SECRET_PATH):
    raise FileNotFoundError(f"OAuth credentials file not found: {CLIENT_SECRET_PATH}")
# Load allowed emails from JSON file
def load_allowed_emails():
    try:
        with open("Access.json", "r") as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        st.error("Allowed emails file not found.")
        return {"admins": [], "users": []}
    except json.JSONDecodeError:
        st.error("Invalid JSON format in allowed emails file.")
        return {"admins": [], "users": []}
ALLOWED_EMAILS = load_allowed_emails()
def get_flow():
    return Flow.from_client_secrets_file(
        CLIENT_SECRET_PATH,
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri="http://localhost:8501"
    )
# - Authentication -
def authenticate():
    # Check if the user is already authenticated
    if "authenticated" in st.session_state and st.session_state.authenticated:
        return True, st.session_state.user_info
    query_params = st.query_params
    if "code" not in query_params:
        # Show the welcome page only if the user is not authenticated
        if "authenticated" not in st.session_state or not st.session_state.authenticated:
            st.markdown(
                """
                <div style="text-align: center;">
                    <h1>Welcome to TalentIQ</h1>
                    <p>Please sign in to your account to start using the applications</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            flow = get_flow()
            auth_url, _ = flow.authorization_url(prompt="consent")
            st.markdown(
                """
                <div style="display: flex; justify-content: center; align-items: center; height: 100px;">
                    <a href='{auth_url}' style='text-decoration: none;'>
                        <button style='background-color: #4285F4; color: white; border: none; padding: 10px 20px; border-radius: 5px; font-size: 16px; cursor: pointer;'>
                            Sign in with Google
                        </button>
                    </a>
                </div>
                """.format(auth_url=auth_url),
                unsafe_allow_html=True
            )
        return False, None
    try:
        code = query_params["code"]
        flow = get_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        id_info = id_token.verify_oauth2_token(credentials.id_token, Request())
        # Check if the email is allowed
        user_email = id_info["email"]
        if user_email not in ALLOWED_EMAILS["admins"] + ALLOWED_EMAILS["users"]:
            st.error("You do not have access to this application.")
            return False, None
        # Assign role based on email
        if user_email in ALLOWED_EMAILS["admins"]:
            role = "admin"
        else:
            role = "user"
        st.success(f"Logged in as: {id_info['name']} ({id_info['email']})")
        user_ref = db.collection("users").document(id_info['email'])
        user_doc = user_ref.get()
        if not user_doc.exists:
            user_ref.set({
                "name": id_info['name'],
                "email": id_info['email'],
                "profile_picture": id_info.get('picture', ''),
                "role": role,  # Assign role here
                "total_resumes_screened": 0,
                "usage_count": 0
            })
        user_data = user_ref.get().to_dict()
        st.session_state.authenticated = True
        st.session_state.user_info = user_data
        st.session_state.role = role  # Store role in session state
        # Clear the query parameters after successful authentication
        st.query_params.clear()
        st.rerun()
        return True, user_data
    except Exception as e:
        st.error(f"Authentication failed: {e}")
        return False, None
# Function to log usage
def log_usage(email, num_resumes):
    usage_ref = db.collection("usage_logs").document()
    usage_ref.set({
        "user_email": email,
        "num_resumes": num_resumes,
        "timestamp": datetime.now()
    })
    user_ref = db.collection("users").document(email)
    user_ref.update({
        "total_resumes_screened": firestore.Increment(num_resumes),
        "usage_count": firestore.Increment(1)
    })
# Sign-out functionality
def sign_out():
    st.session_state.authenticated = False
    st.session_state.user_info = None
    st.session_state.role = None
    st.session_state.token = None
    st.session_state.code = None
    st.query_params.clear()
    st.rerun()