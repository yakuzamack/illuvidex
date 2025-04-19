from flask import Flask, send_from_directory, send_file, Response, make_response, request
import os
import requests
import mimetypes
import logging
import io

logger = logging.getLogger(__name__)

def init_static_files(app):
    """Initialize static file handling"""
    # Create necessary directories
    os.makedirs(os.path.join(app.root_path, '_next', 'static', 'chunks'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '_next', 'static', 'css'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '_next', 'static', 'media'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'images'), exist_ok=True)
    
    @app.route('/_next/static/<path:path>')
    def serve_next_static(path):
        """Handle Next.js static files with proper binary handling"""
        local_path = os.path.join(app.root_path, '_next', 'static', path)
        local_dir = os.path.dirname(local_path)
        os.makedirs(local_dir, exist_ok=True)
        
        # Check if the file exists locally and isn't corrupted
        file_exists = os.path.exists(local_path) and os.path.isfile(local_path)
        is_js_file = path.endswith('.js')
        
        # For JS files, always download fresh copies to avoid corruption
        if is_js_file:
            file_exists = False  # Force re-download for now
        
        if file_exists:
            # Serve the local file
            return send_file(local_path)
        
        # Download from original site
        try:
            # Use raw binary mode for JS files to prevent text processing
            url = f"https://overworld.illuvium.io/_next/static/{path}"
            logger.info(f"Downloading: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'
            }
            
            # Use streaming for binary files
            response = requests.get(url, headers=headers, stream=True)
            
            if response.status_code == 200:
                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # For JS files, download as binary without text manipulation
                with open(local_path, 'wb') as f:
                    # Use raw content without text processing
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Serve the downloaded file
                resp = send_file(local_path)
                
                # Set appropriate cache headers
                if is_js_file:
                    resp.headers['Cache-Control'] = 'no-cache'  # Don't cache JS during dev
                else:
                    resp.headers['Cache-Control'] = 'public, max-age=31536000'
                    
                return resp
            else:
                logger.error(f"Failed to download: {url} - Status: {response.status_code}")
                return "File not found", 404
        except Exception as e:
            logger.error(f"Error processing {path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return "Error processing file", 500
    
    # Image handling routes
    @app.route('/images/<path:path>')
    def serve_images(path):
        """Handle image file requests"""
        logger.info(f"Serving image: {path}")
        images_dir = os.path.join(app.root_path, 'images')
        os.makedirs(images_dir, exist_ok=True)
        file_path = os.path.join(images_dir, path)
        
        # Check if image exists locally
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_file(file_path)
        
        # Try to proxy from original site
        try:
            url = f"https://overworld.illuvium.io/images/{path}"
            logger.info(f"Downloading image: {url}")
            
            response = requests.get(url, stream=True)
            
            if response.status_code == 200:
                # Create directory structure
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Save file
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Serve the downloaded file
                return send_file(file_path)
            else:
                logger.warning(f"Failed to download image: {response.status_code}")
                return "Image not found", 404
        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            return "Error processing image", 500
    
    # Add handler for images with extensions
    @app.route('/images/<path:path>.<ext>')
    def serve_images_with_extension(path, ext):
        """Fallback handler for image requests with extensions"""
        full_path = f"{path}.{ext}"
        return serve_images(full_path)  # Now this function is defined above
    
    # Add handler for Next.js image optimization
    @app.route('/_next/image')
    def next_image_optimization():
        """Handle Next.js image optimization requests"""
        url = request.args.get('url', '')
        width = request.args.get('w', '256')
        quality = request.args.get('q', '75')
        

        if not url:
            return "Missing url parameter", 400
        
        # Generate cache path
        cache_key = f"{url.replace('/', '_')}_{width}_{quality}"
        cache_dir = os.path.join(app.root_path, 'image_cache')
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, cache_key)
        
        # Check if cached
        if os.path.exists(cache_path):
            logger.info(f"Serving cached image: {cache_path}")
            return send_file(cache_path)
        
        # Proxy to original
        try:
            proxy_url = f"https://overworld.illuvium.io/_next/image?url={url}&w={width}&q={quality}"
            logger.info(f"Proxying image: {proxy_url}")
            
            response = requests.get(proxy_url, stream=True)
            
            if response.status_code == 200:
                # Save to cache
                with open(cache_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Serve file
                return send_file(cache_path)
            else:
                return "Image not found", 404
        except Exception as e:
            logger.error(f"Error proxying image: {str(e)}")
            return "Error processing image", 500
    
    # Add direct route for JS files that are causing issues
    @app.route('/_next/<path:filename>')
    def serve_next_files(filename):
        """Direct handler for Next.js files"""
        # Special handling for problematic JS files
        if filename.endswith('.js'):
            try:
                url = f"https://overworld.illuvium.io/_next/{filename}"
                logger.info(f"Direct proxying JS: {url}")
                
                response = requests.get(url, stream=True)
                
                if response.status_code == 200:
                    # Create directory structure
                    local_path = os.path.join(app.root_path, '_next', filename)
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    
                    # Save as binary
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Stream directly from memory to avoid any text processing
                    return Response(
                        io.BytesIO(response.content),
                        mimetype='application/javascript',
                        headers={
                            'Content-Type': 'application/javascript',
                            'Cache-Control': 'no-cache'  # Don't cache during dev
                        }
                    )
                else:
                    return f"File not found: {filename}", 404
            except Exception as e:
                logger.error(f"Error with JS file {filename}: {str(e)}")
                return "Error processing file", 500
        
        # Regular handling for other files
        local_path = os.path.join(app.root_path, '_next', filename)
        if os.path.exists(local_path):
            return send_file(local_path)
        
        # Proxy other files
        try:
            url = f"https://overworld.illuvium.io/_next/{filename}"
            response = requests.get(url, stream=True)
            
            if response.status_code == 200:
                # Save file
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                return send_file(local_path)
            else:
                return f"File not found: {filename}", 404
        except Exception as e:
            logger.error(f"Error with file {filename}: {str(e)}")
            return "Error processing file", 500
    # Add this function to your init_static_files function in static_files.py

    @app.route('/blob/<path:path>')
    def serve_blob_resources(path):
        """Handle blob resources (images and videos) for autodrone feature"""
        logger.info(f"Serving blob resource: {path}")
        
        # Create blob directory structure if it doesn't exist
        blob_dir = os.path.join(app.root_path, 'blob')
        os.makedirs(blob_dir, exist_ok=True)
        
        # Full local path for the requested resource
        local_path = os.path.join(blob_dir, path)
        local_dir = os.path.dirname(local_path)
        
        # Check if directory exists, create if not
        os.makedirs(local_dir, exist_ok=True)
        
        # Check if file exists locally
        if os.path.exists(local_path) and os.path.isfile(local_path):
            logger.info(f"Serving local blob file: {local_path}")
            return send_file(local_path)
        
        # File doesn't exist locally, try to proxy from original site
        try:
            url = f"https://overworld.illuvium.io/blob/{path}"
            logger.info(f"Proxying blob resource from: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True)
            
            if response.status_code == 200:
                # Save file for future requests
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                logger.info(f"Saved blob resource to: {local_path}")
                
                # Determine content type based on file extension
                content_type = response.headers.get('Content-Type')
                if not content_type:
                    if path.endswith('.webp'):
                        content_type = 'image/webp'
                    elif path.endswith('.webm'):
                        content_type = 'video/webm'
                    elif path.endswith('.mov'):
                        content_type = 'video/quicktime'
                    else:
                        content_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
                
                # Serve the downloaded file
                return send_file(
                    local_path,
                    mimetype=content_type
                )
            else:
                logger.warning(f"Failed to proxy blob resource: {response.status_code} - {url}")
                return f"Resource not found: {path}", 404
        except Exception as e:
            logger.error(f"Error proxying blob resource: {str(e)} - {url}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error fetching resource: {str(e)}", 500

        # Add this fallback route for any other autodrone resources
    @app.route('/autodrone/<path:path>')
    def serve_autodrone_resources(path):
        """Fallback handler for autodrone resources"""
        logger.info(f"Serving autodrone resource: {path}")
        
        # Check if the file exists in several possible locations
        possible_locations = [
            os.path.join(app.root_path, 'autodrone', path),
            os.path.join(app.root_path, '_next', 'autodrone', path),
            os.path.join(app.root_path, '_next', 'static', 'autodrone', path)
        ]
        
        for location in possible_locations:
            if os.path.exists(location) and os.path.isfile(location):
                logger.info(f"Found autodrone resource at: {location}")
                return send_file(location)
        
        # If not found locally, try to proxy from original site
        try:
            url = f"https://overworld.illuvium.io/autodrone/{path}"
            logger.info(f"Proxying autodrone resource from: {url}")
            
            response = requests.get(url, stream=True)
            
            if response.status_code == 200:
                # Save for future use
                save_location = os.path.join(app.root_path, 'autodrone', path)
                os.makedirs(os.path.dirname(save_location), exist_ok=True)
                
                with open(save_location, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                return send_file(save_location)
            else:
                logger.warning(f"Failed to proxy autodrone resource: {response.status_code}")
                return f"Resource not found: {path}", 404
        except Exception as e:
            logger.error(f"Error proxying autodrone resource: {str(e)}")
            return f"Error fetching resource: {str(e)}", 500


    