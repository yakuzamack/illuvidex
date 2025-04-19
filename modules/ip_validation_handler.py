import logging

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
