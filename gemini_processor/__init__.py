from typing import List
import google.generativeai as genai
from prometheus_client import (
    Counter,
    Histogram,
    Summary,
    CollectorRegistry,
)
import threading
import time
import logging
from collections import deque

my_registry = CollectorRegistry()

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

REQUEST_COUNT = Counter(
    "gemini_api_requests", "Số lượng request đến Gemini API", registry=my_registry
)
SUCCESS_COUNT = Counter(
    "gemini_api_success_count", "Số lượng request thành công", registry=my_registry
)
ERROR_COUNT = Counter(
    "gemini_api_errors", "Số lỗi xảy ra khi gọi Gemini API", registry=my_registry
)
ERROR_TYPE_COUNT = Counter(
    "gemini_api_error_count_by_type",
    "Số lỗi theo loại",
    ["error_type"],
    registry=my_registry,
)
RESPONSE_TIME_HIST = Histogram(
    "gemini_response_time",
    "Thời gian phản hồi của Gemini API",
    buckets=[0.1, 0.5, 1, 2, 5, 10],
    registry=my_registry,
)
RESPONSE_TIME_SUM = Summary(
    "gemini_api_latency_seconds",
    "Thời gian phản hồi trung bình của Gemini API",
    registry=my_registry,
)

CATEGORIES = ["Work", "Commercial", "Fraud", "Others"]

def _handle_error(e):
    error_message = str(e)
    if "429" in error_message:
        ERROR_TYPE_COUNT.labels(error_type="RateLimit").inc()
    elif "403" in error_message:
        ERROR_TYPE_COUNT.labels(error_type="InvalidAPIKey").inc()
    elif "500" in error_message:
        ERROR_TYPE_COUNT.labels(error_type="ServerError").inc()
    else:
        ERROR_TYPE_COUNT.labels(error_type="Unknown").inc()
    logging.error(f"❌ Lỗi API Gemini: {error_message}")


def _observe_latency(start_time, task):
    elapsed = time.time() - start_time
    RESPONSE_TIME_HIST.observe(elapsed)
    RESPONSE_TIME_SUM.observe(elapsed)
    logging.info(f"📊 Thời gian phản hồi {task}: {elapsed:.2f} giây")



