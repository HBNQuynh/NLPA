import os
import base64
import logging
from email.mime.text import MIMEText
from email.utils import parseaddr     
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

SCOPES     = ['https://www.googleapis.com/auth/gmail.send']
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CRED_FILE  = os.path.join(BASE_DIR, "..", "usermailbox", "desktop_client.json")
TOKEN_FILE = os.path.join(BASE_DIR, "..", "usermailbox", "token.json")

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CRED_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def create_reply(to: str, subject: str, body: str, message_id: str) -> dict:
    msg = MIMEText(body)
    # Use the special “me” for the API’s userId, but for the header use your own address  
    msg['From'] = 'me'  

    # sanitize the To header
    name, addr = parseaddr(to)
    if not addr:
        raise ValueError(f"Invalid recipient address: {to}")
    msg['To'] = addr            # ← only the email part

    msg['Subject']    = subject
    msg['In-Reply-To'] = message_id
    msg['References']  = message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {'raw': raw}

def send_reply(to: str, subject: str, body: str, message_id: str, thread_id: str = None) -> dict:
    """
    1) Try sending without threadId (Gmail will infer it from In-Reply‑To).
    2) If you still need to force a threadId, catch the 400 and re-fetch the real one.
    """
    service = get_service()
    payload = create_reply(to, subject, body, message_id)

    try:
        return service.users().messages().send(userId='me', body=payload).execute()

    except HttpError as e:
        # If thread_id was provided but invalid, grab the real one and retry
        msg = e.error_details or []
        if e.resp.status == 400 and any('Invalid thread_id' in d.get('message', '') for d in msg):
            # fetch the real threadId on the server
            meta = service.users().messages()\
                          .get(userId='me', id=message_id, format='minimal')\
                          .execute()
            true_thread = meta.get('threadId')
            if not true_thread:
                raise

            # retry with an explicit, correct threadId
            payload['threadId'] = true_thread
            return service.users().messages().send(userId='me', body=payload).execute()

        # anything else just re‑raise
        logging.error(f"Failed to send reply: {e}", exc_info=True)
        raise