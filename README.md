# TCEQ Technical Review Downloader

A Streamlit application to search and download "Technical Review" documents from the Texas Commission on Environmental Quality (TCEQ) Records Online database.

## Features
- **Search by Central Registry RN**: Enter a specific RN to find relevant documents.
- **Filter by Year**: Specify a start and end year to narrow down results.
- **Download**: Directly download PDF documents found.

## Installation

1.  Clone this repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    streamlit run app.py
    ```

## Usage
- Enter a valid Central Registry Number (e.g., `RN100210517`).
- Set the Year Range.
- Click "Search Documents".
- Download key files as needed.

## Note on Errors
The application interacts with an external government database. Connecting to TCEQ servers may occasionally result in timeouts or 503 errors if the service is busy or down.
