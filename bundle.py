from pathlib import Path
from urllib.parse import urlparse

# Set base directory and output path
base_dir = Path("jsfiles")
output_file = Path("bundle.js")
output_file.touch(exist_ok=True)

# Define folders to scan
folders = [
    base_dir,
    base_dir / "7c93fa6a",
    base_dir / "037b440f",
]

# External JS files
external_js_links = [
    "https://cdn.jsdelivr.net/gh/ethereumjs/browser-builds/dist/ethereumjs-tx/ethereumjs-tx-1.3.3.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/ethers/5.7.2/ethers.umd.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/web3/4.0.3/web3.min.js"
]

# Preconnect domains
preconnect_domains = [
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com"
]

# Helper: Get domain
def get_domain(url):
    return urlparse(url).netloc

# Generate bundle.js
def bundle_assets():
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("// Auto-generated bundle.js to dynamically inject assets\n\n")

        # Preconnects
        for domain in preconnect_domains:
            out.write(f"document.head.insertAdjacentHTML('beforeend', `<!-- Preconnect to {domain} -->\n")
            out.write(f"<link rel='preconnect' href='https://{domain}' crossorigin='anonymous'>`);\n\n")

        # External scripts
        for url in external_js_links:
            out.write(f"document.head.insertAdjacentHTML('beforeend', `<!-- External JS: {url} -->\n")
            out.write(f"<script src='{url}'></script>`);\n\n")

        # Local assets
        for folder in folders:
            if folder.exists():
                for file in folder.rglob("*.*"):
                    rel_path = f"/jsfiles/{file.relative_to(base_dir)}"
                    tag = ""
                    if file.suffix == ".js":
                        tag = f"<script src='{rel_path}'></script>"
                    elif file.suffix == ".css":
                        tag = f"<link rel='stylesheet' href='{rel_path}'>"
                    elif file.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
                        tag = f"<!-- <img src='{rel_path}' alt='{file.stem}'> -->"
                    if tag:
                        out.write(f"document.head.insertAdjacentHTML('beforeend', `// === {file.name} ===\n{tag}`);\n\n")

    print(f"✅ bundle.js created successfully at: {output_file.resolve()}")

# Run it
bundle_assets()
