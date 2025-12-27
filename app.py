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
    """
    Tries to get caption using a specialized user-agent to mimic a browser.
    If Instagram blocks this, it returns None.
    """
    # Cleaning URL to get the JSON data directly if possible
    json_url = f"{url.rstrip('/')}/?__a=1&__d=dis"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(json_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            caption = data['items'][0]['caption']['text']
            owner = data['items'][0]['user']['username']
            return caption, owner
    except:
        # Fallback to standard HTML scraping if JSON fails
        try:
            res = requests.get(url, headers=headers, timeout=10)
            # Find caption in metadata
            cap_match = re.search(r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.*?)"\}\}\]\}', res.text)
            handle_match = re.search(r'"owner":\{"id":"\d+","username":"(.*?)"\}', res.text)
            
            caption = cap_match.group(1).encode().decode('unicode_escape') if cap_match else None
            owner = handle_match.group(1) if handle_match else None
            return caption, owner
        except:
            return None, None
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

    # 3. PENYELENGGARA (Host + @Mentions + Collabs)
    found_hosts = set()
    if owner_handle:
        found_hosts.add(f"@{owner_handle}")
    
    # URL Handle extraction fallback
    url_handle = re.search(r"instagram\.com/([^/]+)", url)
    if url_handle and url_handle.group(1) not in ['p', 'reels', 'tv']:
        found_hosts.add(f"@{url_handle.group(1)}")

    # Mentions & Collabs
    mentions = re.findall(r'@([\w.]+)', caption)
    found_hosts.update([f"@{m}" for m in mentions])
    
    collab_matches = re.findall(r"([@\w\s]+)\s+[xX]\s+([@\w\s]+)", caption)
    for match in collab_matches:
        for name in match:
            n = name.strip()
            if len(n) > 2: found_hosts.add(n)

    penyelenggara = ", ".join(sorted(found_hosts))

    # 4. LOCATION (Expanded keywords)
    location = ""
    loc_keys = ["📍", "location:", "lokasi:", "area:", "at:", "place:", "venue:"]
    for l in lines:
        if any(k in l.lower() for k in loc_keys):
            location = re.sub(r'(?i)location:|lokasi:|area:|at:|place:|venue:|📍', '', l).strip()
            break

    # 5. REGISTRATION / FREE
    reg_link = "-"
    if any(f in caption.upper() for f in ["FREE", "GRATIS", "HTM: 0", "RP 0"]):
        reg_link = "FREE"

    # Proximity search for link near registration keywords
    kw_pattern = r"(?i)(?:link|htm|daftar|regis|tiket|ticket|pendaftaran|bit\.ly|form).*?(https?://[^\s]+)"
    link_match = re.search(kw_pattern, caption, re.DOTALL)
    
    if link_match:
        reg_link = link_match.group(1)
    else:
        # Fallback to any link
        any_l = re.search(r'(https?://[^\s]+)', caption)
        if any_l: reg_link = any_l.group(1)

    return [event_date, event_title, penyelenggara, location, reg_link, url]

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Temu Pekan", page_icon="💗")

st.markdown("""
<style>
    .stApp { background-color: #D84565; color: white; }
    .main-card { background: white; padding: 20px; border-radius: 15px; color: #333; }
</style>
""", unsafe_allow_html=True)

st.title("💗 Bertemu Djakarta Auto-Parser")

with st.container():
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    url_input = st.text_input("Paste Instagram URL 👇")
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 Fetch & Save to Sheet"):
    if url_input:
        with st.spinner("Trying to fetch from Instagram..."):
            caption, owner = fetch_ig_caption(url_input)
            
        if not caption:
            st.error("Instagram is blocking the automated request. 🚧")
            # Creating a manual fallback so you can still work
            caption = st.text_area("Please paste the caption manually to parse:")
        
        if caption:
            service = get_g_service()
            if service:
                row = parse_all_fields(caption, url_input, owner)
                service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:F",
                    valueInputOption="USER_ENTERED", body={"values": [row]}
                ).execute()
                st.success("✅ Saved!")
                st.table({"Date": row[0], "Title": row[1], "Host": row[2], "Loc": row[3], "Reg": row[4]})
