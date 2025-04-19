import os
import json
import glob  # Add this line
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import requests as http_requests


def query_local_llm(prompt, system_message="You are a helpful assistant.", temperature=0.7):
    """
    Query the local LLM running on localhost:1234
    """
    try:
        response = http_requests.post(
            "http://localhost:1234/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "ministral-8b-instruct-2410",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": -1,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            app.logger.error(f"Error querying LLM: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"Exception when querying LLM: {str(e)}")
        return None

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.template_filter('strftime')
def _jinja2_filter_datetime(timestamp, fmt=None):
    """Convert a timestamp to a formatted date string"""
    if fmt is None:
        fmt = '%B %d, %Y'
    return datetime.fromtimestamp(timestamp).strftime(fmt)

def is_llm_server_available():
    """Check if the local LLM server is available"""
    try:
        response = http_requests.get("http://localhost:1234/health")
        return response.status_code == 200
    except:
        return False

# Use this in your routes
@app.context_processor
def inject_llm_status():
    """Make LLM status available to all templates"""
    return {'llm_available': is_llm_server_available()}# Load blocked IPs, ISPs, and organizations from files
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

# Load blocked items on startup
BLOCKED_IPS = load_blocked_items('data/ips.txt')
BLOCKED_ISPS = load_blocked_items('data/isps.txt')
BLOCKED_ORGS = load_blocked_items('data/organisations.txt')

# Get client's real IP address
def get_client_ip():
    """Get the client's real IP address, considering X-Forwarded-For header"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get the real IP
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    else:
        # If not behind a proxy, get the direct IP
        ip = request.remote_addr
    return ip

# Server-side validation function
def validate_ip_server_side(ip):
    """
    Server-side validation function
    Returns a tuple of (is_blocked, reason)
    """
    # Check if IP is directly blocked
    if ip.lower() in BLOCKED_IPS:
        return True, "IP address is directly blocked"
    
    # Check with IP-API Pro
    try:
        ip_api_response = requests.get(
            f"https://pro.ip-api.com/json/{ip}?fields=66842623&key=ipapiq9SFY1Ic4",
            headers={
                'Accept': '*/*',
                'Origin': 'https://members.ip-api.com',
                'Referer': 'https://members.ip-api.com/',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
            }
        )
        ip_api_data = ip_api_response.json()
        
        # Check if ISP or organization is blocked
        if "isp" in ip_api_data and ip_api_data["isp"].lower() in BLOCKED_ISPS:
            return True, f"ISP '{ip_api_data['isp']}' is blocked"
            
        if "org" in ip_api_data and ip_api_data["org"].lower() in BLOCKED_ORGS:
            return True, f"Organization '{ip_api_data['org']}' is blocked"
    except Exception:
        pass
    
    # Check with Avast
    try:
        avast_response = requests.get(
            f"https://ip-info.ff.avast.com/v2/info?ip={ip}",
            headers={
                'Accept': '*/*',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
            }
        )
        avast_data = avast_response.json()
        
        # Check if organization from Avast is blocked
        if "organization" in avast_data and avast_data["organization"].lower() in BLOCKED_ORGS:
            return True, f"Organization '{avast_data['organization']}' is blocked"
            
        if "isp" in avast_data and avast_data["isp"].lower() in BLOCKED_ISPS:
            return True, f"ISP '{avast_data['isp']}' is blocked"
    except Exception:
        pass
    
    # Check with Mind-Media proxy
    try:
        # Simple GET request without any special headers or payload
        mind_media_response = requests.get(f"http://proxy.mind-media.com/block/proxycheck.php?ip={ip}")
        
        # Handle raw Y/N response
        raw_response = mind_media_response.text.strip()
        
        # Check if proxy is detected
        if raw_response == "Y":
            return True, "Proxy detected by Mind-Media"
    except Exception:
        pass
    
    return False, None

# Decorator for IP validation
def validate_ip_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip validation for API endpoints and static files
        if request.path.startswith('/api/') or request.path.startswith('/static/'):
            return f(*args, **kwargs)
        
        # Get the user's IP address
        user_ip = get_client_ip()
        
        # Validate the IP
        is_blocked, reason = validate_ip_server_side(user_ip)
        
        if is_blocked:
            # Store the reason in the session for display
            app.logger.warning(f"Blocked access from IP {user_ip}: {reason}")
            # Render the 403 template with the same URL
            return render_template('403.html', reason=reason), 403
        
        # IP is allowed, proceed with the request
        return f(*args, **kwargs)
    return decorated_function

# Apply the validation decorator to all routes
@app.before_request
def validate_request():
    # Skip validation for API endpoints and static files
    if request.path.startswith('/api/') or request.path.startswith('/static/'):
        return None
    
    # Get the user's IP address
    user_ip = get_client_ip()
    
    # Skip validation for localhost (127.0.0.1)
    if user_ip == '127.0.0.1' or user_ip == 'localhost':
        return None
    
    # Validate the IP
    is_blocked, reason = validate_ip_server_side(user_ip)
    
    if is_blocked:
        # Store the reason for display
        app.logger.warning(f"Blocked access from IP {user_ip}: {reason}")
        # Render the 403 template with the same URL
        return render_template('403.html', reason=reason), 403
    
    # IP is allowed, proceed with the request
    return None
# Load blog posts
def load_blog_posts():
    posts = []
    post_files = glob.glob('data/posts/*.html')
    
    for file_path in post_files:
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                
            # Extract filename without extension for the post ID
            post_id = os.path.splitext(os.path.basename(file_path))[0]
            
            # Simple parsing to extract title from the first h1 tag
            title = "Untitled Post"
            if '<h1>' in content and '</h1>' in content:
                title = content.split('<h1>')[1].split('</h1>')[0]
            
            # Get file modification time for the date
            mod_time = os.path.getmtime(file_path)
            
            posts.append({
                'id': post_id,
                'title': title,
                'content': content,
                'date': mod_time,
                'url': f'/post/{post_id}'
            })
        except Exception as e:
            app.logger.error(f"Error loading post {file_path}: {str(e)}")
    
    # Sort posts by date (newest first)
    posts.sort(key=lambda x: x['date'], reverse=True)
    return posts

# Routes for the blog
@app.route('/')
def index():
    posts = load_blog_posts()
    return render_template('index.html', posts=posts)

@app.route('/post/<post_id>')
def view_post(post_id):
    # Sanitize post_id to prevent directory traversal
    post_id = os.path.basename(post_id)
    post_path = f'data/posts/{post_id}.html'
    
    if not os.path.exists(post_path):
        abort(404)
    
    try:
        with open(post_path, 'r') as file:
            content = file.read()
        
        # Simple parsing to extract title from the first h1 tag
        title = "Untitled Post"
        if '<h1>' in content and '</h1>' in content:
            title = content.split('<h1>')[1].split('</h1>')[0]
        
        post = {
            'id': post_id,
            'title': title,
            'content': content,
            'date': os.path.getmtime(post_path)
        }
        
        return render_template('post.html', post=post)
    except Exception as e:
        app.logger.error(f"Error loading post {post_path}: {str(e)}")
        abort(500)

# API endpoints for IP validation (same as before)
@app.route('/api/ip-lookup/<ip>')
def ip_lookup(ip):
    url = f"https://pro.ip-api.com/json/{ip}?fields=66842623&key=ipapiq9SFY1Ic4"
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Origin': 'https://members.ip-api.com',
        'Referer': 'https://members.ip-api.com/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    try:
        response = requests.get(url, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mind-media/<ip>')
def mind_media_proxy(ip):
    url = f"http://proxy.mind-media.com/block/proxycheck.php?ip={ip}"
    
    try:
        # Simple GET request without any special headers or payload
        response = requests.get(url)
        
        # Handle raw Y/N response
        raw_response = response.text.strip()
        
        # Convert the raw Y/N to a JSON response
        result = {
            ip: {
                "proxy": "yes" if raw_response == "Y" else "no",
                "raw_response": raw_response
            }
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/avast/<ip>')
def avast_ip_info(ip):
    url = f"https://ip-info.ff.avast.com/v2/info?ip={ip}"
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check/<ip>')
def check_ip(ip):
    """Check if IP is blocked based on local files and API data"""
    result = {
        "ip": ip,
        "blocked": False,
        "reason": None,
        "details": {}
    }
    
    # Check if IP is directly blocked
    if ip.lower() in BLOCKED_IPS:
        result["blocked"] = True
        result["reason"] = "IP address is directly blocked"
        return jsonify(result)
    
    # Check with IP-API Pro
    try:
        ip_api_response = requests.get(
            f"https://pro.ip-api.com/json/{ip}?fields=66842623&key=ipapiq9SFY1Ic4",
            headers={
                'Accept': '*/*',
                'Origin': 'https://members.ip-api.com',
                'Referer': 'https://members.ip-api.com/',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
            }
        )
        ip_api_data = ip_api_response.json()
        result["details"]["ip_api"] = ip_api_data
        
        # Check if ISP or organization is blocked
        if "isp" in ip_api_data and ip_api_data["isp"].lower() in BLOCKED_ISPS:
            result["blocked"] = True
            result["reason"] = f"ISP '{ip_api_data['isp']}' is blocked"
            return jsonify(result)
            
        if "org" in ip_api_data and ip_api_data["org"].lower() in BLOCKED_ORGS:
            result["blocked"] = True
            result["reason"] = f"Organization '{ip_api_data['org']}' is blocked"
            return jsonify(result)
    except Exception as e:
        result["details"]["ip_api_error"] = str(e)
    
    # Check with Avast
        # Check with Avast
    try:
        avast_response = requests.get(
            f"https://ip-info.ff.avast.com/v2/info?ip={ip}",
            headers={
                'Accept': '*/*',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
            }
        )
        avast_data = avast_response.json()
        result["details"]["avast"] = avast_data
        
        # Check if organization from Avast is blocked
        if "organization" in avast_data and avast_data["organization"].lower() in BLOCKED_ORGS:
            result["blocked"] = True
            result["reason"] = f"Organization '{avast_data['organization']}' is blocked"
            return jsonify(result)
            
        if "isp" in avast_data and avast_data["isp"].lower() in BLOCKED_ISPS:
            result["blocked"] = True
            result["reason"] = f"ISP '{avast_data['isp']}' is blocked"
            return jsonify(result)
    except Exception as e:
        result["details"]["avast_error"] = str(e)
    
    # Check with Mind-Media proxy
    try:
        # Simple GET request without any special headers or payload
        mind_media_response = requests.get(f"http://proxy.mind-media.com/block/proxycheck.php?ip={ip}")
        
        # Handle raw Y/N response
        raw_response = mind_media_response.text.strip()
        
        # Convert the raw Y/N to a structured format
        mind_media_data = {
            ip: {
                "proxy": "yes" if raw_response == "Y" else "no",
                "raw_response": raw_response
            }
        }
        
        result["details"]["mind_media"] = mind_media_data
        
        # Check if proxy is detected
        if mind_media_data.get(ip, {}).get("proxy") == "yes":
            result["blocked"] = True
            result["reason"] = "Proxy detected by Mind-Media"
            return jsonify(result)
    except Exception as e:
        result["details"]["mind_media_error"] = str(e)
    
    return jsonify(result)

# Create necessary directories and sample blog posts
def initialize_blog():
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # Create posts directory if it doesn't exist
    posts_dir = 'data/posts'
    if not os.path.exists(posts_dir):
        os.makedirs(posts_dir)
    
    # Create sample blog posts if none exist
    if not glob.glob('data/posts/*.html'):
        sample_posts = [
            {
                'id': 'welcome-to-my-blog',
                'title': 'Welcome to My Blog',
                'content': '''
<h1>Welcome to My Blog</h1>
<p>This is my first blog post. I'm excited to share my thoughts with you!</p>
<p>This blog is protected by an advanced IP validation system that blocks unwanted visitors.</p>
<p>Only legitimate users can access this content.</p>
'''
            },
            {
                'id': 'how-ip-validation-works',
                'title': 'How IP Validation Works',
                'content': '''
<h1>How IP Validation Works</h1>
<p>Our IP validation system checks multiple factors:</p>
<ul>
    <li>Direct IP blocking for known bad actors</li>
    <li>ISP and organization checking to block entire networks</li>
    <li>Proxy detection to prevent anonymized access</li>
</ul>
<p>This multi-layered approach provides robust protection against unwanted visitors.</p>
'''
            },
            {
                'id': 'future-plans',
                'title': 'Future Plans for This Blog',
                'content': '''
<h1>Future Plans for This Blog</h1>
<p>I have big plans for this blog in the future:</p>
<ol>
    <li>More regular content updates</li>
    <li>Enhanced security features</li>
    <li>User comments and interaction</li>
    <li>Subscription options for updates</li>
</ol>
<p>Stay tuned for more exciting developments!</p>
'''
            }
        ]
        
        for post in sample_posts:
            with open(f'data/posts/{post["id"]}.html', 'w') as file:
                file.write(post['content'])
    
    # Create blocked lists files if they don't exist
    for filename in ['data/ips.txt', 'data/isps.txt', 'data/organisations.txt']:
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                f.write('# One item per line\n')

# Initialize the blog when the app starts
initialize_blog()

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
@app.errorhandler(500)
def server_error(e):
    current_year = datetime.now().year
    return render_template('500.html', current_year=current_year), 500@app.route('/generate-post', methods=['GET', 'POST'])
def generate_post():
    """Generate a blog post using the LLM"""
    # Check if LLM is available
    if not is_llm_server_available():
        return render_template('error.html', 
                              error_title="LLM Not Available", 
                              error_message="The LLM server is not running. Please start it and try again.")
    
    if request.method == 'POST':
        topic = request.form.get('topic', '')
        
        if not topic:
            return render_template('generate_post.html', error="Please provide a topic.")
        
        # Generate blog post using the local LLM
        system_message = "You are a blog content creator. Write engaging, informative content with proper HTML formatting."
        prompt = f"Write a blog post about {topic}. Include an h1 title, paragraphs, and at least one list. Format the content in HTML."
        
        app.logger.info(f"Generating blog post about: {topic}")
        generated_content = query_local_llm(prompt, system_message)
        
        if not generated_content:
            return render_template('generate_post.html', 
                                  error="Failed to generate content. Please try again.",
                                  topic=topic)
        
        # Extract title from the content
        title = "Untitled Post"
        if '<h1>' in generated_content and '</h1>' in generated_content:
            title = generated_content.split('<h1>')[1].split('</h1>')[0]
        
        # Create a URL-friendly slug from the title
        import re
        from datetime import datetime
        slug = title.lower().replace(' ', '-')
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = f"{slug}-{timestamp}"
        
        # Save the generated post
        os.makedirs('data/posts', exist_ok=True)
        post_path = f'data/posts/{slug}.html'
        with open(post_path, 'w') as file:
            file.write(generated_content)
        
        app.logger.info(f"Generated blog post saved to: {post_path}")
        return redirect(url_for('view_post', post_id=slug))
    
    return render_template('generate_post.html')
@app.route('/post/<post_id>/comment', methods=['POST'])
@app.route('/admin/analyze-error', methods=['POST'])









@app.route('/test-llm')
def test_llm():
    """Test route to verify LLM integration"""
    import requests as http_requests
    
    try:
        # Check if LLM server is available
        llm_available = False
        try:
            response = http_requests.get("http://localhost:1234/health", timeout=2)
            llm_available = response.status_code == 200
        except:
            llm_available = False
        
        if not llm_available:
            return jsonify({
                "status": "error",
                "message": "LLM server is not available. Make sure it's running on localhost:1234."
            }), 500
        
        # Test the LLM with a simple prompt
        response = http_requests.post(
            "http://localhost:1234/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "ministral-8b-instruct-2410",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Write a short paragraph about blogs."}
                ],
                "temperature": 0.7,
                "max_tokens": -1,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result["choices"][0]["message"]["content"]
            
            return jsonify({
                "status": "success",
                "message": "LLM integration is working!",
                "response": llm_response
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to get a response from the LLM. Status code: {response.status_code}"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500        
@app.context_processor
def inject_now():
    """Make the current datetime available to all templates"""
    return {'now': datetime.now()}

@app.route('/generate-post', methods=['GET', 'POST'])
def generate_post():
    """Generate a blog post using the LLM"""
    # Import requests if not already imported
    import requests as http_requests
    import os
    from datetime import datetime
    import re
    
    if request.method == 'POST':
        topic = request.form.get('topic', '')
        
        if not topic:
            return render_template('generate_post.html', error="Please provide a topic.")
        
        # Try to connect to the LLM
        try:
            # Test if LLM is available
            llm_available = False
            try:
                response = http_requests.get("http://localhost:1234/health", timeout=2)
                llm_available = response.status_code == 200
            except:
                llm_available = False
            
            if not llm_available:
                return render_template('generate_post.html', 
                                      error="LLM server is not available. Please start it and try again.",
                                      topic=topic)
            
            # Generate blog post using the local LLM
            system_message = "You are a blog content creator. Write engaging, informative content with proper HTML formatting."
            prompt = f"Write a blog post about {topic}. Include an h1 title, paragraphs, and at least one list. Format the content in HTML."
            
            response = http_requests.post(
                "http://localhost:1234/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "ministral-8b-instruct-2410",
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": -1,
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                return render_template('generate_post.html', 
                                      error=f"Failed to generate content. LLM returned status code: {response.status_code}",
                                      topic=topic)
            
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            
            # Extract title from the content
            title = "Untitled Post"
            if '<h1>' in generated_content and '</h1>' in generated_content:
                title = generated_content.split('<h1>')[1].split('</h1>')[0]
            
            # Create a URL-friendly slug from the title
            slug = title.lower().replace(' ', '-')
            slug = re.sub(r'[^a-z0-9-]', '', slug)
            # Add timestamp to ensure uniqueness
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            slug = f"{slug}-{timestamp}"
            
            # Save the generated post
            os.makedirs('data/posts', exist_ok=True)
            post_path = f'data/posts/{slug}.html'
            with open(post_path, 'w') as file:
                file.write(generated_content)
            
            return redirect(url_for('view_post', post_id=slug))
            
        except Exception as e:
            return render_template('generate_post.html', 
                                  error=f"An error occurred: {str(e)}",
                                  topic=topic)
    
    return render_template('generate_post.html')

