import os
import time
import json
import requests
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Debug mode flag - set to False in production
DEBUG_MODE = False

# Ensure data directories exist
os.makedirs('Data', exist_ok=True)

def load_data_file(filename):
    """Load data from a file into a set for efficient lookups."""
    filepath = os.path.join('Data', filename)
    try:
        with open(filepath, 'r') as f:
            return {line.strip().lower() for line in f if line.strip()}
    except Exception as e:
        logger.error(f"Error loading {filename}: {str(e)}")
        return set()

def validate_ip(ip, site_url="https://example.com"):
    logger.info(f"Starting validation for IP: {ip}")
    logger.info(f"DEBUG_MODE is: {DEBUG_MODE}")
    
    # Always allow localhost IPs regardless of DEBUG_MODE
    if ip in ["127.0.0.1", "::1", "localhost"]:
        logger.info(f"Allowing access for localhost IP: {ip}")
        return False
    
    # First check if we're in debug mode and it's a local IP
    if DEBUG_MODE:
        local_ips = ["127.0.0.1", "::1", "localhost"]
        if ip in local_ips or ip.startswith(("192.168.", "10.")):
            logger.info(f"DEBUG MODE: Allowing access for local IP: {ip}")
            return False
    
    # IMPORTANT: Explicitly block localhost and private IPs when not in debug mode
    if not DEBUG_MODE:
        logger.info("DEBUG_MODE is False, checking if IP should be blocked")
        # List of IPs or IP ranges to block
        blocked_ips = [
            '127.0.0.1',  # Localhost
            '::1',        # IPv6 localhost
            'localhost',  # Hostname for localhost
            '192.168.',   # Private network
            '10.',        # Private network
            # ... other private IP ranges
        ]
        
        # Check if the IP is in the blocked list
        for blocked_ip in blocked_ips:
            if ip == blocked_ip:
                logger.warning(f"Access denied for exact match blocked IP: {ip}")
                return True
            elif blocked_ip.endswith('.') and ip.startswith(blocked_ip):
                logger.warning(f"Access denied for prefix match blocked IP: {ip} (matches {blocked_ip})")
                return True
        
        logger.info(f"IP {ip} not found in blocked list")    
    # Check against data files
    try:
        # Load blocked organizations, IPs, and ISPs
        blocked_orgs = load_data_file('organization.txt')
        blocked_ips = load_data_file('ips.txt')
        blocked_isps = load_data_file('isps.txt')
        
        # Check if IP is directly in the blocked IPs list
        if ip.lower() in blocked_ips:
            logger.info(f"IP {ip} blocked: IP in blocklist")
            return True
            
        # Initialize variables to store API response data
        country = "Unknown"
        isp = "Unknown"
        organization = "Unknown"
        
        # Check Avast IP Info
        try:
            avast_blocked, avast_data = check_avast_ip_info(ip)
            if avast_blocked:
                logger.info(f"IP {ip} blocked by Avast IP Info check")
                return True
            
            # Extract data from Avast response
            if avast_data:
                country = avast_data.get('countryName', country)
                isp = avast_data.get('isp', isp)
                organization = avast_data.get('organization', organization)
                
                # Check if organization is in blocked list
                if organization.lower() in blocked_orgs:
                    logger.info(f"IP {ip} blocked: Organization {organization} in blocklist")
                    return True
        except Exception as e:
            logger.error(f"Error in Avast IP check: {str(e)}")
        
        # Check IP-API Pro
        try:
            ipapi_blocked, ipapi_data = check_ipapi_pro(ip)
            if ipapi_blocked:
                logger.info(f"IP {ip} blocked by IP-API Pro check")
                return True
            
            # Extract data from IP-API response
            if ipapi_data:
                country = ipapi_data.get('country', country)
                isp = ipapi_data.get('isp', isp)
                
                # Check if ISP is in blocked list
                if isp.lower() in blocked_isps:
                    logger.info(f"IP {ip} blocked: ISP {isp} in blocklist")
                    return True
        except Exception as e:
            logger.error(f"Error in IP-API Pro check: {str(e)}")
        
        # Check Mind-Media Proxy
        try:
            if check_mind_media_proxy(ip):
                logger.info(f"IP {ip} blocked by Mind-Media Proxy check")
                return True
        except Exception as e:
            logger.error(f"Error in Mind-Media Proxy check: {str(e)}")
        
        # If we reach here, all checks passed
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            send_telegram_notification(ip, country, isp, timestamp)
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {str(e)}")
            
        logger.info(f"IP {ip} allowed access")
        return False
        
    except Exception as e:
        logger.error(f"Error in IP validation: {str(e)}")
        # If there's an error in validation, default to allowing access
        # You might want to change this to block access instead
        return False

