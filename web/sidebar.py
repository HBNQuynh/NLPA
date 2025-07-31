import streamlit as st

def show_sidebar():
    with st.sidebar:
        st.title("📧 Email Categorization System")
        st.markdown("## Team members:\n"
                    "1) Nguyễn Trần Trung Kiên - 21127327\n"
                    "2) Hồ Bạch Như Quỳnh - 21127412\n"
                    "3) Nguyễn Minh Thuận - 21127448\n"
                    "4) Huỳnh Lê Hải Dương - 22127081\n")

def show_sidebar_category():
    # CSS để làm các nút trong sidebar bằng nhau
    st.markdown("""
        <style>
        /* Chọn tất cả button trong .stButton */
        .stButton > button {
            width: 100% !important;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## Category")
        if st.button("All"):
            st.switch_page("pages/dashboard.py")
        if st.button("Work"):
            st.session_state["selected_category"] = "Work"
            st.switch_page("pages/categorized_mail.py")
        if st.button("Commercial"):
            st.session_state["selected_category"] = "Commercial"
            st.switch_page("pages/categorized_mail.py")
        if st.button("Fraud"):
            st.session_state["selected_category"] = "Fraud"
            st.switch_page("pages/categorized_mail.py")
        if st.button("Others"):
            st.session_state["selected_category"] = "Others"
            st.switch_page("pages/categorized_mail.py")
