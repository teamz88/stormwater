from playwright.sync_api import sync_playwright
import time
import os
import json
import requests
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import logging
import argparse
from ntfybro import NtfyNotifier
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Parse command line arguments
parser = argparse.ArgumentParser(description='Stormwater reports scraper')
parser.add_argument('--date', type=str, help='Target date in ISO format (YYYY-MM-DD). If not provided, uses latest date from reports.')
args = parser.parse_args()

# Validate date format if provided
target_date = None
if args.date:
    try:
        datetime.strptime(args.date, '%Y-%m-%d')
        target_date = args.date
        logging.info(f"Using custom target date: {target_date}")
    except ValueError:
        logging.error(f"Invalid date format: {args.date}. Please use YYYY-MM-DD format.")
        exit(1)
else:
    logging.info("No custom date provided, will use latest date from reports")

# Initialize notification system
notifier = NtfyNotifier(
    server_url="https://ntfy.hvacvoice.com",
    default_topic="stormwater",
    default_icon="https://stormwaterpro.compli.cloud/images/faviconx2.png"
)

def check_login_required(page):
    """Check if login form is present"""
    try:
        page.wait_for_selector("#i-username", timeout=5000)
        return True
    except:
        return False

def perform_login(page):
    """Perform the login process"""
    try:
        username_field = page.locator("#i-username")
        username_field.fill(os.getenv("STORMWATER_USERNAME"))

        password_field = page.locator("#i-password")
        password_field.fill(os.getenv("STORMWATER_PASSWORD"))

        # Submit the form
        login_button = page.locator("input[type='submit'], button[type='submit']")
        login_button.click()

        # Wait for navigation after login
        page.wait_for_load_state("networkidle")
        
        # Check if login was successful by looking for login form absence
        try:
            page.wait_for_selector("#i-username", timeout=3000)
            logging.error("Login failed - login form still present")
            notifier.send_error("Login failed - login form still present", "Authentication Error")
            return False
        except:
            logging.info("Login successful")
            return True
            
    except Exception as e:
        logging.error(f"Login error: {e}")
        notifier.send_error(f"Login error: {e}", "Login Failed")
        return False

def match_pdf_to_report(pdf_name, report):
    """Match PDF file to report based on rd_id in filename"""
    logging.debug(f"Matching PDF: '{pdf_name}' with report: '{report['site']}'")
    
    # Simple check: rd_id must be in PDF filename
    if 'rd_id' in report and report['rd_id'] and report['rd_id'] in pdf_name:
        logging.info(f"PDF '{pdf_name}' matched to report '{report['site']}' by rd_id: {report['rd_id']}")
        return True
    
    logging.debug(f"No rd_id match found for PDF '{pdf_name}' with report '{report['site']}'")
    return False

def send_error_to_n8n_webhook(error_message, error_type="general", additional_data=None):
    """Send error information to n8n webhook for monitoring"""
    webhook_url = os.getenv("N8N_ERROR_WEBHOOK_URL")
    if not webhook_url:
        logging.warning("N8N_ERROR_WEBHOOK_URL not set, skipping error webhook")
        return
    
    error_data = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
        "error_message": str(error_message),
        "script_name": "stormwater_scraper",
        "additional_data": additional_data or {}
    }
    
    try:
        response = requests.post(webhook_url, json=error_data, timeout=30)
        response.raise_for_status()
        logging.info(f"Error sent to n8n webhook: {error_type}")
    except Exception as e:
        logging.error(f"Failed to send error to n8n webhook: {e}")
        notifier.send_error(f"Failed to send error to n8n webhook: {e}", "Webhook Error")

