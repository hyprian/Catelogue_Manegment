# scrapers/amazon_enrichment.py
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random
from datetime import datetime
import sys
import os
import logging
import json

# --- Add project root to the Python path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from connectors.baserow_connector import BaserowConnector
from utils.config_loader import APP_CONFIG

# --- 1. CONFIGURATION ---
BASE_URL = "https://www.amazon.in/dp/"
LOG_DIR = os.path.join(project_root, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'enrichment_run.json')

# --- Custom JSON Logger Setup ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {"timestamp": self.formatTime(record, self.datefmt), "level": record.levelname, "message": record.getMessage()}
        if hasattr(record, 'extra_data'): log_record.update(record.extra_data)
        return json.dumps(log_record)

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): logger.handlers.clear()
    file_handler = logging.FileHandler(LOG_FILE); file_handler.setFormatter(JsonFormatter()); logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(); console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')); logger.addHandler(console_handler)

# --- 2. SELENIUM WEBDRIVER SETUP ---
def setup_driver():
    logging.info("Setting up headless Chrome driver...")
    options = Options()
    options.add_argument("--headless=new")
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    try:
        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logging.info("Driver setup successful.")
        return driver
    except Exception as e:
        logging.error("!!! DRIVER SETUP FAILED", extra={'extra_data': {'error': str(e)}})
        return None

# --- 3. DATA SCRAPING FUNCTION ---
def scrape_product_page(driver, asin):
    url = BASE_URL + asin
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    scraped_data = {'ASIN': asin}
    try: scraped_data['Title'] = wait.until(EC.presence_of_element_located((By.ID, 'productTitle'))).text.strip()
    except Exception: scraped_data['Title'] = None
    try: scraped_data['Brand'] = driver.find_element(By.ID, 'bylineInfo').text.strip()
    except Exception: scraped_data['Brand'] = None
    try:
        price_whole = driver.find_element(By.CSS_SELECTOR, '.a-price-whole').text.strip()
        price_symbol = driver.find_element(By.CSS_SELECTOR, '.a-price-symbol').text.strip()
        scraped_data['Price'] = f"{price_symbol}{price_whole}"
    except Exception: scraped_data['Price'] = None
    try: scraped_data['Rating'] = driver.find_element(By.ID, 'acrPopover').get_attribute('title').strip()
    except Exception: scraped_data['Rating'] = None
    try: scraped_data['Review Count'] = driver.find_element(By.ID, 'acrCustomerReviewText').text.strip()
    except Exception: scraped_data['Review Count'] = None
    try:
        bullets = driver.find_element(By.ID, 'feature-bullets').find_elements(By.TAG_NAME, 'li')
        scraped_data['Bullet Points'] = '\n'.join([b.text.strip() for b in bullets if b.text.strip()])
    except Exception: scraped_data['Bullet Points'] = None
    try:
        thumbs = driver.find_elements(By.CSS_SELECTOR, 'li.thumbnail img')
        urls = {t.get_attribute('src').split('._')[0] + '._AC_SL1500_.jpg' for t in thumbs}
        scraped_data['Image URLs'] = ', '.join(list(urls)) if urls else None
    except Exception: scraped_data['Image URLs'] = None
    try: scraped_data['Product Description'] = driver.find_element(By.ID, 'productDescription').text.strip()
    except Exception: scraped_data['Product Description'] = None
    scraped_data['Status'] = 'Active'
    return scraped_data

