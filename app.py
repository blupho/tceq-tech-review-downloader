import streamlit as st
import pandas as pd
from tceq_selenium_client import TCEQSeleniumClient
from datetime import datetime

st.set_page_config(page_title="TCEQ Technical Review Downloader", layout="wide")

st.title("TCEQ Technical Review Document Downloader")
st.markdown("Automate the retrieval of Technical Review documents from TCEQ Records Online.")

# Sidebar for inputs
with st.sidebar:
    st.header("Search Criteria")
    rn_number = st.text_input("Central Registry RN", value="RN100223445", help="e.g., RN100223445")
    
    # Date Range
    today = datetime.now()
    # Default to last 5 years as per user habit, or just unrestricted? User said "date range to narrow down".
    start_date = st.date_input("Start Date", value=None)
    end_date = st.date_input("End Date", value=None)
    
    search_btn = st.button("Search Documents", type="primary")

if search_btn:
    if not rn_number:
        st.error("Please enter a Central Registry RN number.")
    else:
        status_text = st.empty()
        status_text.info("Starting Selenium Browser... (This may take a moment)")
        
        # Initialize client
        # We use session state to hold results if we want persistence, but simple run is fine
        try:
            with st.spinner("Searching TCEQ Database..."):
                client = TCEQSeleniumClient(headless=True)
                
                # Convert date inputs to datetime
                s_dt = datetime.combine(start_date, datetime.min.time()) if start_date else None
                e_dt = datetime.combine(end_date, datetime.max.time()) if end_date else None
                
                results = client.search(rn_number, s_dt, e_dt)
                client.close()
                
            status_text.empty()
            
            if not results:
                st.warning("No documents found matching the criteria.")
            else:
                st.success(f"Found {len(results)} documents.")
                
                # Create DataFrame
                df = pd.DataFrame(results)
                
                # Display standard table with links
                # We can use st.dataframe with LinkColumn config
                
                st.dataframe(
                    df,
                    column_config={
                        "url": st.column_config.LinkColumn("Download Link"),
                        "title": "Document Title",
                        "date": "Date"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f"An error occurred: {e}")
            if 'client' in locals():
                client.close()
