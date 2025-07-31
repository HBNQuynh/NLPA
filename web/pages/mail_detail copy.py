import streamlit as st

subject = "subject"
sender = "sender@gmail.com"
body = "This is a test email body.This is a test email body.This is a test email body.This is a test email body.This is a test email body.This is a test email body."

# UI
st.markdown("##### Subject")
st.write("From: ", sender)

col = st.columns([10, 1, 10])
with col[0]:
    st.markdown("##### Context")
    st.write(body)
with col[1]:
    st.write("")
with col[2]:
    st.markdown("##### Summary")
    st.write("Summary of the email body goes here.")

reply_button = st.button("Reply", key="reply_button")
if reply_button:
    reply_suggest = "reply suggestion goes here"
    st.write(f"**Reply suggestion:** {reply_suggest}")
    st.text_input("Reply to this email:", key="reply_input")