import streamlit as st
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------- GOOGLE AUTH ----------
def get_g_service():
    try:
        # Streamlit secrets must be in 'TOML' format
        creds_info = dict(st.secrets["google"])
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        return build("sheets", "v4", credentials=credentials)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
SHEET_NAME = "Sheet1"

# ---------- IMPROVED DATE RANGE PARSER ----------
def extract_date(caption):
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "mei": "05", "agu": "08", "okt": "10", "des": "12", "maret": "03"
    }
    caption = caption.lower()
    
    # Matches "25-27 Oct" or "25 - 27 Oct" or "25 Oct"
    # Group 1: Start Day, Group 2: End Day (optional), Group 3: Month Name
    range_pattern = r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s+([a-z]{3,10})"
    
    match = re.search(range_pattern, caption)
    if match:
        day = int(match.group(1))
        month_str = match.group(3)[:3]
        month = month_map.get(month_str, "01")
        year = datetime.today().year
        return f"{year}-{month}-{day:02d}"
    
    # Fallback for DD/MM/YYYY
    simple_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", caption)
    if simple_match:
        return f"{simple_match.group(3)}-{simple_match.group(2).zfill(2)}-{simple_match.group(1).zfill(2)}"
        
    return ""

def parse_all_fields(caption, url):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    
    # 1. Date
    event_date = extract_date(caption)
    
    # 2. Title (Take first line that isn't an emoji or hashtag)
    event_title = "Untitled"
    for l in lines:
        if not l.startswith("#") and len(l) > 5:
            event_title = l[:100]
            break

    # 3. Penyelenggara
    handles = re.findall(r'@[\w.]+', caption)
    penyelenggara = ", ".join(set(handles)) if handles else "-"

    # 4. Location
    location = "-"
    for l in lines:
        if any(emoji in l for emoji in ["📍", "🏛️", "🏢"]):
            location = re.sub(r'[📍🏛️🏢]', '', l).strip()
            break

    # 5. Link
    link_match = re.search(r'(https?://[^\s]+)', caption)
    reg_link = link_match.group(1) if link_match else "-"

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- UI & EXECUTION ----------
st.set_page_config(page_title="Data Parser", page_icon="📝")
st.title("💗 Bertemu Djakarta Parser")

caption_input = st.text_area("Paste Caption Here", height=200)
url_input = st.text_input("Source URL")

if st.button("Save to Google Sheets ✨"):
    if caption_input and url_input:
        service = get_g_service()
        if service:
            row = parse_all_fields(caption_input, url_input)
            
            try:
                service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{SHEET_NAME}!A:F",
                    valueInputOption="USER_ENTERED",
                    body={"values": [row]}
                ).execute()
                
                st.success("Data Saved!")
                st.table({"Date": row[0], "Title": row[1], "Host": row[2], "Loc": row[3], "Link": row[4]})
            except Exception as e:
                st.error(f"Sheet Error: {e}")
    else:
        st.warning("Please fill both fields.")