# --- 4. MAIN EXECUTION LOGIC ---
def main():
    start_time = datetime.now()
    logging.info("🚀 Starting the Automated Catalog Enrichment Process...")
    
    baserow_config = APP_CONFIG.get('baserow', {})
    table_id = baserow_config.get('catalogue_table_id')
    if not table_id:
        logging.error("'catalogue_table_id' not found in configuration."); return

    connector = BaserowConnector(api_token=baserow_config['api_token'], base_url=baserow_config['base_url'])
    catalogue_df = connector.get_table_as_dataframe(table_id)
    
    if catalogue_df.empty:
        logging.warning("Catalogue table is empty. No ASINs to process."); return

    asins_to_scrape = catalogue_df[catalogue_df['Marketplace ASIN/Product ID'].notna()].copy()
    logging.info(f"Found {len(asins_to_scrape)} listings with ASINs to process.")
    
    driver = setup_driver()
    if driver is None: return

    updates_to_send = []
    failed_asins = []
    
    # --- First Pass Scraping ---
    for i, row in asins_to_scrape.iterrows():
        baserow_id, asin = row['id'], row['Marketplace ASIN/Product ID']
        logging.info(f"Scraping (Pass 1) [{i+1}/{len(asins_to_scrape)}] for ASIN: {asin}")
        try:
            product_data = scrape_product_page(driver, asin)
            if product_data.get('Title'):
                product_data['id'] = baserow_id
                product_data['Enrichment Status'] = 'Success'
                updates_to_send.append(product_data)
            else: raise ValueError("Scrape returned no title.")
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logging.warning(f"Could not scrape ASIN {asin} on first pass.", extra={'extra_data': {'asin': asin, 'error': str(e)}})
            failed_asins.append({'id': baserow_id, 'ASIN': asin})
            continue

    # --- Retry Pass for Failed ASINs ---
    if failed_asins:
        logging.info(f"--- Retrying {len(failed_asins)} failed ASINs ---")
        for i, item in enumerate(failed_asins):
            baserow_id, asin = item['id'], item['ASIN']
            logging.info(f"Scraping (Pass 2) [{i+1}/{len(failed_asins)}] for ASIN: {asin}")
            try:
                product_data = scrape_product_page(driver, asin)
                if product_data.get('Title'):
                    product_data['id'] = baserow_id
                    product_data['Enrichment Status'] = 'Success (on retry)'
                    updates_to_send.append(product_data)
                else: raise ValueError("Retry scrape returned no title.")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logging.error(f"Failed to scrape ASIN {asin} on second pass.", extra={'extra_data': {'asin': asin, 'error': str(e)}})
                updates_to_send.append({'id': baserow_id, 'Enrichment Status': 'Scrape Failed'})

    logging.info("✅ Scraping process finished. Closing the browser.")
    driver.quit()

    # --- Final Step: Prepare and Update Baserow ---
    if updates_to_send:
        final_payload = []
        for update in updates_to_send:
            payload_item = {'id': update['id'], 'Enrichment Status': update.get('Enrichment Status'), 'Last Enriched At': datetime.now().isoformat()}
            
            # This mapping ensures we only send data for columns that were successfully scraped
            key_mapping = {'Status': 'Listing Status', 'Title': 'Title', 'Brand': 'Brand', 'Price': 'Price', 'Rating': 'Rating', 'Review Count': 'Review Count', 'Bullet Points': 'Bullet Points', 'Product Description': 'Product Description'}
            for scraped_key, baserow_key in key_mapping.items():
                if update.get(scraped_key): payload_item[baserow_key] = update[scraped_key]
            
            if update.get('Image URLs'):
                payload_item['All Image URLs'] = update['Image URLs']
                payload_item['Product Image 1'] = update['Image URLs'].split(',')[0].strip()
            
            final_payload.append(payload_item)
        
        logging.info(f"Sending {len(final_payload)} updates to Baserow...")
        if connector.update_rows(table_id, final_payload):
            logging.info("✅ Success! Baserow has been updated.")
        else:
            logging.error("❌ Failed to update Baserow.")
    else:
        logging.info("No new data to update in Baserow.")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Enrichment process finished. Total runtime: {duration:.2f} seconds", extra={'extra_data': {'duration_seconds': duration, 'successful_updates': len(updates_to_send)}})

if __name__ == "__main__":
    setup_logging()
    if "error" not in APP_CONFIG:
        main()
    else:
        logging.error("Could not start script due to config error.", extra={'extra_data': {'error': APP_CONFIG['error']}})