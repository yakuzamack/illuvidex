# Illuvium Proxy Server

A high-performance proxy server for Illuvium's overworld site with content modification capabilities.

## Features

- Content modification and injection
- High-performance serving with Gunicorn
- Automatic file caching
- Content compression
- Custom script injection
- URL redirection
- Button class modification

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the server:
```bash
gunicorn server:application -b 0.0.0.0:8000 -w 4
```

2. Access the site:
```
http://localhost:8000
```

## Configuration

The server can be configured by modifying the following in `server.py`:

- `ORIGINAL_SITE`: The original site URL
- `BASE_DIR`: Local directory for downloaded files
- Gunicorn options in `run_server()`

## Content Modification

The server can modify:
- JavaScript files (chunks)
- HTML content
- Button classes
- URLs
- Script injection

## Performance Optimizations

- LRU caching for frequently accessed content
- Gzip compression
- Gevent worker class
- Preloaded application
- Multiple worker processes

## License

[Your License Here] 