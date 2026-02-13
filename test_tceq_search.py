import requests
from bs4 import BeautifulSoup

url = "https://records.tceq.texas.gov/cs/idcplg"

# Construct the search query
# Note: The browser agent found that 'xRecordSeries' is 1081 for AIR/New Source Review Permit
query_text = "dSecurityGroup <matches> 'Public' <AND> xRecordSeries <matches> '1081' <AND> (xRefNumTxt <substring> 'RN100223445') <AND> (dDocTitle <substring> 'Technical Review')"

payload = {
    "IdcService": "GET_SEARCH_RESULTS",
    "QueryText": query_text,
    "ResultCount": 20,
    "SortField": "dInDate",
    "SortOrder": "Desc",
    "ResultTemplate": "StandardResults" # Guessed, but common
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

try:
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Check for result table rows
    print(f"Status Code: {response.status_code}")
    rows = soup.find_all('tr')
    print(f"Found {len(rows)} table rows (including header/footer)")
    
    found_technical_review = False
    for row in rows:
        text = row.get_text()
        if "Technical Review" in text:
            print("Found 'Technical Review' in a row!")
            found_technical_review = True
            # Try to find the Content ID link
            link = row.find('a', href=True)
            if link and 'dID=' in link['href']:
                print(f"Sample Link: {link['href']}")
            break
            
    if not found_technical_review:
        print("Did not find 'Technical Review' in the results.")
        # Print a snippet of the response to debug
        print(soup.prettify()[:1000])

except Exception as e:
    print(f"Error: {e}")
