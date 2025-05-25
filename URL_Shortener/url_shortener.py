from flask import Flask, render_template, request, jsonify, url_for # type: ignore
from flask_cors import CORS # type: ignore
from datetime import datetime
import string
import random
import re
from typing import Dict, Tuple
import logging
from urllib.parse import urlparse
import time
from functools import wraps

app = Flask(__name__)
CORS(app) # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
app.config.setdefault('SHORT_URL_BASE', None)  # If None, will use request.host_url

# In-memory storage
url_mappings: Dict[str, Dict] = {}
request_counts: Dict[str, Tuple[int, float]] = {}

def rate_limit(max_requests: int = 10, window: float = 60) -> callable:
    """Rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            now = time.time()
            ip = request.remote_addr
            
            if ip in request_counts:
                count, window_start = request_counts[ip]
                if now - window_start > window:
                    request_counts[ip] = (1, now)
                elif count >= max_requests:
                    logger.warning(f"Rate limit exceeded for IP: {ip}")
                    return jsonify({"error": "Rate limit exceeded"}), 429
                else:
                    request_counts[ip] = (count + 1, window_start)
            else:
                request_counts[ip] = (1, now)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

def generate_short_id(length: int = 6) -> str:
    """Generate a random short ID."""
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

@app.route('/')
def index():
    print(f"Static URL: {url_for('static', filename='css/style.css')}")
    return render_template('index.html')

@app.route('/api/shorten', methods=['POST'])
@rate_limit()
def shorten_url():
    print("Received request method:", request.method)  # Debug print
    print("Received data:", request.get_json())  # Debug print
    """
    Create a shortened URL from a long URL.
    
    The base URL for shortened links can be configured by setting app.config['SHORT_URL_BASE'].
    Example configurations:
    - app.config['SHORT_URL_BASE'] = 'https://example.com/short/'
    - app.config['SHORT_URL_BASE'] = 'https://mysite.com/url/'
    
    If SHORT_URL_BASE is not set, the application will use request.host_url as the base.
    
    Returns:
        JSON response with shortened URL details or error message
    """
    try:
        data = request.get_json()
        if not data or 'long_url' not in data:
            logger.error("Missing long_url in request")
            return jsonify({"error": "Missing long_url parameter"}), 400

        long_url = data['long_url']
        if not is_valid_url(long_url):
            logger.error(f"Invalid URL format: {long_url}")
            return jsonify({"error": "Invalid URL format"}), 400

        # Generate unique short ID
        while True:
            short_id = generate_short_id()
            if short_id not in url_mappings:
                break

        # Store the mapping
        created_at = datetime.utcnow().isoformat()
        url_mappings[short_id] = {
            "original_url": long_url,
            "created_at": created_at
        }

        # Use configured base URL or fall back to host URL
        base_url = app.config['SHORT_URL_BASE'] or request.host_url
        # Ensure base URL ends with a slash
        base_url = base_url if base_url.endswith('/') else f"{base_url}/"
        short_url = f"{base_url}{short_id}"
        
        logger.info(f"Created shortened URL: {short_url}")
        return jsonify({
            "short_url": short_url,
            "original_url": long_url,
            "created_at": created_at
        }), 201

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/test', methods=['GET'])
def test_route():
    return jsonify({"message": "Server is working"}), 200

if __name__ == '__main__':
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.methods} - {rule}")
    app.run(debug=True, port=5001)

