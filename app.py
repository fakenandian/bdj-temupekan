import streamlit as st
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------- GOOGLE AUTH ----------
def get_g_service():
    try:
        creds_info = dict(st.secrets["google"])
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        return build("sheets", "v4", credentials=credentials)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
SHEET_NAME = "Sheet1"

# ---------- ADVANCED PARSING ----------

def extract_date(caption):
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "mei": "05", "agu": "08", "okt": "10", "des": "12", "maret": "03", "agustus": "08"
    }
    caption = caption.lower()
    range_pattern = r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s+([a-z]{3,10})"
    match = re.search(range_pattern, caption)
    if match:
        day = int(match.group(1))
        month_str = match.group(3)[:3]
        month = month_map.get(month_str, "01")
        year = datetime.today().year
        return f"{year}-{month}-{day:02d}"
    return ""

def parse_all_fields(caption, url):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    
    # 1. DATE
    event_date = extract_date(caption)
    
    # 2. TITLE (Bold detection)
    event_title = "Untitled Event"
    bold_match = re.search(r"\*\*(.*?)\*\*", caption)
    if bold_match:
        event_title = bold_match.group(1).strip()
    elif lines:
        for l in lines:
            if not l.startswith("#") and len(l) > 5:
                event_title = l[:100]
                break

    # 3. PENYELENGGARA (Enhanced Collaboration Logic)
    found_hosts = set()
    
    # A. Extract mentions (@name)
    mentions = re.findall(r'@([\w.]+)', caption)
    for m in mentions:
        found_hosts.add(f"@{m}")

    # B. Extract Collaborations (Name X Name)
    # This looks for CapitalizedWords or @names separated by ' X ' or ' x '
    collab_pattern = r"([@\w\s]+)\s+[xX]\s+([@\w\s]+)"
    collab_matches = re.findall(collab_pattern, caption)
    for match in collab_matches:
        for name in match:
            clean_name = name.strip()
            if clean_name and len(clean_name) > 2:
                found_hosts.add(clean_name)

    # C. Extract Host from URL (if it's an instagram.com/handle/p/ style link)
    # Note: Modern IG URLs often don't have the handle
    url_handle = re.search(r"instagram\.com/([^/]+)", url)
    if url_handle and url_handle.group(1) not in ['p', 'reels', 'tv']:
        found_hosts.add(f"@{url_handle.group(1)}")

    penyelenggara = ", ".join(sorted(found_hosts)) if found_hosts else "-"

   # 4. LOCATION
    location = "-"
    for l in lines:
        if any(mark in l.lower() for mark in ["📍", "location:", "lokasi:", "at ", "place:"]):
            location = re.sub(r'(?i)location:|lokasi:|at |📍', '', l).strip()
            break

    # 5. REGISTRATION / PRICE LINK 
    reg_link = "-"
    # Check for "FREE" keywords specifically first
    if any(free_word in caption.upper() for free_word in ["FREE", "GRATIS", "RP 0", "FREE ENTRY"]):
        reg_link = "FREE / No Link Needed"
        

    # Now look for actual URLs associated with registration keywords
    keyword_pattern = r"(?i)(?:link|htm|daftar|regis|tiket|ticket|pendaftaran|gform|bit\.ly|form).*?(https?://[^\s]+)"
    link_match = re.search(keyword_pattern, caption, re.DOTALL)
    
    if link_match:
        reg_link = link_match.group(1)
    elif reg_link == "-":
        # Final fallback: If no "FREE" found and no keyword-link found, grab the first URL
        any_link = re.search(r'(https?://[^\s]+)', caption)
        if any_link:
            reg_link = any_link.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Temu Pekan", page_icon="💗")

st.markdown("""
<style>
    .stApp { background-color: #D84565; color: white; }
    .main-card { background: white; padding: 20px; border-radius: 15px; color: #333; }
</style>
""", unsafe_allow_html=True)

st.title("💗 Bertemu Djakarta Parser")

with st.container():
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    caption_input = st.text_area("1. Paste Instagram Caption here 👇", height=250)
    url_input = st.text_input("2. Source URL 👇")
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 Process & Save to Sheet"):
    if not caption_input or not url_input:
        st.warning("Input caption and URL first! 🌸")
    else:
        service = get_g_service()
        if service:
            try:
                row_data = parse_all_fields(caption_input, url_input)
                service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{SHEET_NAME}!A:F",
                    valueInputOption="USER_ENTERED",
                    body={"values": [row_data]}
                ).execute()
                
                st.success("✅ Added to Google Sheet! Thankiees!🌸🌸🌸")
                st.table({
                    "Field": ["Date", "Title", "Host/Collab", "Location", "Reg/HTM", "Source"],
                    "Value": row_data
                })
            except Exception as e:
                st.error(f"Error: {e}")
