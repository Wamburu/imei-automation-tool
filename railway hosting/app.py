from flask import Flask, render_template, request, jsonify
import logging
import sys
import os
import time
import threading
import re
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

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
    def __init__(self):
        self.results = {
            'not_active': [],
            'active_2_days': [],
            'active_3_15': [],
            'expired': [],
            'not_exist': [],
            'wrong_format': []
        }
        self.all_results_data = []
        
    def mock_check_imei(self, imei):
        """Mock IMEI check for demonstration - replace with real logic"""
        # This is a simulation - replace with actual Selenium code
        # when you get the Chrome issues resolved
        
        if not re.match(r'^\d{15}$', imei):
            return {'status': 'wrong_format', 'model': 'N/A', 'activated_date': 'N/A'}
        
        # Simulate different responses based on IMEI pattern
        last_digit = int(imei[-1])
        
        if last_digit == 0:
            return {'status': 'not_exist', 'model': 'NOT EXIST', 'activated_date': 'N/A'}
        elif last_digit in [1, 2]:
            return {'status': 'not_active', 'model': 'iPhone 15 Pro', 'activated_date': 'N/A'}
        elif last_digit in [3, 4]:
            days_ago = 1
            date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            return {'status': 'active_2_days', 'model': 'Samsung Galaxy S24', 'activated_date': date}
        elif last_digit in [5, 6, 7]:
            days_ago = 10
            date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            return {'status': 'active_3_15', 'model': 'Google Pixel 8', 'activated_date': date}
        else:
            days_ago = 30
            date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            return {'status': 'expired', 'model': 'Xiaomi 14', 'activated_date': date}

    def process_imeis(self, imei_list, batch_size=50):
        """Process IMEIs with mock data for now"""
        global automation_progress
        
        try:
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
                
                # Process each IMEI in the batch
                for imei in batch:
                    result = self.mock_check_imei(imei)
                    result_data = {
                        'imei1': imei,
                        'model': result['model'],
                        'activated_date': result['activated_date'],
                        'status': result['status']
                    }
                    all_results.append(result_data)
                    
                    # Categorize
                    self.results[result['status']].append(imei)
                    
                    logging.info(f"  {imei} -> {result['status'].upper()}")
                
                # Update progress
                processed_count = len(all_results)
                progress_percent = (processed_count / len(imei_list)) * 100
                automation_progress['progress'] = progress_percent
                automation_progress['message'] = f"Processed {processed_count}/{len(imei_list)} IMEIs"
                
                logging.info(f"Progress: {processed_count}/{len(imei_list)} ({progress_percent:.1f}%)")
                
                # Simulate processing time
                time.sleep(1)
            
            self.all_results_data = all_results
            logging.info("Automation completed!")
            
            # Create final summary
            summary = {category: len(imeis) for category, imeis in self.results.items()}
            
            # Log final results
            for category, imeis in self.results.items():
                logging.info(f"{category.upper()}: {len(imeis)} IMEIs")
            
            return {
                'success': True,
                'total_processed': len(imei_list),
                'categories': self.results,
                'all_results': all_results,
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

def run_automation(imei_list):
    """Run automation in a separate thread"""
    global automation_progress
    
    try:
        automation = IMEIAutomation()
        
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
