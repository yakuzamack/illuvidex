import os
import requests
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import logging
import re
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Original site URL
ORIGINAL_SITE = "https://overworld.illuvium.io"

# Base directory for assets
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'App_files/Assets')

def ensure_directory_exists(path):
    """Ensure the directory exists, create if it doesn't."""
    os.makedirs(path, exist_ok=True)

def process_nextjs_image_url(url):
    """Convert Next.js image URL to original image URL."""
    parsed = urlparse(url)
    if not parsed.path.startswith('/_next/image'):
        return url
    
    query = parse_qs(parsed.query)
    if 'url' not in query:
        return url
    
    original_path = unquote(query['url'][0])
    if original_path.startswith('/'):
        original_path = original_path[1:]
    return original_path

def download_asset(url, local_path):
    """Download an asset from the URL and save it to the local path."""
    try:
        # Process Next.js image URLs
        original_url = process_nextjs_image_url(url)
        full_url = urljoin(ORIGINAL_SITE, original_url)
        
        response = requests.get(full_url, timeout=10)
        if response.status_code == 200:
            ensure_directory_exists(os.path.dirname(local_path))
            with open(local_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Downloaded: {full_url} -> {local_path}")
            return True
        else:
            logger.error(f"Failed to download {full_url}: Status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def extract_assets_from_html(html_content):
    """Extract asset URLs from HTML content."""
    assets = set()
    
    # Find all script tags
    script_pattern = r'<script[^>]*src="([^"]*)"'
    for match in re.finditer(script_pattern, html_content):
        assets.add(match.group(1))
    
    # Find all link tags (CSS)
    link_pattern = r'<link[^>]*href="([^"]*)"'
    for match in re.finditer(link_pattern, html_content):
        href = match.group(1)
        if not href.startswith('data:'):
            assets.add(href)
    
    # Find all img tags
    img_pattern = r'<img[^>]*src="([^"]*)"'
    for match in re.finditer(img_pattern, html_content):
        src = match.group(1)
        if not src.startswith('data:'):
            assets.add(src)
            
    # Find Next.js image URLs in JSON data
    json_pattern = r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    json_match = re.search(json_pattern, html_content, re.DOTALL)
    if json_match:
        try:
            next_data = json.loads(json_match.group(1))
            # Extract image URLs from Next.js data
            def extract_image_urls(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, str) and value.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            if not value.startswith(('data:', 'http:', 'https:')):
                                assets.add(value)
                        elif isinstance(value, (dict, list)):
                            extract_image_urls(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_image_urls(item)
            
            extract_image_urls(next_data)
        except json.JSONDecodeError:
            logger.error("Failed to parse Next.js data")
    
    return assets

def should_download_asset(url):
    """Check if an asset should be downloaded."""
    if url.startswith(('data:', 'http:', 'https:')):
        parsed = urlparse(url)
        if not parsed.netloc.endswith('illuvium.io'):
            return False
    return True

def get_local_path(url):
    """Get the local path for an asset URL."""
    original_url = process_nextjs_image_url(url)
    if original_url.startswith(('http:', 'https:')):
        parsed = urlparse(original_url)
        path = parsed.path
        if path.startswith('/'):
            path = path[1:]
    else:
        path = original_url
        
    # Ensure the path has an extension
    if not Path(path).suffix and '.' not in path:
        path += '.webp'  # Default to webp for Next.js images
        
    return os.path.join(BASE_DIR, path)

def main():
    # First, get the main page to extract asset URLs
    try:
        response = requests.get(ORIGINAL_SITE, timeout=10)
        if response.status_code == 200:
            assets = extract_assets_from_html(response.text)
            logger.info(f"Found {len(assets)} assets in the main page")
            
            # Download each asset
            for asset_url in assets:
                if not should_download_asset(asset_url):
                    logger.info(f"Skipping external asset: {asset_url}")
                    continue
                
                local_path = get_local_path(asset_url)
                
                # Skip if file already exists
                if os.path.exists(local_path):
                    logger.info(f"Skipping existing file: {local_path}")
                    continue
                
                download_asset(asset_url, local_path)
        else:
            logger.error(f"Failed to fetch main page: Status code {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching main page: {str(e)}")

if __name__ == "__main__":
    main() 