def check_avast_ip_info(ip):
    """Check IP against Avast IP Info API."""
    # Skip API check for local IPs in debug mode
    if DEBUG_MODE:
        local_ips = ["127.0.0.1", "::1"]
        if ip in local_ips or ip.startswith(("192.168.", "10.")):
            logger.info(f"DEBUG MODE: Skipping Avast API check for local IP: {ip}")
            return False, {}
    
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'origin': 'https://www.avast.com',
        'priority': 'u=1, i',
        'referer': 'https://www.avast.com/',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
    }
    
    try:
        url = f"https://ip-info.ff.avast.com/v2/info"
        params = {"ip": ip}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Load blocked organizations and IPs
            blocked_orgs = load_data_file('organization.txt')
            blocked_ips = load_data_file('ips.txt')
            
            # Check if organization or IP is in blocked lists
            if 'organization' in data and data['organization'].lower() in blocked_orgs:
                logger.info(f"IP {ip} blocked: Organization {data['organization']} in blocklist")
                return True, data
            
            if ip.lower() in blocked_ips:
                logger.info(f"IP {ip} blocked: IP in blocklist")
                return True, data
                
            return False, data
        else:
            logger.warning(f"Avast API returned status code {response.status_code}")
            return False, {}
    except Exception as e:
        logger.error(f"Error checking Avast IP info: {str(e)}")
        return False, {}

def check_ipapi_pro(ip):
    """Check IP against IP-API Pro."""
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Origin': 'https://members.ip-api.com',
        'Referer': 'https://members.ip-api.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    try:
        url = f"https://pro.ip-api.com/json/{ip}?fields=66842623&key=ipapiq9SFY1Ic4"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Load blocked ISPs
            blocked_isps = load_data_file('isps.txt')
            
            # Check if proxy is false AND isp is in blocked list
            if data.get('proxy') is False and 'isp' in data and data['isp'].lower() in blocked_isps:
                logger.info(f"IP {ip} blocked: ISP {data['isp']} in blocklist and not a proxy")
                return True, data
                
            return False, data
        else:
            logger.warning(f"IP-API Pro returned status code {response.status_code}")
            return False, {}
    except Exception as e:
        logger.error(f"Error checking IP-API Pro: {str(e)}")
        return False, {}

def check_mind_media_proxy(ip):
    """Check IP against Mind-Media Proxycheck."""
    # Skip check for local IPs
    if ip == "127.0.0.1" or ip == "::1" or ip.startswith("192.168.") or ip.startswith("10."):
        return False
        
    try:
        url = f"http://proxy.mind-media.com/block/proxycheck.php?ip={ip}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.text.strip()
            
            if result == "Y":
                logger.info(f"IP {ip} blocked: Mind-Media proxy check returned Y")
                return True
                
            return False
        else:
            logger.warning(f"Mind-Media API returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking Mind-Media proxy: {str(e)}")
        return False

def send_telegram_notification(ip, country, isp, timestamp):
    """Send a notification to Telegram."""
    # Replace with your actual Telegram bot token and chat ID
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram notification skipped: Missing bot token or chat ID")
        return False
    
    message = f"New Access:\nIP: {ip}\nCountry: {country}\nISP: {isp}\nTime: {timestamp}"
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram notification sent successfully")
            return True
        else:
            logger.error(f"Failed to send Telegram notification: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {str(e)}")
        return False