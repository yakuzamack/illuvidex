from flask import request, send_file, current_app
import os
import requests
import urllib.parse
import mimetypes
import logging

logger = logging.getLogger(__name__)

def init_image_handler(app):
    """Initialize Next.js image optimization handling"""
    
    #@app.route('/_next/image')
    #def next_image_optimization():
    #    """Handle Next.js image optimization requests"""
    #    logger.info(f"Handling Next.js image request with params: {request.args}")
    #   
    #   # Get the image URL and other parameters
    #   image_url = request.args.get('url')
    #   width = request.args.get('w')
    #   quality = request.args.get('q', '75')
    #   
    #   if not image_url:
    #       return "Missing URL parameter", 400
    #   
    #   # URL decode the image path
    #   decoded_url = urllib.parse.unquote(image_url)
    #   
    #   # Create cache directory structure
    #   cache_dir = os.path.join(app.root_path, 'image_cache')
    #   os.makedirs(cache_dir, exist_ok=True)
    #   
    #   # Generate a cache key based on URL and parameters
    #   cache_key = f"{decoded_url.replace('/', '_')}_{width}_{quality}"
    #   cache_path = os.path.join(cache_dir, cache_key)
    #   
    #   # Check if we have the image cached
    #   if os.path.exists(cache_path):
    #       logger.info(f"Serving cached image: {cache_path}")
    #       return send_file(
    #           cache_path,
    #           mimetype=mimetypes.guess_type(decoded_url)[0] or 'image/webp'
    #       )
    #   
    #   # If not cached, fetch from original site
    #   try:
    #       # Construct the full URL to the original image
    #       if decoded_url.startswith('/'):
    #           proxy_url = f"https://overworld.illuvium.io{decoded_url}"
    #       else:
    #           proxy_url = decoded_url
    #           
    #       logger.info(f"Fetching image from: {proxy_url}")
    #       
    #       response = requests.get(
    #           proxy_url,
    #           headers={
    #               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    #           },
    #           stream=True
    #       )
    #       
    #       if response.status_code == 200:
    #           # Create directory structure if it doesn't exist
    #           os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    #           
    #           # Save the image to cache
    #           with open(cache_path, 'wb') as f:
    #               for chunk in response.iter_content(chunk_size=8192):
    #                   if chunk:
    #                       f.write(chunk)
    #           
    #           logger.info(f"Cached image to: {cache_path}")
    #           
    #           # Get content type
    #           content_type = response.headers.get('Content-Type') or mimetypes.guess_type(decoded_url)[0] or 'image/webp'
    #           
    #           # Return the image
    #           return send_file(
    #               cache_path,
    #               mimetype=content_type
    #           )
    #       else:
    #           logger.error(f"Failed to fetch image: {response.status_code}")
    #           return "Image not found", 404
    #   except Exception as e:
    #       logger.error(f"Error fetching image: {str(e)}")
    #       import traceback
    #       logger.error(traceback.format_exc())
    #       return "Error fetching image", 500