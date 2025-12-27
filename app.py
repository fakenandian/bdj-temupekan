import streamlit as st
import re
import instaloader
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

# ---------- AUTO-FETCH LOGIC ----------
def fetch_ig_caption(url):
    L = instaloader.Instaloader()
    try:
        # Extract shortcode from URL
        # Pattern handles /p/SHORTCODE/ or /reels/SHORTCODE/
        shortcode_match = re.search(r"/(?:p|reels|tv)/([^/]+)/", url)
        if not shortcode_match:
            return None
        
        shortcode = shortcode_match.group(1)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return post.caption, post.owner_username
    except Exception as e:
        st.warning(f"Auto-fetch failed. Usually happens if IG blocks the server. {e}")
        return None, None

# ---------- UPDATED PARSING ----------
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

def parse_all_fields(caption, url, owner_handle=None):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    
    # 1. DATE
    event_date = extract_date(caption)
    
    # 2. TITLE (Strict: Bold Only)
    event_title = "" 
    bold_match = re.search(r"\*\*(.*?)\*\*", caption)
    if bold_match:
        event_title = bold_match.group(1).strip()

    # 3. PENYELENGGARA (Handle + @Mentions + Collab)
    found_hosts = set()
    if owner_handle:
        found_hosts.add(f"@{owner_handle}")
    
    # @mentions
    mentions = re.findall(r'@([\w.]+)', caption)
    for m in mentions:
        found_hosts.add(f"@{m}")

    # X Collaborations
    collab_pattern = r"([@\w\s]+)\s+[xX]\s+([@\w\s]+)"
    collab_matches = re.findall(collab_pattern, caption)
    for match in collab_matches:
        for name in match:
            clean_name = name.strip()
            if clean_name and len(clean_name) > 2:
                found_hosts.add(clean_name)

    penyelenggara = ", ".join(sorted(found_hosts)) if found_hosts else "-"

    # 4. LOCATION (Enhanced)
    location = "-"
    loc_keywords = ["📍", "location:", "lokasi:", "at ", "place:", "area:", "tempat:"]
    for l in lines:
        if any(mark in l.lower() for mark in loc_keywords):
            location = re.sub(r'(?i)location:|lokasi:|area:|tempat:|at |📍', '', l).strip()
            break

    # 5. REGISTRATION / FREE
    reg_link = "-"
    if any(free_word in caption.upper() for free_word in ["FREE", "GRATIS", "RP 0", "NO FEE"]):
        reg_link = "FREE"

    keyword_pattern = r"(?i)(?:link|htm|daftar|regis|tiket|ticket|pendaftaran|gform|bit\.ly|form).*?(https?://[^\s]+)"
    link_match = re.search(keyword_pattern, caption, re.DOTALL)
    
    if link_match:
        reg_link = link_match.group(1)
    elif reg_link == "-":
        any_link = re.search(r'(https?://[^\s]+)', caption)
        if any_link:
            reg_link = any_link.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- UI ----------
st.set_page_config(page_title="Temu Pekan", page_icon="💗")

st.markdown("""
<style>
    .stApp { background-color: #D84565; color: white; }
    .main-card { background: white; padding: 20px; border-radius: 15px; color: #333; }
</style>
""", unsafe_allow_html=True)

st.title("💗 Temu Pekan Bertemu Djakarta")

with st.container():
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    url_input = st.text_input("Paste Instagram URL only 👇 (Wait for it to fetch)")
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 Fetch & Save to Sheet"):
    if not url_input:
        st.warning("Input URL first! 🌸")
    else:
        with st.spinner("Fetching data from Instagram..."):
            caption, owner = fetch_ig_caption(url_input)
            
        if not caption:
            st.error("Could not fetch caption automatically. Please use a Manual Paste tab or try again.")
            # Optional: provide a manual text area as fallback here
            manual_caption = st.text_area("Paste caption manually as fallback:")
            if manual_caption:
                caption = manual_caption

        if caption:
            service = get_g_service()
            if service:
                try:
                    row_data = parse_all_fields(caption, url_input, owner)
                    service.spreadsheets().values().append(
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"{SHEET_NAME}!A:F",
                        valueInputOption="USER_ENTERED",
                        body={"values": [row_data]}
                    ).execute()
                    
                    st.success("✅ Added to Google Sheet!")
                    st.table({
                        "Field": ["Date", "Title", "Host/Collab", "Location", "Reg/HTM", "Source"],
                        "Value": row_data
                    })
                except Exception as e:
                    st.error(f"Error: {e}")
