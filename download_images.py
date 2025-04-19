import os
import requests
import urllib.parse

def download_image(url, save_path):
    """Download an image from a URL and save it to a path"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Download the image
        response = requests.get(url, stream=True)
        
        if response.status_code == 200:
            # Save the image
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"✅ Downloaded: {save_path}")
            return True
        else:
            print(f"❌ Failed to download {url}: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error downloading {url}: {str(e)}")
        return False

def main():
    # Base URL for the original site
    base_url = "https://overworld.illuvium.io"
    
    # List of images to download
    images = [
        "/images/banners/banner-autodrone.webp",
        "/images/play-now/personalise_experience/Scoriox_RangerSkin.webp",
        "/images/play-now/personalise_experience/Adoredo_RangerSkin.webp",
        "/images/play-now/personalise_experience/card-axodon.webp",
        "/images/play-now/personalise_experience/card-scoriox.webp",
        "/images/play-now/personalise_experience/card-adoredo.webp",
        "/images/play-now/bgs/bg-shadow.webp"
    ]
    
    print("Downloading images...")
    
    # Download each image
    success_count = 0
    for image_path in images:
        # Construct the full URL
        url = f"{base_url}{image_path}"
        
        # Remove leading slash for the save path
        save_path = image_path.lstrip('/')
        
        # Download the image
        if download_image(url, save_path):
            success_count += 1
    
    # Print summary
    total_images = len(images)
    print(f"\nSummary: {success_count}/{total_images} images downloaded")
    
    if success_count < total_images:
        print(f"Warning: {total_images - success_count} images failed to download!")
    else:
        print("All images downloaded successfully!")

if __name__ == "__main__":
    main()
