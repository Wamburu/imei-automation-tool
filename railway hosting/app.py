from flask import Flask, render_template, request, jsonify
import logging
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime, timedelta
import threading
import re
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('automation.log', encoding='utf-8')
    ]
)

# Create Flask app instance
app = Flask(__name__)

# Global variables to track progress and results
automation_progress = {
    'status': 'ready',
    'message': 'Ready to start',
    'progress': 0,
    'total': 0,
    'current_batch': 0,
    'total_batches': 0,
    'results': None,
    'error': None
}

class IMEIAutomation:
    def __init__(self, headless=True):  # Changed to True for Railway
        self.headless = headless
        self.driver = None
        self.results = {
            'not_active': [],
            'active_2_days': [],
            'active_3_15': [],
            'expired': [],
            'not_exist': [],
            'wrong_format': []
        }
        self.all_results_data = []
        
    def setup_driver(self):
        """Setup Chrome driver for Railway"""
        try:
            chrome_options = webdriver.ChromeOptions()
            
            # Railway-specific options
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")
            
            # Additional options for better stability
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set Chrome binary location for Railway
            chrome_options.binary_location = "/usr/bin/google-chrome"
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logging.info("Browser setup complete - RAILWAY MODE")
            return True
            
        except Exception as e:
            logging.error(f"Failed to setup browser: {str(e)}")
            return False

    def login(self, username, password):
        """Login to the system"""
        try:
            logging.info("Attempting login...")
            self.driver.get("https://sellin.oway-ke.com/user/login")
            
            # Wait for page to load
            time.sleep(3)
            
            # Find username field
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Username' or @name='username']"))
            )
            username_field.clear()
            username_field.send_keys(username)
            logging.info("Username entered")
            
            # Find password field
            password_field = self.driver.find_element(By.XPATH, "//input[@type='password']")
            password_field.clear()
            password_field.send_keys(password)
            logging.info("Password entered")
            
            # Find login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            logging.info("Login button clicked")
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login was successful
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                logging.error("Login failed - still on login page")
                return False
            
            logging.info("Login successful!")
            return True
            
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            return False

    def navigate_to_imei_tool(self):
        """Navigate to IMEI check tool"""
        try:
            logging.info("Navigating to IMEI tool...")
            self.driver.get("https://sellin.oway-ke.com/tool/imei")
            
            # Wait for page to load
            time.sleep(3)
            logging.info("Successfully navigated to IMEI tool")
            return True
            
        except Exception as e:
            logging.error(f"Failed to navigate to IMEI tool: {str(e)}")
            return False

    def check_imei_batch(self, imeis):
        """Check a batch of IMEIs"""
        try:
            logging.info(f"Entering {len(imeis)} IMEIs...")
            
            # Find the IMEI textarea
            imei_textarea = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "imei"))
            )
            
            # Clear and enter IMEIs
            imei_textarea.clear()
            imei_textarea.send_keys("\n".join(imeis))
            
            # Click check button
            check_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Get Info')]")
            check_button.click()
            logging.info("Check button clicked - waiting for results...")
            
            # Wait for results with longer timeout
            start_time = time.time()
            timeout = 45
            
            while time.time() - start_time < timeout:
                try:
                    # Look for results table
                    results_table = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                    # Check if table has data (more than just header)
                    rows = results_table.find_elements(By.TAG_NAME, "tr")
                    if len(rows) > 1:  # More than just header row
                        logging.info("Results table found with data!")
                        break
                    else:
                        logging.info("Table found but no data yet...")
                except:
                    logging.info(f"Waiting for results... {int(time.time() - start_time)}s")
                    time.sleep(3)
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to check IMEI batch: {str(e)}")
            return False

    def extract_results(self, expected_imeis):
        """COMPLETELY FIXED: Extract results from the table with proper IMEI mapping"""
        try:
            logging.info("Extracting data from results table...")
            
            # Wait a bit more for the table to fully load
            time.sleep(3)
            
            # Find the table
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # Get all rows
            rows = table.find_elements(By.TAG_NAME, "tr")
            logging.info(f"Found {len(rows)} rows in table")
            
            results_data = []
            extracted_imeis = set()
            
            # DEBUG: Print header to understand column structure
            if len(rows) > 0:
                header_cells = rows[0].find_elements(By.TAG_NAME, "th")
                logging.info("=== TABLE HEADER ===")
                for i, cell in enumerate(header_cells):
                    logging.info(f"Header {i}: '{cell.text}'")
            
            # Skip header row (index 0) and process data rows
            for i, row in enumerate(rows[1:], 1):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    logging.info(f"Row {i} has {len(cells)} cells")
                    
                    # DEBUG: Print all cell contents to understand structure
                    for cell_idx, cell in enumerate(cells):
                        logging.info(f"  Cell {cell_idx}: '{cell.text}'")
                    
                    if len(cells) >= 7:  # Need at least 7 columns for IMEI data
                        # Try different column mappings to find the correct one
                        imei1 = None
                        model = None
                        activated_date = None
                        
                        # Try common column structures:
                        # Structure 1: [Index, IMEI1, IMEI2, Model, Color, In Date, Out Date, Activated Date]
                        if len(cells) >= 8:
                            imei1 = cells[1].text.strip()  # Column 1 for IMEI
                            model = cells[3].text.strip()  # Column 3 for Model
                            activated_date = cells[7].text.strip()  # Column 7 for Activated Date
                        
                        # Structure 2: [IMEI1, IMEI2, Model, Color, In Date, Out Date, Activated Date]
                        elif len(cells) >= 7:
                            imei1 = cells[0].text.strip()  # Column 0 for IMEI
                            model = cells[2].text.strip()  # Column 2 for Model
                            activated_date = cells[6].text.strip()  # Column 6 for Activated Date
                        
                        # Skip if IMEI is empty or invalid
                        if not imei1 or imei1 == '-' or imei1.isdigit() == False:
                            logging.warning(f"Row {i}: Invalid IMEI '{imei1}', skipping")
                            continue
                        
                        result = {
                            'imei1': imei1,
                            'model': model,
                            'activated_date': activated_date
                        }
                        
                        results_data.append(result)
                        extracted_imeis.add(imei1)
                        
                        logging.info(f"Row {i}: IMEI1='{imei1}', Model='{model}', Activated='{activated_date}'")
                        
                except Exception as e:
                    logging.warning(f"Failed to extract row {i}: {str(e)}")
                    continue
            
            # Check for missing IMEIs and categorize them properly
            missing_count = 0
            wrong_format_count = 0
            not_exist_count = 0
            
            for imei in expected_imeis:
                if imei not in extracted_imeis:
                    logging.warning(f"Missing result for IMEI: {imei}")
                    
                    # Check if it's wrong format (not 15 digits or contains non-digits)
                    if not re.match(r'^\d{15}$', imei):
                        results_data.append({
                            'imei1': imei,
                            'model': 'WRONG FORMAT',
                            'activated_date': 'N/A'
                        })
                        wrong_format_count += 1
                        logging.info(f"  {imei} -> WRONG FORMAT")
                    else:
                        results_data.append({
                            'imei1': imei,
                            'model': 'NOT EXIST',
                            'activated_date': 'N/A'
                        })
                        not_exist_count += 1
                        logging.info(f"  {imei} -> NOT EXIST")
                    missing_count += 1
            
            logging.info(f"Successfully processed {len(results_data)} results")
            logging.info(f"Missing IMEIs: {missing_count} (Wrong Format: {wrong_format_count}, Not Exist: {not_exist_count})")
            
            return results_data
            
        except Exception as e:
            logging.error(f"Failed to extract results: {str(e)}")
            return []

    def categorize_imei(self, result):
        """FIXED: Categorize IMEI based on the result"""
        imei = result['imei1']
        model = result.get('model', '').upper()
        activated_date = result.get('activated_date', '').upper()
        
        logging.info(f"Categorizing {imei}: model='{model}', activated='{activated_date}'")
        
        # Check for "not exist" and "wrong format" FIRST - this is critical
        if "NOT EXIST" in model:
            return "not_exist"
        elif "WRONG FORMAT" in model:
            return "wrong_format"
        elif activated_date in ['N/A', 'NA', '', '-', 'NULL', 'NONE']:
            return "not_active"
        elif activated_date not in ['N/A', 'NA', '', '-', 'NULL', 'NONE']:
            try:
                # Parse activated date - handle different date formats
                date_formats = [
                    '%Y-%m-%d %H:%M:%S', 
                    '%Y-%m-%d', 
                    '%d/%m/%Y %H:%M:%S', 
                    '%d/%m/%Y',
                    '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y'
                ]
                
                activated_dt = None
                parsed_date = None
                
                for fmt in date_formats:
                    try:
                        activated_dt = datetime.strptime(activated_date, fmt)
                        parsed_date = fmt
                        break
                    except ValueError:
                        continue
                
                if activated_dt:
                    current_dt = datetime.now()
                    days_diff = (current_dt - activated_dt).days
                    
                    logging.info(f"  Date parsed: {activated_dt}, Days difference: {days_diff}")
                    
                    if days_diff <= 2:
                        return "active_2_days"
                    elif 3 <= days_diff <= 15:
                        return "active_3_15"
                    else:
                        return "expired"
                else:
                    # If date parsing fails completely, log it and treat as not active
                    logging.warning(f"Could not parse date: '{activated_date}'")
                    return "not_active"
                    
            except Exception as e:
                logging.warning(f"Date parsing failed for {imei}: '{activated_date}', error: {e}")
                return "not_active"
        else:
            return "not_active"

    def process_imeis(self, imei_list, batch_size=50):
        """Main method to process all IMEIs"""
        global automation_progress
        
        try:
            # Split IMEIs into batches
            batches = [imei_list[i:i + batch_size] for i in range(0, len(imei_list), batch_size)]
            total_batches = len(batches)
            
            logging.info(f"Processing {total_batches} batch(es) - {len(imei_list)} total IMEIs")
            
            automation_progress['total_batches'] = total_batches
            automation_progress['total'] = len(imei_list)
            
            all_results = []
            
            for batch_num, batch in enumerate(batches, 1):
                automation_progress['current_batch'] = batch_num
                automation_progress['message'] = f"Processing batch {batch_num}/{total_batches}"
                automation_progress['progress'] = (batch_num - 1) / total_batches * 100
                
                logging.info(f"Checking batch {batch_num}/{total_batches} - {len(batch)} IMEIs")
                
                # Navigate to IMEI tool for each batch
                if not self.navigate_to_imei_tool():
                    raise Exception("Failed to navigate to IMEI tool")
                
                # Check the batch
                if not self.check_imei_batch(batch):
                    raise Exception("Failed to check IMEI batch")
                
                # Extract results
                batch_results = self.extract_results(batch)
                all_results.extend(batch_results)
                
                # Categorize results using FIXED logic
                for result in batch_results:
                    category = self.categorize_imei(result)
                    self.results[category].append(result['imei1'])
                    
                    logging.info(f"  {result['imei1']} -> {category.upper()}")
                
                # Update progress
                processed_count = len([r for r in all_results if r['imei1'] in imei_list])
                progress_percent = (processed_count / len(imei_list)) * 100
                automation_progress['progress'] = progress_percent
                automation_progress['message'] = f"Processed {processed_count}/{len(imei_list)} IMEIs"
                
                logging.info(f"Progress: {processed_count}/{len(imei_list)} ({progress_percent:.1f}%)")
                
                # Small delay between batches
                if batch_num < total_batches:
                    time.sleep(2)
            
            self.all_results_data = all_results
            logging.info("Automation completed!")
            
            # Create final summary
            final_categories = {category: [] for category in self.results.keys()}
            for category, imeis in self.results.items():
                for imei in imeis:
                    if imei in imei_list:  # Only count the original IMEIs we submitted
                        final_categories[category].append(imei)
            
            summary = {category: len(imeis) for category, imeis in final_categories.items()}
            
            # Log final results
            for category, imeis in final_categories.items():
                logging.info(f"{category.upper()}: {len(imeis)} IMEIs")
                for imei in imeis:
                    logging.info(f"  - {imei}")
            
            return {
                'success': True,
                'total_processed': len(imei_list),
                'categories': final_categories,
                'all_results': [r for r in all_results if r['imei1'] in imei_list],
                'summary': summary
            }
            
        except Exception as e:
            logging.error(f"Automation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'total_processed': 0,
                'categories': self.results,
                'all_results': [],
                'summary': {category: len(imeis) for category, imeis in self.results.items()}
            }
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("Browser closed")

