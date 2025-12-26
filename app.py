import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st

from google.oauth2 import service_account
from googleapiclient.discovery import build


# ===================== EDIT THESE =====================
SERVICE_ACCOUNT_FILE = "bdj-events-c7fce9e830db.json"
SPREADSHEET_ID = "1FNotGZKUXw3iU6qaqKyadRaQMYSQr65KSIonlwH-CZE"
SHEET_NAME = "Sheet1"
# ======================================================


# ---------- GOOGLE SHEETS CONNECTION ----------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()


# ---------- STYLING ----------
st.markdown("""
<style>
.stApp { background-color: #D84565; }

h1 { color:#D63384 !important; }

.bdj-card {
    background:white;
    padding:18px;
    border-radius:18px;
    box-shadow:0 4px 12px rgba(214,51,132,0.18);
    border:1px solid #FFD1E8;
}

.pink-button button{
    background:#D84565!important;
    color:white!important;
    border-radius:12px!important;
}

.pink-button button:hover{
    background:#BDE040!important;
}
</style>
""", unsafe_allow_html=True)


# ---------- DATE ----------
def extract_event_date(caption):
    month_map = {
        "jan":"01","january":"01",
        "feb":"02","february":"02","februari":"02",
        "mar":"03","march":"03","maret":"03",
        "apr":"04","april":"04",
        "may":"05","mei":"05",
        "jun":"06","june":"06",
        "jul":"07","july":"07",
        "aug":"08","august":"08","agustus":"08",
        "sep":"09","september":"09",
        "oct":"10","oktober":"10","october":"10",
        "nov":"11","november":"11",
        "dec":"12","december":"12","desember":"12",
    }

    caption = caption.lower()
    patterns = [
        r"(\d{1,2})\s+([a-z]+)\s+(\d{2,4})",
        r"(\d{1,2})\s+([a-z]+)",
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})"
    ]

    for pat in patterns:
        m = re.search(pat, caption)
        if not m:
            continue

        g = m.groups()

        if len(g) == 3 and g[1].isalpha():
            day = int(g[0])
            month = month_map.get(g[1][:3], "01")
            year = int(g[2])
        elif len(g) == 2 and g[1].isalpha():
            day = int(g[0])
            month = month_map.get(g[1][:3], "01")
            year = datetime.today().year
        else:
            day = int(g[0])
            month = int(g[1])
            year = int(g[2]) if len(g[2]) == 4 else 2000 + int(g[2])

        return f"{year:04d}-{month}-{day:02d}"

    return ""


# ---------- TITLE ----------
def extract_event_title(caption):
    lines = [l.strip() for l in caption.split("\n") if l.strip()]

    for l in lines:
        if re.search(r'\b(title|tema|theme)\b', l, re.IGNORECASE):
            return re.sub(r'(?i)\b(title|tema|theme)\b[:\-–]*','',l).strip()

    for l in lines:
        m = re.search(r'\*\*(.+?)\*\*', l)
        if m:
            return m.group(1).strip()

    for l in lines:
        if l.isupper() and 4 <= len(l) <= 70:
            return l

    for l in lines:
        if not l.startswith("#"):
            return l

    return ""


# ---------- SCRAPE IG ----------
def get_instagram_data(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    caption = ""
    m = re.search(
        r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.*?)"\}\}\]\}',
        res.text, re.S
    )
    if m:
        caption = m.group(1).encode("utf-8").decode("unicode_escape")

    event_date = extract_event_date(caption)
    event_title = extract_event_title(caption)

    handles = re.findall(r'@[\w.]+', caption)
    penyelenggara = ", ".join(sorted(set(handles))) if handles else ""

    location = ""
    for l in caption.split("\n"):
        if "📍" in l:
            location = l.replace("📍","").strip()
            break

    registration_link = ""
    if re.search(r'\bfree\b', caption, re.IGNORECASE):
        registration_link = "Free"
    else:
        link = re.search(r'(https?://[^\s]+)', caption)
        if link:
            registration_link = link.group(1)

    return [
        event_date,
        event_title,
        penyelenggara,
        location,
        registration_link,
        url
    ]


# ---------- WRITE TO SHEET ----------
def append_to_sheet(row):
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F",
        valueInputOption="RAW",
        body={"values":[row]},
    ).execute()


# ---------- UI ----------
st.title("🩷 BDJ Event Extractor (Auto-Sheet)")

st.markdown('<div class="bdj-card">', unsafe_allow_html=True)
url = st.text_input("Paste Instagram link here 👇")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="pink-button">', unsafe_allow_html=True)
clicked = st.button("Extract & Save to Sheet ✨")
st.markdown('</div>', unsafe_allow_html=True)


if clicked:

    if not url:
        st.warning("Masukin link dulu ya 🌷")
    else:
        try:
            row = get_instagram_data(url)
            append_to_sheet(row)

            st.success("💗 Success! Added to Google Sheet. Don't forget to re-check!!")
            st.write({
                "Event Date": row[0],
                "Event Title": row[1],
                "Penyelenggara": row[2],
                "Location": row[3],
                "Registration Link": row[4],
                "Source": row[5]
            })

        except Exception as e:
            st.error(f"⚠️ Something went wrong: {e}")
