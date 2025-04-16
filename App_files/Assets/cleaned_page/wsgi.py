from server import CustomHandler
from wsgiref.simple_server import make_server
import io
import sys

class WSGIHandler:
    def __init__(self):
        self.handler = CustomHandler

    def __call__(self, environ, start_response):
        # Convert WSGI environ to HTTP request
        path = environ.get('PATH_INFO', '/')
        method = environ.get('REQUEST_METHOD', 'GET')
        
        # Create a StringIO object to capture the response
        response = io.StringIO()
        headers = []
        
        # Create a custom response writer
        def write(data):
            response.write(data.decode('utf-8') if isinstance(data, bytes) else data)
        
        def send_response(code, message=None):
            status = f"{code} {message}" if message else str(code)
            start_response(status, headers)
        
        # Create a mock request handler
        handler = self.handler(
            None,  # request
            (environ.get('REMOTE_ADDR', '127.0.0.1'), 0),  # client_address
            None,  # server
        )
        
        # Set up the handler's response methods
        handler.wfile = response
        handler.send_response = send_response
        handler.send_header = lambda k, v: headers.append((k, v))
        handler.end_headers = lambda: None
        
        # Handle the request
        if method == 'GET':
            handler.do_GET()
        elif method == 'POST':
            handler.do_POST()
        else:
            handler.send_response(405)
            handler.end_headers()
            handler.wfile.write('Method Not Allowed')
        
        return [response.getvalue().encode('utf-8')]

wsgi_app = WSGIHandler() 