class GeminiProcessor:
    api_keys: List[str] = [
        # Insert your API key here
    ]
    RATE_LIMIT = 15
    
    def __init__(self):
        self.usage = {key: deque() for key in self.api_keys}  # track timestamps
        self.lock = threading.Lock()

    def _get_available_key_RR(self):
        now = time.time()
        with self.lock:
            for key in self.api_keys:
                # Remove old timestamps
                while self.usage[key] and now - self.usage[key][0] > 60:
                    self.usage[key].popleft()

                if len(self.usage[key]) < self.RATE_LIMIT:
                    self.usage[key].append(now)
                    return key
        return None
    
    def _get_available_key_LRU(self):
        now = time.time()
        with self.lock:
            # Clean up old timestamps
            for key in self.api_keys:
                while self.usage[key] and now - self.usage[key][0] > 60:
                    self.usage[key].popleft()

            # Find the key with the fewest requests in the last 60 seconds
            available_keys = [
                (key, len(self.usage[key])) 
                for key in self.api_keys 
                if len(self.usage[key]) < self.RATE_LIMIT
            ]

            if not available_keys:
                return None

            # Pick the key with the least usage
            best_key = min(available_keys, key=lambda x: x[1])[0]
            self.usage[best_key].append(now)
            return best_key

    def _get_available_key(self):
        return self._get_available_key_LRU()

    def classify_email(self, subject: str, body: str) -> str:
        while True:
            api_key = self._get_available_key()
            if api_key:
                break
            time.sleep(1)  # wait a second before retrying
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are an intelligent email classification system.

        Your task is to categorize an email into one of the following categories:
        Work,Commercial,Fraud,Others.

        Definitions:
        - Work: Professional communication such as meeting invites, reports, or project discussions. Typically comes from colleagues, clients, or managers.
        - Commercial: Marketing or promotional emails like newsletters, discounts, sales campaigns. They DO NOT request passwords or financial information.
        - Fraud: Emails pretending to be from trusted entities (e.g., banks), containing suspicious links, requests for login credentials, or urgent action.
        - Others: Emails that are personal, social, or do not clearly match the above.

        Rules for classification:
        - If an email includes both promotional content and a suspicious request or link, classify it as "Fraud".
        - If an email references "invoice", "billing", "payment" but comes from unknown or suspicious domains → classify as "Fraud".
        - If the subject contains business-related terms like "meeting", "project", "report", "update" and the tone is formal → classify as "Work".
        - If the email contains greetings like "Dear customer", "Congratulations", "Limited time offer" and includes a product or deal → classify as "Commercial".
        - If the message urges you to "click immediately", "verify your account", or "your account is suspended" → classify as "Fraud".

        Email to classify:
        - Subject: {subject}
        - Body: {body}

        Respond with ONLY ONE WORD from this list: Work, Commercial, Fraud, Others.
        DO NOT explain your reasoning.
        DO NOT include "Category:" or any other text.
        """.strip()

        REQUEST_COUNT.inc()
        start_time = time.time()

        try:
            response = model.generate_content(prompt)
            result = response.text.strip()
            SUCCESS_COUNT.inc()
            return result
        except Exception as e:
            ERROR_COUNT.inc()
            _handle_error(e)
            return "None"
        finally:
            _observe_latency(start_time, "classify")

    def prioritize_email(self, subject: str, body: str, category: str, date: str) -> str:
        while True:
            api_key = self._get_available_key()
            if api_key:
                break
            time.sleep(1)  # wait a second before retrying
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are an intelligent email assistant that evaluates the priority of emails.
        Start with a **base score of 6**. Adjust this score based on the following rules and context to return a final score between **0 and 10**.
        ---
        *Scoring Rules*:
        1. **Based on Category**:
        - "Work": Add 2 points
        - "Commercial": Subtract 2 points
        - "Fraud": Subtract 3 points
        - "Others": No change — score is adjusted only based on subject, body, and date
        2. **Subject & Body Content**:
        - Add points if email contains urgency, deadlines, meetings, approvals, requests for actions, reports
        - Subtract points for promotional language like "discount", "subscribe", "limited offer", "congratulations"
        - Add 1 point for financial or transaction-related content (e.g., invoice, payment notice) IF it's from a trusted source
        3. **Date Received**:
        - Add 1 point if the email was received today or yesterday AND has time-sensitive content
        - Subtract 1 point if the email is older than 7 days and contains no urgency
        ---
        *Email to evaluate*:
        - Category: {category}
        - Subject: {subject}
        - Body: {body}
        - Date received: {date}
        ---
        Respond with ONLY a number between **0 and 10**, representing the final priority score.
        Do NOT explain your reasoning.
        Do NOT include any additional text or formatting.
        """.strip()

        REQUEST_COUNT.inc()
        start_time = time.time()
        try:
            response = model.generate_content(prompt)
            result = response.text.strip()
            SUCCESS_COUNT.inc()
            return result
        except Exception as e:
            ERROR_COUNT.inc()
            _handle_error(e)
            return "None"
        finally:
            _observe_latency(start_time, "prioritize")

    def summarize_email(self, subject: str, body: str, category: str) -> str:
        while True:
            api_key = self._get_available_key()
            if api_key:
                break
            time.sleep(1)  # wait a second before retrying
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are an AI assistant. Please summarize the following email based on its content and its category: "{category}".
        Email:
        - Subject: {subject}
        - Body: {body}
        Return a short summary (1-2 sentences), capturing the key message. Please note that the summary should be concise and to the point and should be the same language as the email.
        Do NOT include any additional text or formatting.
        """.strip()

        REQUEST_COUNT.inc()
        start_time = time.time()

        try:
            response = model.generate_content(prompt)
            summary = response.text.strip()
            SUCCESS_COUNT.inc()
            return summary
        except Exception as e:
            ERROR_COUNT.inc()
            _handle_error(e)
            return f"Error: {e}"
        finally:
            _observe_latency(start_time, "summarize")

    def suggest_reply(self, subject: str, body: str, category: str) -> str:
        while True:
            api_key = self._get_available_key()
            if api_key:
                break
            time.sleep(1)  # wait a second before retrying
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are a highly competent AI assistant specialized in drafting thoughtful and professional email replies.

        Based on the given email's content, subject, and assigned category ("{category}"), generate a **complete, relevant, and polite reply**. 
        Ensure the response:
        - Appropriately addresses the context and intent of the original message
        - Maintains a professional and natural tone
        - Provides necessary details, clarifications, or next steps if applicable
        - Is coherent and easy to read
        - Can be longer than 3 sentences if the context requires
        Do NOT repeat the subject or header. Your reply should be formatted as the body of an actual email.
        ---
        📨 Email:
        - Subject: {subject}
        - Category: {category}
        - Body: {body}
        ---
        ✉️ Write your reply below:
        """.strip()
        
        REQUEST_COUNT.inc()
        start_time = time.time()

        try:
            response = model.generate_content(prompt)
            reply = response.text.strip()
            SUCCESS_COUNT.inc()
            return reply
        except Exception as e:
            ERROR_COUNT.inc()
            _handle_error(e)
            return f"Error: {e}"
        finally:
            _observe_latency(start_time, "suggest")


