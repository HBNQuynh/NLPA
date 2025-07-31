import imaplib

# Load environment variables from .env
# from dotenv import load_dotenv
# load_dotenv()

# Streamlit for UI
import streamlit as st
from web.sidebar import show_sidebar
from usermailbox import MailBox
import logging
import socket
from prometheus_client import start_http_server
from gemini_processor import my_registry

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
show_sidebar()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "_prometheus_server_started" not in st.session_state or st.session_state["_prometheus_server_started"] == False:
    start_http_server(8000, registry=my_registry)
    logging.info("🚀 Prometheus metrics server đang chạy tại http://localhost:8000")
    st.session_state["_prometheus_server_started"] = True

# Just can be used for the first time or log out
if "logged_in" in st.session_state and st.session_state["logged_in"]:
    st.warning("You have already logged in!")
    st.switch_page("pages/dashboard.py")
    
st.write("# Welcome to Email Classifier! 👋")

email_id = st.text_input("Enter your Email ID (Gmail) which you want to monitor", placeholder="example@gmail.com")
app_password = st.text_input("Enter your App Password (Gmail) to access the emails through IMAP", placeholder="yourpassword", type="password")


login_button = st.button("Login")

login_with_google = st.button("Login with google")

if login_button:
    # Khởi động Prometheus (nếu cần)
    if "mail_box" not in st.session_state:
        st.session_state.mail_box = MailBox(email_id, app_password, False)
    else:
        st.session_state.mail_box.authenticate(email_id, app_password, False)
    st.session_state["logged_in"] = st.session_state.mail_box.login_successful
    print(st.session_state["logged_in"])
    if st.session_state["logged_in"]:
        st.switch_page("pages/dashboard.py")
        
if login_with_google:
    # Khởi động Prometheus (nếu cần)
    if "mail_box" not in st.session_state:
        st.session_state.mail_box = MailBox(email_id, app_password, True)
    else:
        st.session_state.mail_box.authenticate(email_id, app_password, True)
    
    st.session_state["logged_in"] = st.session_state.mail_box.login_successful
    print(st.session_state["logged_in"])
    if st.session_state["logged_in"]:
        st.switch_page("pages/dashboard.py")