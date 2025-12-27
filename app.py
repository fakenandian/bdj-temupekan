import streamlit as st
import re
import requests
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
    embed_url = f"{url.rstrip('/')}/embed/captioned/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(embed_url, headers=headers, timeout=10)
        owner_match = re.search(r'class="UsernameText"[^>]*>([^<]+)</span>', res.text)
        cap_match = re.search(r'class="CaptionText"[^>]*>(.*?)</div>', res.text, re.DOTALL)
        
        owner = owner_match.group(1).strip() if owner_match else None
        caption = cap_match.group(1).encode().decode('unicode_escape') if cap_match else None
        
        if caption:
            caption = re.sub('<[^<]+?>', '', caption)
        return caption, owner
    except:
        return None, None

# ---------- PARSING LOGIC ----------
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
        return f"{datetime.today().year}-{month}-{day:02d}"
    return ""

def parse_all_fields(caption, url, owner_handle):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    
    # 1. DATE
    event_date = extract_date(caption)
    
    # 2. TITLE (Strict: Bold Only)
    event_title = ""
    bold_match = re.search(r"\*\*(.*?)\*\*", caption)
    if bold_match:
        event_title = bold_match.group(1).strip()

    # 3. PENYELENGGARA (Host Logic)
    found_hosts = set()
    
    # Extract from URL if owner_handle is missing
    if not owner_handle:
        url_parts = url.split('/')
        if "instagram.com" in url and len(url_parts) > 3:
            potential = url_parts[3]
            if potential not in ['p', 'reels', 'tv', 'stories']:
                owner_handle = potential

    if owner_handle:
        found_hosts.add(f"@{owner_handle.replace('@','')}")
    
    mentions = re.findall(r'@([\w.]+)', caption)
    for m in mentions:
        found_hosts.add(f"@{m.rstrip('.')}")
    
    collab_matches = re.findall(r"([@\w\s]+)\s+[xX]\s+([@\w\s]+)", caption)
    for match in collab_matches:
        for name in match:
            n = name.strip()
            if len(n) > 2 and not n.lower().startswith('http'): 
                found_hosts.add(n.rstrip('.'))

    penyelenggara = ", ".join(sorted(found_hosts))

    # 4. LOCATION
    location = ""
    loc_keys = ["📍", "location:", "lokasi:", "area:", "at:", "place:", "venue:"]
    for l in lines:
        if any(k in l.lower() for k in loc_keys):
            location = re.sub(r'(?i)location:|lokasi:|area:|at:|place:|venue:|📍', '', l).strip()
            break

    # 5. REGISTRATION LINK
    reg_link = "-"
    if any(f in caption.upper() for f in ["FREE", "GRATIS", "HTM: 0", "RP 0"]):
        reg_link = "FREE"

    url_pattern = r"((?:https?://|www\.)[^\s]+|(?:bit\.ly|linktr\.ee|forms\.gle|tinyurl\.com|linkin\.bio)/[^\s]+)"
    kw_pattern = rf"(?i)(?:link|htm|daftar|regis|tiket|ticket|pendaftaran).*?{url_pattern}"
    link_match = re.search(kw_pattern, caption, re.DOTALL)
    
    if link_match:
        reg_link = link_match.group(1).rstrip('.,')
    else:
        any_l = re.search(url_pattern, caption)
        if any_l: reg_link = any_l.group(1).rstrip('.,')

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- STREAMLIT UI ----------
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
    url_input = st.text_input("1. Paste Instagram URL here 👇")
    
    # Auto-fetch attempt
    caption = None
    owner = None
    if url_input:
        with st.spinner("Checking Instagram..."):
            caption, owner = fetch_ig_caption(url_input)
        
        if not caption:
            st.info("Manual check: Please paste the caption below. 🌸")
            caption = st.text_area("2. Paste Caption manually 👇", height=200)
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 Process & Save to Sheet"):
    if not url_input or not caption:
        st.warning("Please provide both the URL and the Caption! 🌸")
    else:
        service = get_g_service()
        if service:
            try:
                row = parse_all_fields(caption, url_input, owner)
                service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:F",
                    valueInputOption="USER_ENTERED", body={"values": [row]}
                ).execute()
                st.success("✅ Added to Google Sheet! Thankiees! 🌸")
                st.table({"Field": ["Date", "Title", "Host(s)", "Loc", "Reg", "Source"], "Value": row})
            except Exception as e:
                st.error(f"Error saving to Sheet: {e}")
