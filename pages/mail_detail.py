import streamlit as st
from mail.reply   import send_reply
from usermailbox import gemini_processor

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# Check if the user is logged in
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.warning("You have to log in first!")
    st.switch_page("main.py")

# Grab the selected mail record from session state
if "selected_mail" not in st.session_state or not st.session_state["selected_mail"]:
    st.warning("No mail are selected!")
    st.switch_page("pages/dashboard.py")

# Wrap it in your Mail class using (msg_id, data)
mail = st.session_state.get("selected_mail")
mail_summarize = gemini_processor.summarize_email(mail.subject, mail.content, mail.category)

col1, col2 = st.columns([8, 1])
with col1: 
    st.title("📧 Email Detail")
with col2:
    st.text("\n")
    if st.button("Back to Dashboard"):
        st.session_state["selected_mail"] = None
        st.session_state["reply_suggest"] = ""
        st.switch_page("pages/dashboard.py")
st.divider()

# --- Header UI ---
st.markdown(f"##### Subject: {mail.subject}")
st.write("From: ", mail.sender)
st.write("Received at: ", mail.datetime.strftime("%Y-%m-%d %H:%M"))

st.divider()

print(mail.content)

# --- Body & Summary Columns ---
with st.container():
    col1, col2, col3 = st.columns([12, 1, 8])
    with col1:
        st.markdown("##### Context")
        st.write(mail.content)
    with col2:
        st.markdown("<div style='height:100%; border-left:1px solid #ccc'></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("##### Summary")
        st.write(mail_summarize)
st.divider()

# --- Reply Suggestion Handling ---
if "reply_suggest" not in st.session_state:
    st.session_state.reply_suggest = ""

if st.button("Reply Suggest", key="reply_suggest_btn"):
    st.session_state.reply_suggest = gemini_processor.suggest_reply(mail.subject, mail.content, mail.category)

if st.session_state.reply_suggest:
    st.write(f"**Reply suggestion:** {st.session_state.reply_suggest}")

# --- Reply Input Handling ---
reply_body = st.text_area("Reply to this email:", key="reply_input")

if st.button("Send Reply"):
    # 0) Ensure we have the required IDs
    if not mail.message_id or not mail.thread_id:
        st.error("Cannot reply: original message/thread ID missing.")
    # 1) Ensure body is not empty
    elif not reply_body.strip():
        st.error("Reply body cannot be empty.")
    else:
        # 2) Attempt to send
        try:
            result = send_reply(
                to=mail.sender_addr,  # <-- FIXED: use sender_addr, not sender
                subject=f"Re: {mail.subject}",
                body=reply_body,
                thread_id=mail.thread_id,
                message_id=mail.message_id
            )
        except Exception as e:
            st.error(f"Send failed: {e}")
        else:
            # 3) Attempt to persist
            try:
                st.session_state.mail_box.firestore_connection.persist_reply(mail.message_id, result)
            except Exception as e:
                st.warning(f"Sent but not logged: {e}")
            else:
                st.success("✅ Reply sent and logged!")