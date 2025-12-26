import streamlit as st
import re
import json
import requests
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------- GOOGLE AUTH ----------
# Ensure your secrets are correctly set in Streamlit Cloud or .streamlit/secrets.toml
credentials = service_account.Credentials.from_service_account_info(
    dict(st.secrets["google"])
)

SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
SHEET_NAME = "Sheet1"

service = build("sheets", "v4", credentials=credentials)
sheet = service.spreadsheets()

# ---------- PARSING LOGIC ----------

def extract_event_date(caption):
    month_map = {
        "jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
        "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12",
        "mei":"05","agu":"08","okt":"10","des":"12"
    }
    caption = caption.lower()
    # Pattern for "25 October 2023" or "25 Oct"
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s*(\d{2,4})?", caption)
    if m:
        day = int(m.group(1))
        month_str = m.group(2)[:3]
        month = month_map.get(month_str, "01")
        year = m.group(3) if m.group(3) else datetime.today().year
        return f"{year}-{month}-{day:02d}"
    return ""

def extract_event_title(caption):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    if not lines: return "Untitled"
    # Look for common headers
    for l in lines:
        if any(x in l.lower() for x in ["tema:", "title:", "event:"]):
            return re.sub(r'(?i).+?:', '', l).strip()
    return lines[0][:100] # Fallback to first line

def process_caption(caption, url):
    """Core logic to parse the text once it is obtained"""
    event_date = extract_event_date(caption)
    event_title = extract_event_title(caption)
    
    handles = re.findall(r'@[\w.]+', caption)
    penyelenggara = ", ".join(sorted(set(handles)))
    
    location = ""
    for l in caption.split("\n"):
        if "📍" in l or "at " in l.lower():
            location = l.replace("📍","").strip()
            break

    reg_link = ""
    link = re.search(r'(https?://[^\s]+)', caption)
    if link: reg_link = link.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- SAVE ----------
def append_to_sheet(row):
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F",
        valueInputOption="RAW",
        body={"values":[row]},
    ).execute()

# ---------- UI ----------
st.title("🩷 Bertemu Djakarta")

tab1, tab2 = st.tabs(["Auto-Link", "Manual Paste"])

with tab1:
    url = st.text_input("Paste Instagram link here 👇")
    if st.button("Extract from Link ✨"):
        # This part often fails because of IG bot protection
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers)
        
        if "login" in res.url:
            st.error("Instagram blocked the automatic scraper. Please use the 'Manual Paste' tab!")
        else:
            # Attempt to find caption in the HTML
            # Note: This is fragile as IG changes their HTML frequently
            match = re.search(r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.*?)"\}\}\]\}', res.text)
            if match:
                caption = match.group(1).encode().decode('unicode_escape')
                row = process_caption(caption, url)
                append_to_sheet(row)
                st.success("Added to Sheet!")
                st.write(row)
            else:
                st.warning("Couldn't find caption automatically. Use Manual Paste.")

with tab2:
    manual_url = st.text_input("Source URL")
    manual_caption = st.text_area("Paste the caption text here directly")
    if st.button("Parse & Save ✨"):
        if manual_caption:
            row = process_caption(manual_caption, manual_url)
            append_to_sheet(row)
            st.success("Saved Successfully!")
            st.table({
                "Field": ["Date", "Title", "Host", "Loc", "Link", "Source"],
                "Value": row
            })
