import requests
from bs4 import BeautifulSoup

url = "https://records.tceq.texas.gov/cs/idcplg"

payload = {
    "IdcService": "TCEQ_SEARCH",
    "xRecordSeries": "1081",
    "select0": "xRefNumTxt",
    "input0": "RN100223445",
    "ftx": "Technical Review",
    "SortField": "dInDate",
    "SortOrder": "Desc",
    "ResultCount": 20
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

try:
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    
    print(f"Status: {response.status_code}")
    print(f"Content Length: {len(response.content)}")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Check title
    print(f"Page Title: {soup.title.string.strip() if soup.title else 'No Title'}")
    
    # Check for specific results
    rows = soup.find_all('tr')
    for row in rows:
        if "Technical Review" in row.get_text():
            print(f"Row text: {row.get_text(separator=' ', strip=True)[:100]}...")
            links = row.find_all('a', href=True)
            if not links:
                print("  No links in this row.")
            for link in links:
                if 'dID=' in link['href']:
                    print(f"Link: {link['href']}")
                else:
                    print(f"  Other Link: {link['href']}")
                    
except Exception as e:
    print(e)
