import streamlit as st
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------- GOOGLE AUTH ----------
def get_g_service():
    try:
        # Streamlit secrets must be in TOML format
        creds_info = dict(st.secrets["google"])
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        return build("sheets", "v4", credentials=credentials)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
SHEET_NAME = "Sheet1"

# ---------- ADVANCED PARSING LOGIC ----------

def extract_date(caption):
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "mei": "05", "agu": "08", "okt": "10", "des": "12", "maret": "03", "agustus": "08"
    }
    caption = caption.lower()
    
    # Matches "25-27 Oct" or "25 Oct"
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
        y = simple_match.group(3)
        if len(y) == 2: y = f"20{y}"
        return f"{y}-{simple_match.group(2).zfill(2)}-{simple_match.group(1).zfill(2)}"
        
    return ""

def parse_all_fields(caption, url):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    
    # 1. DATE
    event_date = extract_date(caption)
    
    # 2. TITLE (Prioritize Bold **text**)
    event_title = "Untitled Event"
    bold_match = re.search(r"\*\*(.*?)\*\*", caption)
    if bold_match:
        event_title = bold_match.group(1).strip()
    else:
        # Fallback: Find first line that isn't a hashtag or emoji-only
        for l in lines:
            clean_l = re.sub(r'[^\w\s]', '', l).strip()
            if not l.startswith("#") and len(clean_l) > 3:
                event_title = l[:100]
                break

    # 3. PENYELENGGARA (@mentions)
    handles = re.findall(r'@[\w.]+', caption)
    penyelenggara = ", ".join(sorted(set(handles))) if handles else "-"

    # 4. LOCATION (Looking for markers)
    location = "-"
    for l in lines:
        if any(mark in l.lower() for mark in ["📍", "location:", "lokasi:", "at ", "place:"]):
            location = re.sub(r'(?i)location:|lokasi:|at |📍', '', l).strip()
            break

    # 5. REGISTRATION LINK (Keyword-aware)
    reg_link = "-"
    # Search for link near keywords
    for l in lines:
        if any(k in l.lower() for k in ["link", "htm", "daftar", "free", "regis", "tiket", "ticket"]):
            link_search = re.search(r'(https?://[^\s]+)', l)
            if link_search:
                reg_link = link_search.group(1)
                break
    
    # Final fallback if no keyword match
    if reg_link == "-":
        any_link = re.search(r'(https?://[^\s]+)', caption)
        if any_link:
            reg_link = any_link.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Event Parser", page_icon="💗")

st.markdown("""
<style>
    .stApp { background-color: #D84565; color: white; }
    .main-card { background: white; padding: 20px; border-radius: 15px; color: #333; }
    .stButton>button { background-color: #D84565 !important; color: white !important; width: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("💗 Bertemu Djakarta: Event Parser")

with st.container():
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    caption_input = st.text_area("1. Paste Instagram Caption here 👇", height=250)
    url_input = st.text_input("2. Source URL 👇")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("---")

if st.button("🚀 Process & Save to Sheet"):
    if not caption_input or not url_input:
        st.warning("Please fill in both the caption and the source URL! 🌸")
    else:
        service = get_g_service()
        if service:
            try:
                with st.spinner('Parsing data...'):
                    row_data = parse_all_fields(caption_input, url_input)
                    
                    # Append to Sheets
                    service.spreadsheets().values().append(
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"{SHEET_NAME}!A:F",
                        valueInputOption="USER_ENTERED", # Better for formatting dates/links
                        body={"values": [row_data]}
                    ).execute()
                    
                st.success("✅ Added to Google Sheet successfully!")
                
                # Display Summary
                st.table({
                    "Field": ["Event Date", "Title", "Host", "Location", "Reg Link", "Source"],
                    "Parsed Value": row_data
                })
            except Exception as e:
                st.error(f"Error saving to Sheet: {e}")
