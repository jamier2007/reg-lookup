from flask import Flask, jsonify, request
import logging
import time
import requests
from bs4 import BeautifulSoup
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Retry decorator for handling temporary failures
def retry(max_retries=3, delay=1):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        raise
                    logger.warning(f"Retry {retries}/{max_retries} after error: {str(e)}")
                    time.sleep(delay)
            return None
        return decorated_function
    return decorator

@retry(max_retries=3, delay=1)
def get_vehicle_data(reg):
    """
    Fetch vehicle data from the website using the registration number.
    
    Args:
        reg (str): Vehicle registration number
        
    Returns:
        dict: Vehicle data or error message
    """
    url = f"https://bookmygarage.com/garage-detail/sussexautocareltd/rh12lw/book/?ref=sussexautocare.co.uk&vrm={reg}&referrer=widget"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Error fetching data for {reg}: HTTP {response.status_code}")
            return {"error": f"HTTP Error: {response.status_code}"}
            
        html = response.text
        
        soup = BeautifulSoup(html, 'html.parser')
        vehicle_info = soup.select_one("div.row.second-header div.col.m9.s12>span>span:nth-child(2)")
        
        if not vehicle_info:
            logger.warning(f"No vehicle info found for {reg}")
            return {"error": "No data found"}
            
        vehicle_text = vehicle_info.get_text(strip=True)
        vehicle_parts = vehicle_text.split(',')
        
        if len(vehicle_parts) < 4:
            logger.warning(f"Incomplete vehicle data for {reg}: {vehicle_text}")
            return {"error": "Incomplete data found"}
            
        make_model = vehicle_parts[0].replace('-', '').strip().split(' ', 1)
        if len(make_model) < 2:
            make_model.append("")  # Handle case where model might be missing
            
        result = OrderedDict([
            ('reg', reg.upper()),
            ('make', make_model[0]),
            ('model', make_model[1]),
            ('fuel', vehicle_parts[1].strip()),
            ('cc', vehicle_parts[2].replace('cc', '').strip()),
            ('transmission', vehicle_parts[3].strip())
        ])
        
        elapsed = time.time() - start_time
        logger.info(f"Retrieved data for {reg} in {elapsed:.2f} seconds")
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching data for {reg}")
        return {"error": "Request timed out"}
    except Exception as e:
        logger.error(f"Error processing {reg}: {str(e)}")
        return {"error": f"Processing error: {str(e)}"}

@app.route('/<reg>')
def vehicle_lookup(reg):
    """API endpoint to lookup vehicle data by registration number"""
    result = get_vehicle_data(reg)
    return jsonify(result or {"error": "No data found"})

@app.route('/batch', methods=['POST'])
def batch_lookup():
    """API endpoint to lookup multiple vehicles in a single request"""
    data = request.get_json()
    if not data or 'registrations' not in data:
        return jsonify({"error": "Invalid request. Please provide a list of registrations."}), 400
        
    registrations = data['registrations']
    if not registrations or not isinstance(registrations, list):
        return jsonify({"error": "Please provide a valid list of registrations."}), 400
        
    # Limit batch size to prevent abuse
    if len(registrations) > 50:
        return jsonify({"error": "Batch size too large. Maximum 50 registrations per request."}), 400
    
    # Process registrations with ThreadPoolExecutor for parallelism
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(get_vehicle_data, registrations))
    
    # Create a dictionary mapping each registration to its result
    response = {reg.upper(): result for reg, result in zip(registrations, results)}
    return jsonify(response)

if __name__ == "__main__":
    logger.info("Starting vehicle lookup service...")
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
