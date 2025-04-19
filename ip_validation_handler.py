import os
import time
import logging
import traceback
from ip_validator import validate_ip as external_validate_ip, DEBUG_MODE

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_client_ip_wsgi(environ):
    """
    Extract the client IP address from the WSGI environment.
    
    Args:
        environ: The WSGI environment dictionary
        
    Returns:
        str: The client IP address
    """
    # Try to get IP from various WSGI environment variables
    # Check for standard proxy headers first
    if 'HTTP_X_FORWARDED_FOR' in environ:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        logger.debug(f"IP from X-Forwarded-For: {ip}")
        return ip
    
    if 'HTTP_X_REAL_IP' in environ:
        ip = environ['HTTP_X_REAL_IP']
        logger.debug(f"IP from X-Real-IP: {ip}")
        return ip
    
    if 'HTTP_CLIENT_IP' in environ:
        ip = environ['HTTP_CLIENT_IP']
        logger.debug(f"IP from Client-IP: {ip}")
        return ip
    
    # Check for CloudFlare headers
    if 'HTTP_CF_CONNECTING_IP' in environ:
        ip = environ['HTTP_CF_CONNECTING_IP']
        logger.debug(f"IP from CF-Connecting-IP: {ip}")
        return ip
    
    # Fall back to the remote address
    ip = environ.get('REMOTE_ADDR', '127.0.0.1')
    logger.debug(f"IP from REMOTE_ADDR: {ip}")
    return ip

class IPValidationHandler:
    def __init__(self, original_site):
        self.original_site = original_site
        # Initialize IP validation cache
        self.ip_cache = {}
        self.ip_cache_timeout = 300  # 5 minutes
        logger.info("IP validation cache initialized")
    
    def should_skip_validation(self, path):
        """
        Determine if IP validation should be skipped for this path.
        
        Args:
            path: The request path
            
        Returns:
            bool: True if validation should be skipped, False otherwise
        """
        return any(path.endswith(ext) for ext in [
            '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', 
            '.woff', '.woff2', '.ttf', '.eot', '.otf', '.ico', '.json'
        ]) or path.startswith(('/_next/static/', '/static/', '/assets/', '/images/'))
    
    def validate_client_ip(self, environ):
        """
        Validate the client IP using the comprehensive validation from ip_validator.py
        
        Args:
            environ: The WSGI environment dictionary
                
        Returns:
            tuple: (is_blocked, client_ip)
        """
        # Get request path
        path = environ.get('PATH_INFO', '')
        
        # Skip validation for assets and static files
        if self.should_skip_validation(path):
            return False, get_client_ip_wsgi(environ)
        
        # Get client IP
        client_ip = get_client_ip_wsgi(environ)
        
        # Check cache first to avoid repeated API calls
        current_time = time.time()
        if client_ip in self.ip_cache:
            cache_time, is_blocked = self.ip_cache[client_ip]
            # If cache entry is still valid
            if current_time - cache_time < self.ip_cache_timeout:
                logger.debug(f"Using cached IP validation result for {client_ip}: {'blocked' if is_blocked else 'allowed'}")
                return is_blocked, client_ip
        
        # Allow access in debug mode for local IPs
        if DEBUG_MODE:
            local_ips = ["127.0.0.1", "::1"]
            if client_ip in local_ips or client_ip.startswith(("192.168.", "10.")):
                logger.info(f"DEBUG MODE: Allowing access for local IP: {client_ip}")
                self.ip_cache[client_ip] = (current_time, False)
                return False, client_ip
        
        # Use the comprehensive validation from ip_validator.py
        try:
            is_blocked = external_validate_ip(client_ip, self.original_site)
            # Cache the result
            self.ip_cache[client_ip] = (current_time, is_blocked)
            
            if is_blocked:
                logger.warning(f"Access denied for IP: {client_ip}")
            else:
                logger.info(f"Access allowed for IP: {client_ip}")
                
            return is_blocked, client_ip
        except Exception as e:
            logger.error(f"Error validating IP {client_ip}: {str(e)}")
            logger.error(traceback.format_exc())
            # Default to allowing access if validation fails
            return False, client_ip