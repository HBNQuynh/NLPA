import streamlit as st
import time
from web.sidebar import show_sidebar_category

st.set_page_config(page_title="Categorized email", page_icon="📬", layout="wide")
show_sidebar_category()

# Kiểm tra nếu chưa đăng nhập thì quay lại trang login
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.warning("You have to log in first!")
    st.switch_page("main.py")

# ——————————————
# Guard: must be logged in
if "mail_box" not in st.session_state or not st.session_state.mail_box.login_successful:
    st.warning("🚪 Please log in first.")
    st.stop()

category = st.session_state.get("selected_category")
st.title(f"📬 {category} Email")

col = st.columns([4,1,1])
with col[0]:
    st.write(f"Logged in as: {st.session_state.mail_box.email}")
with col[1]:
    check_mail = st.button("Check mail", key="check_mail_button")
with col[2]:
    logout = st.button("Log out", key="logout_button")


# Code xử lý mail
st.session_state["mail_checked_initially"] = False

# # Gọi khi vừa vào trang (mặc định)
# if "mail_checked_initially" not in st.session_state or not st.session_state["mail_checked_initially"]:
#     with st.spinner("Checking for mail..."):
#         time.sleep(1)
#         st.session_state[f"{category} mails"] = query_emails_by_category(st.session_state["email"], category)
#     st.session_state["mail_checked_initially"] = True

if check_mail:
    with st.spinner("Checking for mail..."):
        time.sleep(1)
        st.session_state.mail_box.get_mails()
    # for mail in st.session_state.mail_box.mails:
    #     # Lưu mail vào Firestore
    #     add_email_to_user(st.session_state.mail_box.email, mail.id, mail.to_dict())

# Logout
if logout:
    st.session_state.mail_box.logout()
    st.session_state["logged_in"] = False
    st.session_state["email"] = None
    st.session_state["app_password"] = None
    st.success("Logged out successfully!")
    st.session_state["mail_checked_initially"] = False
    st.switch_page("main.py")

# Hiển thị danh sách mail dạng dòng
# List mails; switch pages immediately in the button handler
if st.session_state.mail_box.get_mails_successful:
    for idx, mail in enumerate(st.session_state.mail_box.get_mails_list()):
        if mail.success and mail.category == category:
            mail_dt_str = mail.datetime.strftime("%Y-%m-%d %H:%M")
            st.divider()
            with st.container():
                col1, col2, col3 = st.columns([2, 8, 1.5])
                with col1:
                    st.markdown(f"**{mail.sender}** \n\n{mail_dt_str}")
                with col2:
                    if st.button(mail.subject, key=f"subject_{idx}"):
                        st.session_state["selected_mail"] = mail
                        st.switch_page("pages/mail_detail.py")
                with col3:
                    st.info(mail.category)

else:
    st.info("No messages or failed to fetch.")