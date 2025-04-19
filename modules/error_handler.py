def init_error_handlers(app):
    """Initialize error handlers"""
    @app.errorhandler(404)
    def page_not_found(e):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def server_error(e):
        return "Server error", 500