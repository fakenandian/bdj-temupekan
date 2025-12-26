import streamlit as st
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------- GOOGLE AUTH ----------
try:
    credentials = service_account.Credentials.from_service_account_info(
        dict(st.secrets["google"])
    )
    SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
    SHEET_NAME = "Sheet1"
    service = build("sheets", "v4", credentials=credentials)
    sheet = service.spreadsheets()
except Exception as e:
    st.error("Google Auth Error: Check your Streamlit Secrets!")

# ---------- NEW & IMPROVED PARSING ----------

def parse_all_fields(caption, source_url):
    # 1. DATE PARSING (Handles Indo & English)
    event_date = ""
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "mei": "05", "agu": "08", "okt": "10", "des": "12"
    }
    
    # Look for "25 Oct" or "25 Oktober"
    date_match = re.search(r"(\d{1,2})\s+([a-zA-Z]{3,10})", caption)
    if date_match:
        day = int(date_match.group(1))
        month_str = date_match.group(2).lower()[:3]
        month = month_map.get(month_str, "01")
        year = datetime.today().year
        event_date = f"{year}-{month}-{day:02d}"

    # 2. TITLE PARSING (Aggressive fallback)
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    event_title = "Untitled Event"
    if lines:
        # Check if any line has "Tema" or "Title"
        for l in lines:
            if any(x in l.lower() for x in ["tema:", "title:", "event:"]):
                event_title = re.sub(r'(?i).+?:', '', l).strip()
                break
        else:
            # If no keyword, take the first non-hashtag line
            for l in lines:
                if not l.startswith("#"):
                    event_title = l[:100]
                    break

    # 3. PENYELENGGARA (@mentions)
    handles = re.findall(r'@[\w.]+', caption)
    penyelenggara = ", ".join(sorted(set(handles))) if handles else "Unknown"

    # 4. LOCATION (Emoji or Keyword)
    location = "Not Specified"
    for l in lines:
        if "📍" in l or "at " in l.lower() or "loc:" in l.lower():
            location = l.replace("📍","").replace("Loc:","").replace("loc:","").strip()
            break

    # 5. REGISTRATION LINK
    reg_link = "No Link"
    link_search = re.search(r'(https?://[^\s]+)', caption)
    if link_search:
        reg_link = link_search.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, source_url]

# ---------- SAVE FUNCTION ----------
def append_to_sheet(row):
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F",
        value
