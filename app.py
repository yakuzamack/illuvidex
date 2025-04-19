from flask import Flask
import logging
from modules.content_proxy import init_content_proxy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize content proxy routes
init_content_proxy(app)

if __name__ == '__main__':
    logger.info("Starting Illuvidex application")
    app.run(host='0.0.0.0', port=5000, debug=True)
