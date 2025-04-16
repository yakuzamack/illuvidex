import http.server
import socketserver
import os
import urllib.parse
import urllib.request
import logging
import json
from pathlib import Path
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Cache configuration
CACHE_DIR = "cache"
CACHE_DURATION = 3600  # 1 hour in seconds
ASSET_CACHE = {}

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), CACHE_DIR)
        os.makedirs(self.cache_dir, exist_ok=True)

    def do_GET(self):
        try:
            path = urllib.parse.unquote(self.path)
            logging.info(f"Handling request: {path}")

            # Handle Next.js image optimization URLs
            if path.startswith('/_next/image'):
                self.handle_next_image(path)
                return

            # Handle static files
            if path.startswith('/_next/static'):
                self.handle_next_static(path)
                return

            # Handle direct image requests
            if any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
                self.handle_image(path)
                return

            # Handle HTML files
            if path.endswith('.html') or path == '/':
                self.handle_html(path)
                return

            # Handle other static files
            self.handle_other_static(path)

        except Exception as e:
            logging.error(f"Error handling request: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'')

    def handle_next_static(self, path):
        try:
            # Extract the actual file path
            file_path = path.split('?')[0]
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path.lstrip('/'))
            
            if os.path.exists(local_path):
                self.serve_file(local_path)
            else:
                # Return valid empty module for missing Next.js chunks
                self.send_response(200)
                if file_path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                    self.wfile.write(b'export default {};')
                elif file_path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                    self.wfile.write(b'')
                else:
                    self.send_header('Content-type', 'application/octet-stream')
                    self.wfile.write(b'')
                self.end_headers()
        except Exception as e:
            logging.error(f"Error handling static file: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'')

    def handle_next_image(self, path):
        try:
            # Extract the actual image path from the Next.js image optimization URL
            match = re.search(r'url=([^&]+)', path)
            if match:
                image_path = urllib.parse.unquote(match.group(1))
                logging.info(f"Looking for image: {image_path}")
                
                # Check if image exists locally
                local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path.lstrip('/'))
                if os.path.exists(local_path):
                    self.serve_file(local_path, 'image/webp')
                    return

                # If not found locally, fetch from original site
                original_url = f"https://overworld.illuvium.io{image_path}"
                logging.info(f"Fetching from original site: {original_url}")
                
                # Check cache first
                cache_key = f"image_{image_path}"
                cached_data = self.get_from_cache(cache_key)
                if cached_data:
                    self.send_response(200)
                    self.send_header('Content-type', 'image/webp')
                    self.end_headers()
                    self.wfile.write(cached_data)
                    return

                # Fetch and cache the image
                with urllib.request.urlopen(original_url) as response:
                    image_data = response.read()
                    self.set_cache(cache_key, image_data)
                    self.send_response(200)
                    self.send_header('Content-type', 'image/webp')
                    self.end_headers()
                    self.wfile.write(image_data)
            else:
                self.send_response(200)
                self.send_header('Content-type', 'image/webp')
                self.end_headers()
                self.wfile.write(b'')
        except Exception as e:
            logging.error(f"Error handling image: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'image/webp')
            self.end_headers()
            self.wfile.write(b'')

    def handle_image(self, path):
        try:
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip('/'))
            if os.path.exists(local_path):
                self.serve_file(local_path, 'image/webp')
            else:
                self.send_response(200)
                self.send_header('Content-type', 'image/webp')
                self.end_headers()
                self.wfile.write(b'')
        except Exception as e:
            logging.error(f"Error handling image: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'image/webp')
            self.end_headers()
            self.wfile.write(b'')

    def handle_html(self, path):
        try:
            if path == '/':
                path = '/index.html'
            
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip('/'))
            if os.path.exists(local_path):
                with open(local_path, 'rb') as file:
                    content = file.read()
                    
                    # Read both scripts
                    prevention_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prevent-behaviors.js')
                    load_complete_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'load-complete.js')
                    
                    with open(prevention_script_path, 'rb') as prevention_file:
                        prevention_script = prevention_file.read()
                    
                    with open(load_complete_script_path, 'rb') as load_complete_file:
                        load_complete_script = load_complete_file.read()
                    
                    # Inject both scripts before closing body tag
                    scripts = b'<script>' + prevention_script + b'</script><script>' + load_complete_script + b'</script>'
                    content = content.replace(b'</body>', scripts + b'</body>')
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(content)
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body></body></html>')
        except Exception as e:
            logging.error(f"Error handling HTML: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body></body></html>')

    def handle_other_static(self, path):
        try:
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip('/'))
            if os.path.exists(local_path):
                self.serve_file(local_path)
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.end_headers()
                self.wfile.write(b'')
        except Exception as e:
            logging.error(f"Error handling static file: {str(e)}")
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'')

    def serve_file(self, path, content_type=None):
        try:
            with open(path, 'rb') as file:
                self.send_response(200)
                if content_type:
                    self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(file.read())
        except Exception as e:
            logging.error(f"Error serving file: {str(e)}")
            self.send_response(200)
            if content_type:
                self.send_header('Content-type', content_type)
            else:
                self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'')

    def get_from_cache(self, key):
        if key in ASSET_CACHE:
            cached_time, data = ASSET_CACHE[key]
            if time.time() - cached_time < CACHE_DURATION:
                return data
            del ASSET_CACHE[key]
        return None

    def set_cache(self, key, data):
        ASSET_CACHE[key] = (time.time(), data)

def run_server(port=8000):
    handler = CustomHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Server running at http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.server_close()

if __name__ == "__main__":
    run_server() 