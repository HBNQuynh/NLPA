import os
import json
import logging
from typing import List, Tuple, Dict
from google.auth.transport.requests import Request
from imapclient import IMAPClient # Use consistently
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError, GoogleAuthError
from json import JSONDecodeError
import datetime
from firebase_module.firestore import FirebaseFirestore

from concurrent.futures import ThreadPoolExecutor, as_completed, Future

from gemini_processor import GeminiProcessor
from mail import Mail

executor = ThreadPoolExecutor(max_workers=30)  # Keep executor alive

futures = []
proccessing_msg_ids = []


week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

gemini_processor = GeminiProcessor()
class MailBox:
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email', # Full URL for email
        'https://mail.google.com/'
    ]
    DEFAULT_CLIENT_SECRETS_PATH = "usermailbox/desktop_client.json" # Ensure this path is correct

    def __init__(self, email: str, app_password: str = "", oauth_authenticate: bool = False):
        self.client: IMAPClient = None
        self.future_map: Dict[Future, Tuple[int, str]] = {}
        self.email = email
        self.get_mails_successful: bool = False
        self.mails: Dict[str, Mail] = {}

        if self.email == "" and not oauth_authenticate:
            logging.error("Email cannot be empty")
            return
        
        self.authenticate(email, app_password, oauth_authenticate)

    def handle_scheduler_result(self):
        mail_to_update = set()

        for future in as_completed(self.future_map):
            msg_id, task = self.future_map[future]
            mail_to_update.add(msg_id)
            result = future.result()
            if task == "classify":
                self.mails[msg_id].category = result
            elif task == "prioritize":
                self.mails[msg_id].priority_score = result
        
        for id in mail_to_update:
            self.firestore_connection.add_email_to_user(str(id), self.mails[id].to_dict())
        
        self.future_map = {}


    def get_mails(self):
        emails_data = None
        fetched_data: list = list(self.mails.keys())
        if self.client:
            emails_data = self.fetch_mails(search_criteria = ['SINCE', week_ago.strftime("%d-%b-%Y")])
        else:
            logging.error("Failed to authenticate")
            self.get_mails_successful = False
            return
        if emails_data:
            for msg_id, data in emails_data.items():
                if msg_id not in fetched_data:
                    mail = Mail(msg_id, data)
                    if mail.success:
                        found, past_mail_dict = self.firestore_connection.get_email_by_id(str(msg_id))
                        if (
                            found 
                            and past_mail_dict["category"] 
                            and past_mail_dict["category"] != "None" 
                            and past_mail_dict["priority_score"] 
                            and past_mail_dict["priority_score"] != -1
                        ):
                            mail.category = past_mail_dict["category"]
                            mail.priority_score = past_mail_dict["priority_score"]
                        else:
                            self.future_map[
                                executor.submit(
                                    gemini_processor.classify_email, 
                                    mail.subject, 
                                    mail.content
                                )
                            ] = (msg_id, "classify")

                            self.future_map[ 
                                executor.submit(
                                    gemini_processor.prioritize_email, 
                                    mail.subject, 
                                    mail.content, 
                                    mail.category, 
                                    mail.datetime.strftime("%Y-%m-%d - %I:%M%p")
                                )
                            ] = (msg_id, "prioritize")

                        self.mails[msg_id] = mail
                    else:
                        logging.error(f"Fail to parse mail id: {msg_id}")
                else:
                    if self.mails[msg_id].category == "None":
                        self.future_map[ 
                            executor.submit(
                                gemini_processor.classify_email, 
                                self.mails[msg_id].subject, 
                                self.mails[msg_id].content
                            )
                        ] = (msg_id, "classify")

                    if self.mails[msg_id].priority_score == -1 or self.mails[msg_id].priority_score == "None":
                        self.future_map[ 
                            executor.submit(
                                gemini_processor.prioritize_email, 
                                self.mails[msg_id].subject, 
                                self.mails[msg_id].content, 
                                self.mails[msg_id].category, 
                                self.mails[msg_id].datetime.strftime("%Y-%m-%d - %I:%M%p")
                            )
                        ] = (msg_id, "prioritize")

                    # self.firestore_connection.add_email_to_user(str(msg_id), self.mails[msg_id].to_dict())
        
        self.handle_scheduler_result()
        self.get_mails_successful = True
    
    def authenticate(self, email: str, app_password: str, oauth_authenticate: bool):
        self.email = email
        try:
            if oauth_authenticate:            
                self.client = self.authenticate_with_oauth()
                self.login_successful = True
            else:
                self.client = self.authenticate_with_app_password_imapclient(self.email, app_password)
                self.login_successful = True
        except:
            self.login_successful = False
        
        if self.login_successful:
            self.firestore_connection = FirebaseFirestore(self.email)
            self.get_mails()  

    def fetch_mails(self, folder: str = 'INBOX', search_criteria: list = ['UNSEEN', "RECENT"]) -> dict:
        try:
            logging.info(f"Selecting folder: {folder}")
            # Select folder - use readonly=False if you plan to modify flags (e.g., mark as read)
            select_info = self.client.select_folder(folder, readonly=True)
            logging.info(f"{select_info[b'EXISTS']} messages in {folder}")

            logging.info(f"Searching for emails with criteria: {search_criteria}")
            # Search for message IDs
            message_ids = self.client.search(search_criteria)
            logging.info(f"Found {len(message_ids)} matching messages.")

            if not message_ids:
                return None # Return empty list if no messages found

            # Fetch envelope (for sender, subject, date) and RFC822 (for full raw content)
            # Using bytes keys is generally safer with imapclient fetch results
            fetch_items = [b'ENVELOPE', b'RFC822', b'X-GM-THRID', b'X-GM-MSGID']
            logging.info(f"Fetching {fetch_items} for {len(message_ids)} messages...")
            messages_data = self.client.fetch(message_ids, fetch_items)
        except IMAPClient.Error as e:
            logging.error(f"An IMAP error occurred during email fetching: {e}")
        return messages_data
    
    def authenticate_with_oauth(
        self,
        token_info: dict = None,
        client_secrets_path: str = DEFAULT_CLIENT_SECRETS_PATH
    ) -> IMAPClient | None:
        """
        Authenticates with Gmail IMAP using OAuth 2.0.

        Handles token loading, refreshing, and user authorization flow.

        Args:
            token_info: Dictionary containing token info (alternative to file).
            client_secrets_path: Path to the client secrets JSON file.

        Returns:
            An authenticated IMAPClient instance or None if authentication fails.
        """
        creds = None
        try:
            # 1. Load token from dictionary (if provided)
            if token_info:
                logging.info("Loading credentials from provided token_info dictionary.")
                creds = Credentials.from_authorized_user_info(token_info, self.SCOPES)

            # 2. Refresh or Authenticate if no valid credentials exist
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logging.info("Credentials expired, attempting to refresh...")
                    try:
                        creds.refresh(Request())
                    except RefreshError as e:
                        logging.warning(f"Failed to refresh token: {e}. Need to re-authenticate.")
                        creds = None # Refresh failed, force re-authentication
                    except Exception as e: # Catch other potential refresh errors
                        logging.error(f"An unexpected error occurred during token refresh: {e}")
                        creds = None
                else:
                    logging.info("No valid credentials found, initiating OAuth flow...")
                    if not os.path.exists(client_secrets_path):
                        logging.error(f"Client secrets file not found at: {client_secrets_path}")
                        return None
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, self.SCOPES)
                        # Ensure port=0 to avoid conflicts if run multiple times locally
                        creds = flow.run_local_server(port=0)
                    except Exception as e:
                        logging.error(f"OAuth flow failed: {e}")
                        return None # Critical failure during flow
                    
            # --- If we still don't have valid credentials after all attempts ---
            if not creds or not creds.valid:
                logging.error("Failed to obtain valid OAuth credentials.")
                return None

            # 4. Verify ID token and get email
            try:
                id_info = id_token.verify_oauth2_token(
                    creds.id_token, Request(), audience=creds.client_id
                )
                user_email = id_info["email"]
                self.email = user_email
                logging.info(f"Successfully obtained credentials for user: {user_email}")
            except Exception as e:
                logging.error(f"Failed to verify ID token: {e}")
                # Decide if you want to proceed without verification or fail
                # For IMAP login, email is needed by imapclient, so we should fail here.
                return None

            # 5. Authenticate with IMAP using OAuth2
            try:
                imap_client = IMAPClient("imap.gmail.com", ssl=True)
                logging.info(f"Attempting IMAP OAuth2 login for {user_email}...")
                # Use the access token (creds.token) for the XOAUTH2 mechanism
                auth_string = f"user={user_email}\1auth=Bearer {creds.token}\1\1"
                imap_client.oauth2_login(user_email, creds.token) # Correct usage for imapclient >= 2.1.0
                # Note: Older imapclient versions might need `imap_client.login(user_email, auth_string)` and capability check

                logging.info("IMAP OAuth2 login successful.")
                return imap_client
            except IMAPClient.Error as e: # Catch imapclient specific errors
                logging.error(f"IMAP OAuth2 login failed: {e}")
                return None
            except Exception as e:
                logging.error(f"An unexpected error occurred during IMAP login: {e}")
                # Clean up client if login fails mid-way? IMAPClient usually handles this.
                return None

        except GoogleAuthError as e:
            logging.error(f"A Google Authentication error occurred: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during OAuth setup: {e}")
            return None

    def authenticate_with_app_password_imapclient(self, email: str, app_password: str) -> IMAPClient | None:
        """
        Authenticates with Gmail IMAP using an App Password (less secure).
        Uses imapclient library.

        Args:
            email: The Gmail address.
            app_password: The generated App Password.

        Returns:
            An authenticated IMAPClient instance or None if authentication fails.
        """
        try:
            logging.info(f"Attempting IMAP login with App Password for {email} using imapclient...")
            client = IMAPClient("imap.gmail.com", ssl=True)
            client.login(email, app_password)
            logging.info("IMAP App Password login successful (imapclient).")
            return client
        except IMAPClient.LoginError as e:
            logging.error(f"IMAP App Password login failed (imapclient): {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during App Password login (imapclient): {e}")
            return None

    def logout(self):
        self.client.logout()
        self.email = None
        self.login_successful = False
        self.get_mails_successful: bool = False
        self.mails: Dict[str, Mail] = {}

    def get_mails_list(self) -> List[Mail]:
        mail_list = list(self.mails.values())
        mail_list.sort(key=lambda mail: int(mail.priority_score) if mail.priority_score != "None" else -1, reverse=True)
        return mail_list

