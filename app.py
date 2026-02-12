import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

# Base URL for TCEQ search
BASE_URL = "https://records.tceq.texas.gov/cs/idcplg"

def get_configured_session():
    """
    Creates a requests Session with robust retry logic and browser-like headers.
    Used for file downloads.
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Browser-like headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Connection": "keep-alive",
    })
    return session

def search_tceq(rn_number):
    """
    Search TCEQ records for a given RN using Selenium to bypass bot detection.
    Returns the page source (HTML string).
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Add a user agent just in case
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get("https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_SEARCH")
        
        # Select Record Series: AIR / New Source Review Permit (1081)
        # Use CSS selector to be safe
        select_series = Select(driver.find_element(By.CSS_SELECTOR, "select[name='xRecordSeries']"))
        select_series.select_by_value("1081") 
        
        # Select RN Search
        select0 = Select(driver.find_element(By.CSS_SELECTOR, "select[name='select0']"))
        select0.select_by_value("xRefNumTxt")
        
        # Enter RN
        # Find the visible input0
        inputs = driver.find_elements(By.NAME, "input0")
        target_input = None
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                target_input = inp
                break
        
        if target_input:
            target_input.clear()
            target_input.send_keys(rn_number)
            
            # Submit
            # Try finding submit button first
            submit_btns = driver.find_elements(By.XPATH, "//input[@type='submit' or @value='Search']")
            if submit_btns:
                submit_btns[0].click()
            else:
                target_input.submit()
            
            # Wait for results
            time.sleep(5) # Basic wait, could be improved with WebDriverWait
            
            return driver.page_source
        else:
            st.error("Could not find search input field on TCEQ page.")
            return None

    except Exception as e:
        st.error(f"Error connecting to TCEQ via Selenium: {e}")
        return None
    finally:
        if driver:
            driver.quit()

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
        # search_tceq now returns HTML string (page_source) or None
        html_content = search_tceq(rn_input)
        
        if html_content:
            data = parse_results(html_content)
            
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

