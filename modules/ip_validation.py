import requests
from flask import request, render_template, g
from functools import wraps
import time
import os

# Cache for IP validation results
IP_CACHE = {}
CACHE_DURATION = 3600  # 1 hour in seconds

# Load blocked items on module initialization
def load_blocked_items(filename):
    items = set()
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as file:
                for line in file:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        items.add(line)
        return items
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return set()

BLOCKED_IPS = load_blocked_items('data/ips.txt')
BLOCKED_ISPS = load_blocked_items('data/isps.txt')
BLOCKED_ORGS = load_blocked_items('data/organisations.txt')

def get_client_ip():
    """Get the client's real IP address, considering X-Forwarded-For header"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get the real IP
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    else:
        # If not behind a proxy, get the direct IP
        ip = request.remote_addr
    return ip

def validate_ip_server_side(ip):
    """
    Server-side validation function with caching
    Returns a tuple of (is_blocked, reason)
    """
    # Check cache first
    now = time.time()
    if ip in IP_CACHE and now - IP_CACHE[ip]['timestamp'] < CACHE_DURATION:
        return IP_CACHE[ip]['blocked'], IP_CACHE[ip]['reason']
    
    # Check if IP is directly blocked
    if ip.lower() in BLOCKED_IPS:
        result = (True, "IP address is directly blocked")
        IP_CACHE[ip] = {'blocked': result[0], 'reason': result[1], 'timestamp': now}
        return result
    
    # Only perform external API checks for suspicious IPs to improve performance
    if _is_suspicious_ip(ip):
        # Perform external API checks (IP-API, Avast, Mind-Media)
        is_blocked, reason = _check_external_services(ip)
        if is_blocked:
            # Cache the result
            IP_CACHE[ip] = {'blocked': True, 'reason': reason, 'timestamp': now}
            return True, reason
    
    # If we get here, the IP is allowed
    IP_CACHE[ip] = {'blocked': False, 'reason': None, 'timestamp': now}
    return False, None

def _is_suspicious_ip(ip):
    """Quick check to determine if an IP needs further validation"""
    # Implement simple heuristics to identify suspicious IPs
    # For example, check known proxy ranges, non-standard ports, etc.
    return False  # Default to non-suspicious for most IPs

def _check_external_services(ip):
    """Check external services for IP validation"""
    # Implement checks with external APIs in parallel for better performance
    # Use asyncio or threading to make concurrent requests
    
    # For now, we'll implement a simplified sequential version
    try:
        # Check with IP-API Pro
        ip_api_response = requests.get(
            f"https://pro.ip-api.com/json/{ip}?fields=66842623&key=ipapiq9SFY1Ic4",
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://members.ip-api.com/'},
            timeout=2  # Set timeout to prevent hanging
        )
        ip_api_data = ip_api_response.json()
        
        # Check if ISP or organization is blocked
        if "isp" in ip_api_data and ip_api_data["isp"].lower() in BLOCKED_ISPS:
            return True, f"ISP '{ip_api_data['isp']}' is blocked"
            
        if "org" in ip_api_data and ip_api_data["org"].lower() in BLOCKED_ORGS:
            return True, f"Organization '{ip_api_data['org']}' is blocked"
    except Exception:
        pass

    # Additional checks with other services...
    
    return False, None

def init_ip_validation(app):
    """Initialize IP validation middleware for the Flask app"""
    @app.before_request
    def validate_request():
        # This is a placeholder that does nothing yet
        return None
def _should_skip_validation(path):
    """Determine if IP validation should be skipped for this path"""
    # Skip for static assets
    if any(path.endswith(ext) for ext in [
            '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', 
            '.svg', '.webp', '.woff', '.woff2', '.ico']):
        return True
        
    # Skip for static directories
    if path.startswith(('/_next/static/', '/static/', '/assets/', '/images/')):
        return True
        
    # Skip for API endpoints that don't need protection
    if path.startswith('/api/public/'):
        return True
        
    return False

# Decorator for routes that need additional IP validation
def require_validated_ip(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if IP has already been validated by middleware
        if hasattr(g, 'ip_validated') and g.ip_validated:
            return f(*args, **kwargs)
            
        # If not, validate now
        client_ip = get_client_ip()
        is_blocked, reason = validate_ip_server_side(client_ip)
        
        if is_blocked:
            return render_template('403.html', reason=reason), 403
            
        return f(*args, **kwargs)
    return decorated_function