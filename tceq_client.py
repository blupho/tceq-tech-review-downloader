import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse

class TCEQClient:
    BASE_URL = "https://records.tceq.texas.gov/cs/idcplg"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        })

    def _get_search_params(self):
        """
        Visit the search page and extract necessary hidden fields and accessID.
        Returns a dictionary of parameters.
        """
        try:
            response = self.session.get(f"{self.BASE_URL}?IdcService=TCEQ_SEARCH")
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            params = {}
            # Extract all hidden inputs
            for input_tag in soup.find_all('input', type='hidden'):
                if input_tag.get('name') and input_tag.get('value'):
                    params[input_tag['name']] = input_tag['value']
            
            # Ensure we have essential ones, if not, set defaults based on browser findings
            if 'IdcService' not in params:
                params['IdcService'] = 'TCEQ_PERFORM_SEARCH' 
            
            return params
        except Exception as e:
            print(f"Error initializing search session: {e}")
            return {}

    def search_technical_reviews(self, rn_number, start_date=None, end_date=None):
        """
        Search for Technical Review documents using TCEQ_PERFORM_SEARCH service and client-side filtering.
        """
        # Get baseParams from the search page
        search_params = self._get_search_params()
        
        # Override/Add specific search criteria
        search_params.update({
            "IdcService": "TCEQ_PERFORM_SEARCH",
            "xRecordSeries": "1081", # AIR / New Source Review Permit
            "select0": "xRefNumTxt",
            "input0": rn_number,
            "ftx": "Technical Review",
            "SortField": "dInDate",
            "SortOrder": "Desc",
            "ResultCount": 200,
            # Ensure these are present if scraping missed them
            "SearchQueryFormat": "Universal", 
            "IsExternalSearch": "1"
        })
        
        # Add Referer header which is often required for search actions
        headers = {
            "Referer": f"{self.BASE_URL}?IdcService=TCEQ_SEARCH"
        }
        
        try:
            response = self.session.post(self.BASE_URL, data=search_params, headers=headers)
            response.raise_for_status()
            
            all_results = self._parse_results(response.content)
            
            # Client-side Date Filtering
            filtered_results = []
            for doc in all_results:
                if not doc.get('date'):
                    filtered_results.append(doc)
                    continue
                    
                try:
                    # Date format is typically MM/DD/YYYY
                    doc_date = datetime.strptime(doc['date'], '%m/%d/%Y')
                    
                    if start_date and doc_date < start_date:
                        continue
                    if end_date and doc_date > end_date:
                        continue
                        
                    filtered_results.append(doc)
                    
                except ValueError:
                    # If date parse fails, include it (safe default) or log warning
                    filtered_results.append(doc)
            
            return filtered_results

        except Exception as e:
            print(f"Error executing search: {e}")
            return []

    def _parse_results(self, content):
        soup = BeautifulSoup(content, 'html.parser')
        results = []
        
        # TCEQ results are usually in a table. We need to identify the correct table.
        # Often it involves looking for specific headers or iterating through rows.
        
        # Helper to find the table with results
        # This is heuristic based on standard Oracle Content Server layouts
        tables = soup.find_all('table')
        result_table = None
        for table in tables:
            if table.find('th') and "Title" in table.get_text():
                result_table = table
                break
        
        if not result_table:
            # Fallback: Look for rows directly if table structure is messy
            rows = soup.find_all('tr')
        else:
            rows = result_table.find_all('tr')

        for row in rows:
            # Skip header rows
            if row.find('th'):
                continue
                
            cells = row.find_all('td')
            if not cells:
                continue
                
            # We need to extract: Title, Content ID (for link), Date
            # The column order might vary, so we look for links and text
            
            text_content = row.get_text(separator=' ', strip=True)
            if "Technical Review" not in text_content:
                continue

            doc_info = {}
            
            # Extract Link and Content ID
            link_tag = row.find('a', href=True)
            if link_tag:
                href = link_tag['href']
                doc_info['url'] = urllib.parse.urljoin(self.BASE_URL, href)
                doc_info['title'] = link_tag.get_text(strip=True)
                
                # Extract dID if possible for robust linking
                # href usually looks like ...?IdcService=GET_FILE&dID=12345...
                parsed_url = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed_url.query)
                if 'dID' in params:
                    doc_info['dID'] = params['dID'][0]
            
            # Try to find date
            # It's usually in one of the cells. We can match a regex or just take the last cell often.
            # For now, let's just store the full text row as snippet if we can't parse perfectly
            doc_info['raw_text'] = text_content
            
            # Heuristic for date: look for MM/DD/YYYY format in cells
            import re
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', text_content)
            if date_match:
                doc_info['date'] = date_match.group(0)
            
            if 'url' in doc_info:
                results.append(doc_info)
                
        return results