def run_automation(imei_list):
    """Run automation in a separate thread"""
    global automation_progress
    
    try:
        automation = IMEIAutomation(headless=True)  # True for Railway
        
        # Setup driver
        if not automation.setup_driver():
            automation_progress['error'] = "Failed to setup browser"
            automation_progress['status'] = 'error'
            return
        
        # Login
        if not automation.login("KE007", "KE007"):
            automation_progress['error'] = "Login failed - check screenshots and logs"
            automation_progress['status'] = 'error'
            return
        
        # Process IMEIs
        result = automation.process_imeis(imei_list, batch_size=50)
        automation_progress['results'] = result
        automation_progress['status'] = 'completed'
        automation_progress['message'] = f'Completed! Processed {len(imei_list)} IMEIs'
        automation_progress['progress'] = 100
        
    except Exception as e:
        automation_progress['error'] = str(e)
        automation_progress['status'] = 'error'
        automation_progress['message'] = f'Automation failed: {str(e)}'

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_automation():
    global automation_progress
    
    try:
        data = request.get_json()
        imei_text = data.get('imeis', '')
        
        # Parse IMEIs from text
        imei_list = [imei.strip() for imei in imei_text.split('\n') if imei.strip()]
        
        if not imei_list:
            return jsonify({'success': False, 'error': 'No IMEIs provided'})
        
        # Reset progress
        automation_progress = {
            'status': 'running',
            'message': 'Starting automation...',
            'progress': 0,
            'total': len(imei_list),
            'current_batch': 0,
            'total_batches': 0,
            'results': None,
            'error': None
        }
        
        # Start automation in separate thread
        thread = threading.Thread(target=run_automation, args=(imei_list,))
        thread.daemon = True
        thread.start()
        
        logging.info(f"Starting automation for {len(imei_list)} IMEIs")
        return jsonify({'success': True, 'message': 'Automation started'})
        
    except Exception as e:
        logging.error(f"Failed to start automation: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/progress')
def get_progress():
    return jsonify(automation_progress)

@app.route('/api/results')
def get_results():
    global automation_progress
    
    if automation_progress['results']:
        return jsonify(automation_progress['results'])
    else:
        return jsonify({'success': False, 'error': 'No results available'})

# Chrome installation check for Railway
def check_chrome_installation():
    """Check if Chrome is available on Railway"""
    try:
        result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Chrome found at: {result.stdout.strip()}")
            return True
        else:
            logging.warning("Chrome not found in PATH")
            return False
    except Exception as e:
        logging.error(f"Error checking Chrome installation: {e}")
        return False

# Initialize Chrome check when app starts
@app.before_first_request
def initialize_chrome():
    logging.info("Initializing Chrome check for Railway...")
    chrome_available = check_chrome_installation()
    if chrome_available:
        logging.info("✅ Chrome is available - ready for automation")
    else:
        logging.warning("❌ Chrome not available - automation may fail")

# Railway-compatible main block
if __name__ == '__main__':
    logging.info("🚀 IMEI AUTOMATION TOOL - RAILWAY EDITION")
    logging.info("Key features:")
    logging.info("✅ Optimized for Railway deployment")
    logging.info("✅ Headless Chrome configuration")
    logging.info("✅ Production-ready settings")
    logging.info("✅ Chrome installation checking")
    logging.info("------------------------------------------------------------")
    
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)