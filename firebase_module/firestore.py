import datetime
from typing import List
import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os

def init_firestore():
    if not firebase_admin._apps:
        # Lấy đường dẫn tuyệt đối tới file hiện tại
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Ghép với đường dẫn tới file JSON
        key_path = os.path.join(current_dir, "firestore_access_key.json")
        
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
    return firestore.client()
class FirebaseFirestore:
    def __init__(self, user_email: str):
        self.firestore_client = init_firestore()
        self.user_id = user_email
        self.mail_collection = self.firestore_client.collection('user').document(self.user_id).collection('mail')

    # Add list of mails vào collection 'email'
    def add_email_to_user(self, email_id: str, email_data: dict) -> bool:
        try:
            # Đường dẫn tới mail collection của user
            mail_ref = self.mail_collection.document(email_id)
            
            # Set dữ liệu
            mail_ref.set(email_data)
            logging.info(f"Successfully added email {email_id} to user {self.user_id}.")
            return True
        
        except Exception as e:
            logging.error(f"Error adding email to user: {e}")
            return False
    
    def get_email_by_id(self, email_id: str) -> tuple[bool, dict]:
        try: 
            doc_ref = self.mail_collection.document(email_id)
            doc = doc_ref.get()
            if doc.exists:
                mail_dict = doc.to_dict()
                return True, mail_dict
            else:
                logging.warning(f"Unable to find mail id: {email_id}")
                return False, None
        except Exception as e:
            logging.error(f"Error retrieving email {email_id}: {e}")
            return False, None

    def get_emails_by_ids(self, email_ids: list[str]) -> tuple[dict, list[str]]:
        result = {}
        not_found = []

        for email_id in email_ids:
            try:
                doc_ref = self.firestore_client.collection('user').document(self.user_id).collection('mail').document(email_id)
                doc = doc_ref.get()
                if doc.exists:
                    result[email_id] = doc.to_dict()
                else:
                    not_found.append(email_id)
            except Exception as e:
                logging.error(f"Error retrieving email {email_id}: {e}")
                not_found.append(email_id)
        return result, not_found

    def persist_reply(self, orig_mid: str, reply_res: dict):
        sent_at = datetime.datetime.now()
        doc = {
            'orig_message_id': orig_mid,
            'reply_id':        reply_res.get('id'),
            'thread_id':       reply_res.get('threadId'),
            'sent_at':         sent_at,
        }
        try:
            self.firestore_client.collection('replies').add(doc)
        except Exception as e:
            # log but don’t crash
            import logging; logging.error(f"Failed to persist reply {reply_res.get('id')}: {e}")

def query_emails_by_category(user_id: str, category_id: str) -> List[dict]:
    db = init_firestore()
    output = []

    try:
        mails = db.collection('user').document(user_id).collection('mail') \
            .where('categoryID', '==', category_id) \
            .stream()

        for mail_doc in mails:
            data = mail_doc.to_dict()
            data['id'] = mail_doc.id
            output.append(data)

        logging.info(f"Successfully fetched emails with category {category_id} for user {user_id}.")
    except Exception as e:
        logging.error(f"Error querying emails by category: {e}")

    return output