def send_to_n8n_webhook(reports_data, downloads_dir, webhook_url):
    """Send all reports and their PDF files to n8n webhook in a single request"""
    try:
        # Prepare data and files for the webhook
        data = {'reports': json.dumps(reports_data)}  # All reports as JSON
        files = {}
        
        # List all available PDF files for debugging
        available_pdfs = list(downloads_dir.glob('*.pdf'))
        logging.info(f"Found {len(available_pdfs)} PDF files in downloads directory:")
        for pdf_path in available_pdfs:
            logging.info(f"  - {pdf_path.name}")
        
        # Match PDFs to reports - IMPROVED LOGIC
        pdf_matches = []
        
        # First pass: Try to match each report with the best PDF
        for report in reports_data:
            best_match = None
            best_score = 0
            
            logging.info(f"Trying to match report: {report['site']} ({report['date']})")
            
            for pdf_path in downloads_dir.glob('*.pdf'):
                if match_pdf_to_report(pdf_path.name, report):
                    # Calculate a simple score based on filename similarity
                    score = 1
                    if report['id'] in pdf_path.name:
                        score += 10  # Exact ID match gets highest priority
                    if report['site'].lower().replace(' ', '') in pdf_path.name.lower().replace(' ', ''):
                        score += 5   # Site name match gets high priority
                    if report['date'] in pdf_path.name:
                        score += 3   # Date match gets medium priority
                    
                    if score > best_score:
                        best_match = pdf_path
                        best_score = score
            
            if best_match:
                pdf_matches.append((report, best_match))
                logging.info(f"✓ Matched {best_match.name} to {report['site']} (score: {best_score})")
            else:
                logging.warning(f"✗ No PDF file found for: {report['site']} ({report['date']})")
        
        # Second pass: For reports without matches, try to find any available PDF
        unmatched_reports = [report for report in reports_data if not any(report == match[0] for match in pdf_matches)]
        used_pdfs = {match[1] for match in pdf_matches}
        unused_pdfs = [pdf for pdf in available_pdfs if pdf not in used_pdfs]
        
        if unmatched_reports and unused_pdfs:
            logging.info(f"Attempting fallback matching for {len(unmatched_reports)} unmatched reports with {len(unused_pdfs)} unused PDFs")
            for i, report in enumerate(unmatched_reports):
                if i < len(unused_pdfs):
                    pdf_path = unused_pdfs[i]
                    pdf_matches.append((report, pdf_path))
                    logging.info(f"🔄 Fallback matched {pdf_path.name} to {report['site']}")
        
        # Add matched PDFs to files dict with id_rd_id format
        for idx, (report, pdf_path) in enumerate(pdf_matches):
            # Create filename in id_rd_id format
            pdf_key = f"pdf_{report['id']}_{report['rd_id']}"
            files[pdf_key] = (pdf_path.name, open(pdf_path, 'rb'), 'application/pdf')
            logging.info(f"Prepared PDF for sending: {pdf_path.name} for {report['site']} with key: {pdf_key}")
        
        # Send the webhook request
        response = requests.post(webhook_url, data=data, files=files)
        
        if response.status_code == 200:
            logging.info("Successfully sent all reports and PDFs to n8n webhook")
            # Send success notification for webhook
            notifier.send_success(
                f"Successfully sent {len(pdf_matches)} reports with PDFs to n8n webhook",
                "Webhook Data Sent"
            )
        else:
            logging.error(f"Failed to send to n8n webhook. Status code: {response.status_code}")
            # Send error notification for webhook failure
            notifier.send_error(
                f"Failed to send data to n8n webhook. Status code: {response.status_code}",
                "Webhook Send Failed"
            )
        
        # Close all file handles
        for key in files:
            files[key][1].close()
            
    except Exception as e:
        logging.error(f"Error sending to n8n webhook: {e}")
        send_error_to_n8n_webhook(e, "webhook_send_error", {"webhook_url": webhook_url, "reports_count": len(reports_data) if 'reports_data' in locals() else 0})

# Check required environment variables
required_env_vars = ["STORMWATER_USERNAME", "STORMWATER_PASSWORD", "STORMWATER_REPORT_URL"]
for var in required_env_vars:
    if not os.getenv(var):
        error_msg = f"Error: Environment variable {var} is not set"
        logging.error(error_msg)
        notifier.send_error(error_msg, "Configuration Error")
        send_error_to_n8n_webhook(error_msg, "configuration_error", {"missing_variable": var})
        exit(1)

