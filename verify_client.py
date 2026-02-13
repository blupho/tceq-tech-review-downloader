from tceq_client import TCEQClient
import datetime

client = TCEQClient()
rn = "RN100223445"

print(f"Searching for {rn}...")
results = client.search_technical_reviews(rn)

print(f"Found {len(results)} results.")
for res in results:
    print(f"Title: {res.get('title', 'N/A')}")
    print(f"Date: {res.get('date', 'N/A')}")
    print(f"URL: {res.get('url', 'N/A')}")
    print("-" * 40)
