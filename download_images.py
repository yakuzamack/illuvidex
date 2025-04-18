import os
import requests
from urllib.parse import urljoin

# Base URL
BASE_URL = "https://overworld.illuvium.io"

# List of images to download
IMAGES = [
    "/images/seo/website-card.png",
    "/images/seo/favicon-32x32.png",
    "/images/banners/banner-autodrone.webp",
    "/images/home/illuvium-overworld.webp",
    "/images/play-now/logos/epic-game-logo-text-white.svg",
    "/images/play-now/logos/available-on-text-white.svg",
    "/images/play-now/bgs/bg-shadow-transparent.webp",
    "/images/icons/play.webp",
    "/images/play-now/cards/card-1.webp"
]

def download_image(url, local_path):
    """Download an image from the given URL and save it to the local path."""
    try:
        response = requests.get(url, verify=False)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded: {url} -> {local_path}")
        else:
            print(f"Failed to download {url}: Status code {response.status_code}")
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")

def main():
    for image_path in IMAGES:
        url = urljoin(BASE_URL, image_path)
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path.lstrip('/'))
        download_image(url, local_path)

if __name__ == "__main__":
    main() 