# Start Playwright
with sync_playwright() as p:
    # Launch browser with options similar to Chrome
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-gpu"
        ]
    )
    
    # Create context with download settings
    downloads_dir = Path.home() / 'Downloads'
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        accept_downloads=True
    )
    
    page = context.new_page()
    
    try:
        # Navigate to target URL
        target_url = os.getenv("STORMWATER_REPORT_URL", "https://stormwaterpro.compli.cloud/analytics/reports/created-by-period")
        page.goto(target_url)
        
        # Check if login is required
        if check_login_required(page):
            logging.info("Login form detected, starting login process...")
            if not perform_login(page):
                error_msg = "Login failed, terminating program..."
                logging.error(error_msg)
                notifier.send_error(error_msg, "Authentication Failed")
                send_error_to_n8n_webhook(error_msg, "authentication_error", {"url": target_url})
                browser.close()
                exit(1)
            
            # Navigate to target URL after login
            page.goto(target_url)
        else:
            logging.info("No login required, continuing...")
        
        # Wait for page to load completely after navigation
        page.wait_for_load_state("networkidle")
        
        # Log current URL for debugging
        logging.info(f"Current page URL: {page.url}")
        
        # Wait for data table to be present (this confirms we're on the right page)
        try:
            page.wait_for_selector("#dataTable_length", timeout=60000)
            logging.info("Data table found, page loaded successfully")
        except Exception as e:
            logging.error(f"Data table not found. Current URL: {page.url}")
            raise e
        
        # Set entries per page to 100
        select_element = page.locator("select[name='dataTable_length']")
        select_element.scroll_into_view_if_needed()
        time.sleep(0.5)  # Brief pause for scroll animation to complete
        select_element.select_option("100")
        
        # Wait for table to update
        page.wait_for_selector("#dataTable_processing[style*='display: none']", state="attached")
        
        logging.info(f"Page loaded successfully, entries set to 100: {page.url}")
        
        # Wait for table rows to be present
        page.wait_for_selector("#dataTable tbody tr")
        
        # Get all rows
        rows = page.locator("#dataTable tbody tr").all()
        
        # Determine which date to use for filtering
        if target_date:
            # Use custom date provided via command line
            filter_date = target_date
            logging.info(f"Filtering reports for custom date: {filter_date}")
        else:
            # Get the latest date from the first row (existing behavior)
            filter_date = rows[0].locator("td").nth(6).inner_text()
            logging.info(f"Using latest date from reports: {filter_date}")
        
        # Extract data from all rows with the target date (no uniqueness check)
        reports_data = []
        for row in rows:
            cells = row.locator("td").all()
            row_date = cells[6].inner_text()
            
            # Skip rows that don't match our target date
            if row_date != filter_date:
                continue
                
            site_link = cells[0].locator("a")
            report_def_link = cells[3].locator("a")
            
            # Extract rd_id from report_definition_url
            report_def_url = report_def_link.get_attribute("href")
            rd_id = report_def_url.split('/')[-1] if report_def_url else ""
            
            report = {
                "id": site_link.get_attribute("href").split('/')[-1],
                "site": cells[0].inner_text(),
                "site_url": site_link.get_attribute("href"),
                "program": cells[1].inner_text(),
                "report_type": cells[2].inner_text(),
                "report_definition": cells[3].inner_text(),
                "report_definition_url": report_def_url,
                "rd_id": rd_id,
                "site_tags": cells[4].inner_text(),
                "publishing_user": cells[5].inner_text(),
                "date": cells[6].inner_text(),
                "time": cells[7].inner_text()
            }
            reports_data.append(report)
        
        # Save reports data to JSON file
        with open('reports.json', 'w', encoding='utf-8') as f:
            json.dump(reports_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"Successfully saved {len(reports_data)} reports for {filter_date} to reports.json")
        
        # Send success notification
        notifier.send_success(
            f"Successfully scraped {len(reports_data)} reports for {filter_date}",
            "Stormwater Reports Scraped"
        )
        
        # Clean up old PDF files in Downloads
        if downloads_dir.exists():
            for pdf_file in downloads_dir.glob('*.pdf'):
                pdf_file.unlink()
            logging.info("Cleaned up old PDF files in Downloads")
        
        # Download PDFs
        logging.info("\nStarting PDF downloads...")
        for report in reports_data:
            try:
                logging.info(f"Starting download for {report['report_definition_url']}")
                page.goto(report['report_definition_url'])
                page.wait_for_load_state("networkidle")
                
                if check_login_required(page):
                    perform_login(page)
                    page.goto(report['report_definition_url'])
                
                # Wait for report to generate
                page.wait_for_selector("#report-generating", state="hidden", timeout=20000)
                
                # Try to find and click download button
                try:
                    download_button = page.locator("#downloadUrl")
                    download_button.scroll_into_view_if_needed()
                    time.sleep(0.5)  # Brief pause for scroll animation to complete
                    
                    # Start waiting for download before clicking
                    with page.expect_download() as download_info:
                        download_button.click()
                    
                    download = download_info.value
                    
                    # Create new filename with rd_id prefix
                    original_filename = download.suggested_filename
                    file_extension = Path(original_filename).suffix
                    new_filename = f"{report['rd_id']}_{original_filename}"
                    
                    # Save the download with new filename
                    download.save_as(downloads_dir / new_filename)
                    logging.info(f"PDF saved as: {new_filename} (original: {original_filename})")
                    
                    time.sleep(2)  # Wait for download to complete
                except Exception as e:
                    logging.warning(f"No download button found for {report['site']}: {e}")
                    notifier.send_error(f"No download button found for {report['site']}: {e}", "Download Button Missing")
                    
            except Exception as e:
                logging.error(f"Error downloading {report['site']}: {e}")
                notifier.send_error(f"Error downloading {report['site']}: {e}", "PDF Download Error")
                send_error_to_n8n_webhook(e, "download_error", {
                    "site": report['site'], 
                    "report_id": report['id'], 
                    "url": report['report_definition_url']
                })
        
        time.sleep(30)
        logging.info("\n================= PDF download process completed!")
    
        # Check if any PDF files were downloaded
        pdf_files = list(downloads_dir.glob('*.pdf')) if downloads_dir.exists() else []
        
        if pdf_files:
            logging.info(f"Found {len(pdf_files)} PDF files, proceeding with webhook")
            
            # Send data to n8n webhook if configured
            webhook_url = os.getenv("N8N_WEBHOOK_URL")
            if webhook_url:
                try:
                    send_to_n8n_webhook(reports_data, downloads_dir, webhook_url)
                except Exception as e:
                    logging.error(f"Error sending to n8n webhook: {e}")
                    notifier.send_error(f"Error sending to n8n webhook: {e}", "Webhook Send Error")
                    send_error_to_n8n_webhook(e, "webhook_error", {
                        "webhook_url": webhook_url, 
                        "reports_count": len(reports_data)
                    })
            else:
                logging.warning("N8N_WEBHOOK_URL environment variable not set")
        else:
            logging.warning("No PDF files found, skipping webhook send to n8n")
            notifier.send_error("No PDF files were downloaded, webhook not sent", "No PDFs Downloaded")
            
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        notifier.send_error(f"An error occurred: {e}", "General Application Error")
        send_error_to_n8n_webhook(e, "general_error", {
            "current_url": page.url if 'page' in locals() else "unknown"
        })
    finally:
        logging.info("Task completed! Browser will close in 60 seconds...")
        time.sleep(60)  # Delay before closing
        browser.close()
        
        logging.info("Browser closed successfully")