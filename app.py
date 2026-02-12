import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Base URL for TCEQ search
BASE_URL = "https://records.tceq.texas.gov/cs/idcplg"

def get_configured_session():
    """
    Creates a requests Session with robust retry logic and browser-like headers.
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=10,  # Significantly increased retries
        backoff_factor=5,  # Aggressive backoff (5s, 10s, 20s...)
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Browser-like headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    return session

def search_tceq(rn_number):
    """
    Search TCEQ records for a given RN.
    Returns the response object.
    """
    params = {
        "IdcService": "TCEQ_PERFORM_SEARCH",
        "xRecordSeries": "1081",  # AIR / New Source Review Permit
        "select0": "xRefNumTxt",  # Central Registry RN
        "input0": rn_number,
        "ResultCount": "20",      # Start with fewer results
        "xIdcProfile": "Record",
        "IsExternalSearch": "1",
        "newSearch": "true",
        "SortField": "dInDate",
        "SortOrder": "Desc"
    }
    
    try:
        session = get_configured_session()
        
        # Visit search page first to mimic a real user and get cookies
        # Use a proper timeout
        session.get("https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_SEARCH", timeout=30)
        
        # Add a random delay to mimic human behavior
        import random
        time.sleep(random.uniform(2, 5))
        
        # Update Referer for the search action
        session.headers.update({
            "Referer": "https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_SEARCH",
            "Origin": "https://records.tceq.texas.gov"
        })
        
        # Use POST request
        response = session.post(BASE_URL, data=params, timeout=60)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to TCEQ: {e}")
        return None

def parse_results(html_content):
    """
    Parse the HTML response from TCEQ search.
    Returns a list of dictionaries with document details.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []

    # Find the main results table.
    rows = soup.find_all('tr')
    
    header_map = {}
    header_row = soup.find('tr', class_='xuiListHeaderRow')
    if header_row:
        cols = header_row.find_all(['th', 'td'])
        for idx, col in enumerate(cols):
            header_text = col.get_text(strip=True)
            header_map[header_text] = idx
            
    # Fallback header map if detection failed but we have rows
    # Based on typical TCEQ layout: 
    # 0: Select, 1: Content ID, 2: Record Series, 3: Primary ID, 4: Secondary ID, 5: Doc Type, 6: Title, 7: Begin Date, etc.
    
    for row in rows:
        if not (row.has_attr('class') and any('xuiListContent' in c for c in row['class'])):
            continue
            
        cols = row.find_all('td')
        if not cols:
            continue
            
        # Helper to get text safely
        def get_col_text(idx):
            return cols[idx].get_text(strip=True) if idx is not None and len(cols) > idx else ""

        # Link/ID
        link_tag = cols[1].find('a') if len(cols) > 1 else None
        doc_id = link_tag.get_text(strip=True) if link_tag else "Unknown"
        download_url = urljoin(BASE_URL, link_tag['href']) if link_tag else None
        
        # Document Type
        doctype_idx = header_map.get('Document Type')
        if doctype_idx is None:
             # Guessing index 5
             doctype_idx = 5
        doctype = get_col_text(doctype_idx)

        # Title
        title_idx = header_map.get('Title')
        if title_idx is None: 
            # Guessing index 6 based on observation
            title_idx = 6
        title = get_col_text(title_idx)
        
        # Date
        date_idx = header_map.get('Begin Date') or header_map.get('Date Received')
        if date_idx is None:
            # Guessing index 7
            date_idx = 7
        date_str = get_col_text(date_idx)
        
        if download_url and "GET_FILE" in download_url:
            results.append({
                "Document ID": doc_id,
                "Document Type": doctype,
                "Title": title,
                "Date": date_str,
                "Download URL": download_url
            })
            
    return results

def download_file(url, filename):
    try:
        session = get_configured_session()
        r = session.get(url, stream=True, timeout=120)  # Long timeout for downloads
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
        return True
    except Exception as e:
        return False

# Streamlit UI
st.set_page_config(page_title="TCEQ Tech Review Downloader", layout="wide")

st.title("TCEQ Technical Review Downloader")
st.markdown("""
This app searches for **"Technical Review"** documents for a specific **Central Registry RN** 
on the TCEQ Records Online database.
""")

# Sidebar
st.sidebar.header("Search Parameters")
rn_input = st.sidebar.text_input("Central Registry RN", value="RN100210517")
start_year = st.sidebar.number_input("Start Year", min_value=1900, max_value=2100, value=2010)
end_year = st.sidebar.number_input("End Year", min_value=1900, max_value=2100, value=2025)

# Initialize session state for search results
if "raw_search_results" not in st.session_state:
    st.session_state.raw_search_results = None

if st.button("Search Documents"):
    with st.spinner(f"Searching TCEQ Database for {rn_input}..."):
        response = search_tceq(rn_input)
        
        if response:
            data = parse_results(response.content)
            
            if not data:
                st.warning("No documents found for this RN.")
                st.session_state.raw_search_results = None
            else:
                st.session_state.raw_search_results = data
                st.success("Search complete!")

# Display and Filtering Logic
if st.session_state.raw_search_results:
    data = st.session_state.raw_search_results
    
    # Filter by Title and Year
    filtered_data = []
    for item in data:
        # Filter: Check if "Technical Review" is in Title OR Document Type
        # Case insensitive check
        text_to_check = (item.get('Title', '') + " " + item.get('Document Type', '')).lower()
        if "technical review" not in text_to_check:
            continue

        try:
            # Parse date. Formats can vary, often MM/DD/YYYY
            doc_year = None
            if item['Date']:
                parts = item['Date'].split('/')
                if len(parts) == 3:
                    doc_year = int(parts[2])
            
            if doc_year and start_year <= doc_year <= end_year:
                 filtered_data.append(item)
            elif not doc_year:
                 # Include unknown dates?
                 pass
        except ValueError:
            pass
    
    if filtered_data:
        st.info(f"Showing {len(filtered_data)} documents matching criteria (Found {len(data)} total).")
        df = pd.DataFrame(filtered_data)
        
        # Display table
        st.dataframe(df[['Document ID', 'Document Type', 'Title', 'Date']], use_container_width=True)
        
        # Create downloads directory
        import os
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        # Download All Button
        if st.button("Download All Found Documents"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, doc in enumerate(filtered_data):
                safe_title = "".join([c for c in doc['Title'] if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                filename = f"downloads/{doc['Date'].replace('/', '-')}_{safe_title}_{doc['Document ID']}.pdf"
                
                status_text.text(f"Downloading {filename}...")
                success = download_file(doc['Download URL'], filename)
                
                if not success:
                    st.error(f"Failed to download {doc['Document ID']}")
                
                # Be polite to the server
                time.sleep(1)
                
                progress_bar.progress((i + 1) / len(filtered_data))
            
            st.success(f"Download complete! Files saved to {os.path.abspath('downloads')}")
            
        # Individual Download Links
        st.markdown("### Direct Links")
        for index, row in df.iterrows():
            st.markdown(f"[{row['Document ID']} - {row['Title']}]({row['Download URL']})")
    else:
        st.warning(f"Found {len(data)} documents, but none matched 'Technical Review' in the year range {start_year}-{end_year}.")

