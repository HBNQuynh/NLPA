import streamlit as st
import time

st.set_page_config(page_title="Dashboard", page_icon="📬")

# Kiểm tra nếu chưa đăng nhập thì quay lại trang login
# if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
#     st.warning("You have to log in first!")
#     st.switch_page("web.py")

st.title("📬 Email Dashboard")

col = st.columns([6, 1])
#st.write(f"Logged in as: {st.session_state['email']}")
with col[0]:
    st.write(f"Logged in as: example@gmail.com")
with col[1]:
    logout = st.button("Log out", key="logout_button") 



# Code xử lý mail
n = 0
while (n < 3):
            
    # raw_email = msg_data[0][1]
    # email_message = email.message_from_bytes(raw_email)
    subject = "subject"
    sender = "sender@gmail.com"
    body = "This is a test email body.This is a test email body.This is a test email body.This is a test email body.This is a test email body.This is a test email body."
    
    st.divider()
    with st.container():
        cols = st.columns([2, 3, 1])
        with cols[0]:
            st.markdown("**<Sender>**")
        with cols[1]:
            st.markdown("**<Subject>**")
        with cols[2]:
            st.info(("<Category>"))

    # with st.expander("click to see detail"):
        
    #     st.markdown("##### Subject")

    #     st.write("From: ", sender)
        
    #     col = st.columns([10, 1, 10])
    #     with col[0]:
    #         st.markdown("##### Context")
    #         st.write(body)
    #     with col[1]:
    #         st.write("")
    #     with col[2]:
    #         st.markdown("##### Summary")
    #         st.write("Summary of the email body goes here.")

    #     reply_button = st.button("Reply", key=f"reply_button{n}")
    #     if reply_button:
    #         reply_suggest = "reply suggestion goes here"
    #         st.write(f"**Reply suggestion:** {reply_suggest}")
    #         st.text_input("Reply to this email:", key=f"reply_input{n}")


    n += 1
        
    st.write("\n")

    with st.spinner('Checking for mail...'):
        time.sleep(2)
