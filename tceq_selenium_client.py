import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime
from bs4 import BeautifulSoup

class TCEQSeleniumClient:
    BASE_URL = "https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_SEARCH"

    def __init__(self, headless=True):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Check for system-installed Chromium and ChromeDriver (common in Streamlit Cloud)
        system_chromium = "/usr/bin/chromium"
        system_chromedriver = "/usr/bin/chromedriver"
        
        if os.path.exists(system_chromium) and os.path.exists(system_chromedriver):
            print(f"Using system binaries: {system_chromium} and {system_chromedriver}")
            options.binary_location = system_chromium
            service = Service(system_chromedriver)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            print("Using webdriver_manager for Chrome...")
            # Use webdriver_manager to automatically handle driver installation
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
        self.wait = WebDriverWait(self.driver, 20) # 20 seconds explicit wait

    def close(self):
        if self.driver:
            self.driver.quit()

    def search(self, rn_number, start_date=None, end_date=None):
        """
        Perform a search using Selenium.
        Returns a list of dictionaries with document info.
        """
        try:
            print(f"Navigating to {self.BASE_URL}...")
            self.driver.get(self.BASE_URL)
            
            # 1. Select 'AIR / New Source Review Permit'
            print("Selecting Record Series...")
            record_series_select = self.wait.until(EC.presence_of_element_located((By.ID, "xRecordSeries")))
            Select(record_series_select).select_by_value("1081") # 1081 = AIR / New Source Review Permit
            
            # 1.5 Select 'Permits' in Document Type to narrow results
            print("Selecting 'Permits' Document Type...")
            try:
                # Wait for AJAX update
                time.sleep(1)
                doc_type_select = self.wait.until(EC.presence_of_element_located((By.ID, "xInsightDocumentType")))
                Select(doc_type_select).select_by_value("27") # 27 = Permits
            except Exception as e:
                print(f"Warning: Could not select 'Permits' doc type: {e}")

            # Wait for AJAX reload by checking if 'Central Registry RN' option appears in any select
            print("Waiting for AJAX reload (checking for 'Central Registry RN')...")
            target_select_xpath = "//select[contains(., 'Central Registry RN')]"
            
            try:
                target_select = self.wait.until(EC.presence_of_element_located((By.XPATH, target_select_xpath)))
                print(f"Found 'Central Registry RN' dropdown (ID: {target_select.get_attribute('id')}, Name: {target_select.get_attribute('name')}).")
            except Exception as e:
                print("Timeout waiting for 'Central Registry RN' dropdown.")
                # Fallback: try to find any first select that might be the criteria
                try:
                    target_select = self.driver.find_elements(By.TAG_NAME, "select")[3] 
                    print("Attempting fallback to 4th select for RN field.")
                except:
                    self.driver.save_screenshot("error_no_rn_dropdown.png")
                    return []

            # 2. Select 'Central Registry RN'
            Select(target_select).select_by_value("xRefNumTxt") 
            
            time.sleep(1) 
            
            # 3. Enter RN Number
            print(f"Entering RN: {rn_number}")
            try:
                rn_input = self.wait.until(EC.element_to_be_clickable((By.NAME, "input0")))
            except:
                try:
                    rn_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.wideInput")))
                except:
                    print("Could not find RN input.")
                    return []
            
            rn_input.clear()
            rn_input.send_keys(rn_number)
            
            # 4. Enter 'Technical Review' in Quick Search (ftx)
            print("Entering 'Technical Review' in keyword search (ftx)...")
            try:
                # Use a specific CSS selector to skip hidden input with same name
                search_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ftx'][type='text']")))
                search_input.clear()
                search_input.send_keys("Technical Review")
            except Exception as e:
                print(f"Could not find visible 'ftx' input: {e}")
                try:
                    search_input = self.driver.find_element(By.ID, "MiniSearchText")
                    search_input.clear()
                    search_input.send_keys("Technical Review")
                except:
                    print("Could not find any search keyword input.")

            # 4.5 Try to set ResultCount to 200 to get more results per page
            try:
                # Set all ResultCount fields to 200 just in case
                self.driver.execute_script("""
                    document.querySelectorAll("input[name='ResultCount']").forEach(i => i.value = '200');
                """)
                print("Set ResultCount to 200.")
            except:
                pass
                
            # 5. Click Search
            print("Clicking Search...")
            try:
                search_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "(//button[contains(text(), 'Search')])[last()]")))
                search_btn.click()
            except:
                try:
                    search_btn = self.driver.find_element(By.XPATH, "//input[@type='submit' and @value='Search']")
                    search_btn.click()
                except:
                    print("Could not find any Search button.")
                    return []
            
            # 6. Parse Results
            print("Waiting for results...")
            time.sleep(3) 
            
            self.driver.save_screenshot("search_results_page.png")
            
            results = []
            
            # Pagination loop
            page_num = 1
            while True:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                page_text = soup.get_text()
                
                if "No search results" in page_text:
                    print(f"No results found on page {page_num}.")
                    break
                    
                # Find specific results table
                try:
                    # Use BeautifulSoup for faster parsing of the table if rows are many
                    results_table = soup.find('table', id='table_0')
                    if not results_table:
                        print(f"Could not find results table (id='table_0') on page {page_num}.")
                        break
                        
                    rows = results_table.find_all('tr')
                    print(f"Parsing page {page_num}: Found {len(rows)} rows in results table.")
                except Exception as e:
                    print(f"Error finding results table on page {page_num}: {e}")
                    break
                
                # Identify column indices from header
                header_cells = rows[0].find_all(['th', 'td'])
                header_texts = [h.get_text(strip=True) for h in header_cells]
                
                try:
                    title_idx = header_texts.index('Title')
                except ValueError:
                    title_idx = 12 # Fallback
                
                try:
                    # Prefer 'Begin Date' or just 'Date'
                    date_idx = header_texts.index('Begin Date')
                except ValueError:
                    try:
                        date_idx = header_texts.index('Date')
                    except ValueError:
                        date_idx = 14 # Fallback
                
                # Skip header row
                for row in rows[1:]:
                    try:
                        cols = row.find_all('td')
                        if len(cols) <= max(title_idx, date_idx):
                            continue
                            
                        title = cols[title_idx].get_text(strip=True)
                        date_str = cols[date_idx].get_text(strip=True)
                        
                        # STRICT FILTERING: Only include if "Technical Review" is in the title
                        if "technical review" not in title.lower():
                            continue
                            
                        # Extract Link - try Content ID column (index 2) or any link
                        link_tag = row.find('a', href=True)
                        href = link_tag['href'] if link_tag else ""
                        if href and not href.startswith('http'):
                            href = "https://records.tceq.texas.gov" + href
                            
                        doc_date = None
                        if date_str:
                            try:
                                date_part = date_str.split()[0]
                                doc_date = datetime.strptime(date_part, "%m/%d/%Y")
                            except:
                                pass
                                
                        # Filter by date range
                        if start_date and doc_date and doc_date < start_date:
                            continue
                        if end_date and doc_date and doc_date > end_date:
                            continue
                            
                        results.append({
                            "title": title,
                            "url": href,
                            "date": date_str
                        })
                        
                    except Exception as e:
                        print(f"Error parsing row: {e}")
                        continue
                
                # Check for Next Page
                try:
                    # Robust selector for Next button: an 'a' tag with an 'img' that has alt 'Link To More Results'
                    next_buttons = self.driver.find_elements(By.XPATH, "//a[img[@alt='Link To More Results']]")
                    if next_buttons:
                        # Click the last one (usually bottom) or first (usually top)
                        next_link = next_buttons[-1]
                        print(f"Navigating to page {page_num + 1}...")
                        next_link.click()
                        page_num += 1
                        time.sleep(3) # Wait for page load
                    else:
                        print(f"No 'Next' button found on page {page_num}. Ending pagination.")
                        break
                except Exception as e:
                    print(f"Ending pagination on page {page_num}: {e}")
                    break
                        
            return results

        except Exception as e:
            print(f"Selenium Error: {e}")
            self.driver.save_screenshot("selenium_error.png")
            return []
