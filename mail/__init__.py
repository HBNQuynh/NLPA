from datetime import datetime
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import re
import html2text
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def html_to_text(html):
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0  # prevents line wrapping
    return h.handle(html)

def log_structure(part, depth=0):
    prefix = "  " * depth
    ct = part.get_content_type()
    print(f"{prefix}- Content-Type: {ct}")
    if part.is_multipart():
        for subpart in part.iter_parts():
            log_structure(subpart, depth + 1)
    else:
        disp = part.get("Content-Disposition", "inline")
        print(f"{prefix}  Disposition: {disp}")
        print(f"{prefix}  Charset: {part.get_content_charset()}")
    
class Mail:
    def __init__(self, msg_id, data):
        self.id = msg_id
        self.data = data
        self.success, self.sender, self.sender_addr, self.subject, self.datetime, self.content, self.message_id, self.thread_id = self.parse_email()
        # remove HTML content
        # while self.content.find("[HTML Content Start]") >= 0:
        #     pattern = r"\[HTML Content Start\].*?\[HTML Content End\]"
        #     self.content = re.sub(pattern, "", self.content, flags=re.DOTALL)

        self.category = None
        self.priority_score = None

    def __repr__(self):
        return (f"sender='{self.sender}', subject='{self.subject}', \n"
                f"received_at={self.datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}, \n"
                f"content_len={len(self.content)}\n"
                f"content: {self.content}") if self.success else "Failed to parse mail data"
    
    def extract_preferred_text(self, part):
        if part.is_multipart():
            for subpart in part.iter_parts():
                result = self.extract_preferred_text(subpart)
                if result:  # Return first good result
                    return result
        else:
            disp = part.get("Content-Disposition", "")
            if 'attachment' in disp:
                return ""
            ct = part.get_content_type()
            data = part.get_payload(decode=True) or b""
            try:
                text = data.decode(part.get_content_charset() or 'utf-8', errors='replace')
                if text and ct == "text/html":
                    return html_to_text(text)
                elif text and ct == "text/plain":
                    return text
            except Exception:
                logging.warning("Skipping undecodable part")
        return ""

    def parse_email(self) -> Tuple[bool, str, str, str, datetime, str, str, str]:
        try:
            envelope = self.data.get(b'ENVELOPE')
            raw_email_bytes = self.data.get(b'RFC822')
            if not envelope or not raw_email_bytes:
                logging.warning(f"Skipping message ID {self.id}: Missing ENVELOPE or RFC822 data.")
                return False, None, None, None, None, None, None
            
            # --- Parse Envelope (subject/sender/date) ---
            subject = ''.join(
                frag.decode(enc or 'utf-8', errors='replace') if isinstance(frag, bytes) else frag
                for frag, enc in decode_header(envelope.subject.decode('utf-8', errors='replace'))
            )
            sender_addr = envelope.from_[0] if envelope.from_ else None
            name = ''.join(
                frag.decode(enc or 'utf-8', errors='replace') if isinstance(frag, bytes) else frag
                for frag, enc in decode_header(
                    sender_addr.name.decode('utf-8', errors='replace') if sender_addr and sender_addr.name else ""
                )
            )
            mailbox = sender_addr.mailbox.decode('utf-8', errors='replace') if sender_addr and sender_addr.mailbox else "unknown"
            host = sender_addr.host.decode('utf-8', errors='replace') if sender_addr and sender_addr.host else "host"
            if name == "": 
                name = mailbox
            sender_addr = f"{mailbox}@{host}" if sender_addr else "Unknown Sender"
            
            date_tuple = envelope.date
            if isinstance(date_tuple, datetime):
                dt = date_tuple
            else:
                # fallback to parsing Date header
                temp_msg = BytesParser(policy=policy.default).parsebytes(raw_email_bytes)
                date_str = temp_msg.get('Date')
                if date_str:
                    dt = parsedate_to_datetime(date_str) or datetime.now()
                else:
                    dt = datetime.now()

            # re‑parse full MIME to build body
            msg = BytesParser(policy=policy.default).parsebytes(raw_email_bytes)
            body = self.extract_preferred_text(msg)
            if body.strip() == "":
                log_structure(msg)


            # if msg.is_multipart():
            #     for part in msg.walk():
            #         disp = part.get('Content-Disposition') or ""
            #         if 'attachment' in disp:
            #             continue
            #         ct    = part.get_content_type()
            #         data  = part.get_payload(decode=True) or b""
            #         try:
            #             text = data.decode(part.get_content_charset() or 'utf-8', errors='replace')
            #             if text != "" and ct.startswith('text/'):
            #                 body += f"{text}\n" if ct=='text/plain' else f"[HTML Content Start] {text} [HTML Content End]\n"
            #         except Exception:
            #             logging.warning(f"Msg {self.id}: skipping undecodable part")
            # else:
            #     data = msg.get_payload(decode=True) or b""
            #     try:
            #         body = data.decode(msg.get_content_charset() or 'utf-8', errors='replace')
            #     except Exception:
            #         logging.warning(f"Msg {self.id}: error decoding singlepart")

            # --- Message & Thread IDs with RFC‑822 fallback ---
            # 1) real Message‑ID header
            header_mid = msg.get('Message-ID') or msg.get('Message-Id')
            header_mid = header_mid.strip() if header_mid else None
            # 2) thread ID
            raw_thr = self.data.get(b'X-GM-THRID')
            thread_id = raw_thr.decode() if isinstance(raw_thr, bytes) else str(raw_thr) if raw_thr else None
            # 3) gm msgid fallback
            raw_mid = self.data.get(b'X-GM-MSGID')
            gm_mid  = raw_mid.decode() if isinstance(raw_mid, bytes) else str(raw_mid) if raw_mid else None
            message_id = header_mid or gm_mid

            return True, name, sender_addr, subject, dt, body.strip(), message_id, thread_id

        except Exception as e:
            logging.error(f"Error parsing msg {self.id}: {e}", exc_info=True)
            return False, None, None, None, None, None, None, None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject or "(No Subject)",
            "sender": self.sender,
            "date": self.datetime.strftime("%Y-%m-%d - %I:%M%p"),
            "body": self.content,
            "category": self.category,
            "priority_score": int(self.priority_score) if self.priority_score != "None" else -1
        }