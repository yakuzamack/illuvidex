#!/bin/bash

# ===========================================
# Complete Frontend Website Converter v1.0.0
# ===========================================

# Color configuration
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Script configuration
URL=$1
PROJECT_NAME=${2:-"cloned-site"}
PROXY_ENABLED=${3:-"false"}
MAX_RETRIES=3
WAIT_TIME=2
TIMEOUT=30
MAX_PARALLEL_DOWNLOADS=5

# Load proxy configuration from environment if available
PROXY_URL=${PROXY_URL:-"http://gate2.proxyfuel.com:2000"}
PROXY_AUTH=${PROXY_AUTH:-"anasjamrani007.outlook.com:dzzrfc"}

# Dependencies array
FRONTEND_DEPS=(
    "axios"
    "@tanstack/react-query"
    "framer-motion"
    "react-intersection-observer"
    "@headlessui/react"
    "http-proxy-middleware"
    "swr"
    "zustand"
    "@hookform/resolvers"
    "zod"
    "clsx"
    "tailwind-merge"
    "next-themes"
)

DEV_DEPS=(
    "@types/node"
    "@typescript-eslint/eslint-plugin"
    "@typescript-eslint/parser"
    "autoprefixer"
    "postcss"
    "prettier"
    "prettier-plugin-tailwindcss"
    "eslint-config-prettier"
)

# ==================
# Helper Functions
# ==================

get_timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

log_error() {
    echo -e "${RED}[$(get_timestamp)] ❌ Error: $1${NC}" >&2
}

log_success() {
    echo -e "${GREEN}[$(get_timestamp)] ✅ Success: $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(get_timestamp)] ⚠️  Warning: $1${NC}"
}

log_info() {
    echo -e "${BLUE}[$(get_timestamp)] ℹ️  Info: $1${NC}"
}

error_exit() {
    log_error "$1"
    exit 1
}

# Dependency checking
check_dependencies() {
    local missing_deps=()
    
    log_info "Checking required dependencies..."
    
    for cmd in wget npm npx sed find curl parallel; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        error_exit "Missing required dependencies: ${missing_deps[*]}"
    fi
    
    log_success "All dependencies found!"
}

# Validate URL
validate_url() {
    log_info "Validating URL: $URL"
    
    if [[ ! $URL =~ ^https?:// ]]; then
        error_exit "Invalid URL format. Please provide a valid HTTP/HTTPS URL."
    fi
    
    if ! curl --output /dev/null --silent --head --fail "$URL"; then
        error_exit "URL is not accessible: $URL"
    fi
    
    log_success "URL validated successfully!"
}

# ==================
# Project Creation
# ==================

create_project() {
    log_info "Creating Next.js project: $PROJECT_NAME"
    
    CREATE_NEXT_APP_CMD="npx create-next-app@latest $PROJECT_NAME \
        --typescript \
        --tailwind \
        --eslint \
        --app \
        --src-dir \
        --import-alias \"@/*\" \
        --no-use-turbopack \
        --use-npm"
    
    if ! eval $CREATE_NEXT_APP_CMD; then
        error_exit "Failed to create Next.js project"
    fi
    
    log_success "Next.js project created successfully!"
}

# ==================
# Asset Download
# ==================

download_frontend() {
    log_info "Starting website download..."
    
    local wget_opts=(
        --recursive
        --no-clobber
        --page-requisites
        --html-extension
        --convert-links
        --restrict-file-names=windows
        --domains "$(echo $URL | awk -F[/:] '{print $4}')"
        --no-parent
        --reject "*.php,*.asp,*.aspx,*.jsp,*.cgi,*.pdf,*.doc,*.docx,*.zip"
        --timeout=$TIMEOUT
        --tries=$MAX_RETRIES
        --retry-connrefused
        --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        --no-check-certificate
    )

    if [ "$PROXY_ENABLED" = "true" ]; then
        log_info "Using proxy server..."
        wget_opts+=(--proxy=on --proxy-user="$PROXY_AUTH" --proxy="$PROXY_URL")
    fi

    # Create wget config
    cat > wget.config << EOL
robots = off
recursive = on
adjust_extension = on
convert_links = on
timeout = $TIMEOUT
tries = $MAX_RETRIES
retry_connrefused = on
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
no_check_certificate = on
EOL

    mkdir -p ./downloaded-site

    if ! wget "${wget_opts[@]}" "$URL" -P ./downloaded-site; then
        log_warning "wget failed, trying curl as fallback..."
        if [ "$PROXY_ENABLED" = "true" ]; then
            curl -x "$PROXY_URL" -U "$PROXY_AUTH" -L "$URL" -o "./downloaded-site/index.html"
        else
            curl -L "$URL" -o "./downloaded-site/index.html"
        fi
    fi

    if [ ! -f "./downloaded-site/index.html" ]; then
        log_warning "Failed to download the website. Creating a minimal index.html..."
        cat > ./downloaded-site/index.html << EOL
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Illuvium Overworld</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }
        h1 {
            color: #333;
        }
        p {
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Illuvium Overworld</h1>
        <p>This is a placeholder page. The website content could not be downloaded.</p>
    </div>
</body>
</html>
EOL
    fi

    log_success "Website download completed!"
}

# ==================
# Frontend Processing
# ==================

setup_project_structure() {
    cd $PROJECT_NAME

    # Create directory structure
    local directories=(
        "src/components/ui"
        "src/components/layout"
        "src/hooks"
        "src/utils"
        "src/styles"
        "src/lib"
        "src/types"
        "src/store"
        "src/context"
        "src/middleware"
        "public/assets/css"
        "public/assets/js"
        "public/assets/images"
        "public/assets/fonts"
        "public/assets/icons"
    )

    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
    done

    cd ..
    log_success "Project structure created!"
}

process_assets() {
    local base_domain=$(echo $URL | awk -F[/:] '{print $4}')
    cd $PROJECT_NAME

    log_info "Processing assets..."

    # Process CSS in parallel
    find ../downloaded-site -name "*.css" | parallel -j $MAX_PARALLEL_DOWNLOADS '
        cat {} | tr -d "\n\r" | sed "s/  //g" > "public/assets/css/$(basename {})"
    '

    # Process JS in parallel
    find ../downloaded-site -name "*.js" ! -name "*.min.js" | parallel -j $MAX_PARALLEL_DOWNLOADS '
        cat {} | tr -d "\n\r" | sed "s/  //g" > "public/assets/js/$(basename {})"
    '

    # Process images in parallel
    find ../downloaded-site -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.gif" -o -name "*.svg" \) | \
        parallel -j $MAX_PARALLEL_DOWNLOADS 'cp {} public/assets/images/'

    cd ..
    log_success "Assets processed successfully!"
}

# ==================
# React Components
# ==================

create_components() {
    cd $PROJECT_NAME

    # Create base page component with improved error handling
    cat > src/app/page.tsx << 'EOL'
"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useTheme } from "next-themes";

export default function Home() {
    const [isLoaded, setIsLoaded] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { theme, setTheme } = useTheme();

    useEffect(() => {
        const loadContent = async () => {
            try {
                // Load external styles
                const styles = document.querySelectorAll("link[rel=stylesheet]");
                styles.forEach(style => document.head.appendChild(style.cloneNode(true)));
                setIsLoaded(true);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load content");
                log_error("Failed to load content: " + err);
            }
        };

        loadContent();
    }, []);

    return (
        <main className="min-h-screen">
            {error ? (
                <div className="flex h-screen items-center justify-center">
                    <div className="text-lg text-red-500">Error: {error}</div>
                </div>
            ) : isLoaded ? (
                <div id="content" className="frontend-content" />
            ) : (
                <div className="flex h-screen items-center justify-center">
                    <div className="text-lg">Loading...</div>
                </div>
            )}
        </main>
    );
}
EOL

    # Create layout component with improved metadata
    cat > src/app/layout.tsx << 'EOL'
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "next-themes";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "Converted Website",
    description: "Frontend conversion",
    viewport: "width=device-width, initial-scale=1",
    robots: "index, follow",
    themeColor: "#ffffff",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <meta charSet="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <link rel="stylesheet" href="/assets/css/styles.css" />
            </head>
            <body className={inter.className}>
                <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
                    {children}
                </ThemeProvider>
                <script src="/assets/js/frontend.js" defer />
            </body>
        </html>
    );
}
EOL

    cd ..
    log_success "React components created!"
}

# ==================
# Security Setup
# ==================

setup_security() {
    cd $PROJECT_NAME
    
    # Create security middleware with enhanced CSP
    cat > src/middleware.ts << 'EOL'
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
    const response = NextResponse.next();

    // Add security headers
    const headers = response.headers;
    headers.set("X-DNS-Prefetch-Control", "on");
    headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
    headers.set("X-Frame-Options", "SAMEORIGIN");
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("X-XSS-Protection", "1; mode=block");
    headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");

    if (process.env.NODE_ENV === "production") {
        headers.set("Content-Security-Policy", `
            default-src 'self';
            script-src 'self' 'unsafe-inline' 'unsafe-eval';
            style-src 'self' 'unsafe-inline';
            img-src 'self' data: https:;
            font-src 'self' data:;
            connect-src 'self' https:;
            frame-ancestors 'self';
            form-action 'self';
            base-uri 'self';
            object-src 'none';
            media-src 'self';
            worker-src 'self';
        `.replace(/\s+/g, " ").trim());
    }

    return response;
}

export const config = {
    matcher: "/:path*",
};
EOL

    cd ..
    log_success "Security configuration completed!"
}

# ==================
# Project Configuration
# ==================

setup_config() {
    cd $PROJECT_NAME

    # Update next.config.js with enhanced configuration
    cat > next.config.js << 'EOL'
/** @type {import('next').NextConfig} */
const nextConfig = {
    images: {
        domains: ["*"],
        unoptimized: true,
    },
    reactStrictMode: true,
    compiler: {
        removeConsole: process.env.NODE_ENV === "production",
    },
    experimental: {
        optimizeCss: true,
        optimizePackageImports: ["@headlessui/react", "framer-motion"],
    },
    async headers() {
        return process.env.NODE_ENV === "development" ? [] : [
            {
                source: "/:path*",
                headers: [
                    { key: "X-DNS-Prefetch-Control", value: "on" },
                    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
                    { key: "X-Frame-Options", value: "SAMEORIGIN" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "X-XSS-Protection", value: "1; mode=block" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" }
                ],
            },
        ];
    },
};

module.exports = nextConfig;
EOL

    # Create environment files with enhanced security
    cat > .env.local << EOL
NEXT_PUBLIC_SITE_URL=$URL
PROXY_ENABLED=$PROXY_ENABLED
NEXT_PUBLIC_APP_ENV=development
NEXT_PUBLIC_APP_VERSION=1.0.0
EOL

    if [ "$PROXY_ENABLED" = "true" ]; then
        cat >> .env.local << EOL
PROXY_URL=$PROXY_URL
PROXY_AUTH=$PROXY_AUTH
EOL
    fi

    cd ..
    log_success "Project configuration completed!"
}

# ==================
# Dependencies Setup
# ==================

install_dependencies() {
    cd $PROJECT_NAME
    
    log_info "Installing dependencies..."

    # Install frontend dependencies with legacy peer deps
    for dep in "${FRONTEND_DEPS[@]}"; do
        npm install $dep --legacy-peer-deps --no-audit --no-fund || log_warning "Failed to install $dep" &
    done
    wait

    # Install development dependencies with legacy peer deps
    for dep in "${DEV_DEPS[@]}"; do
        npm install -D $dep --legacy-peer-deps --no-audit --no-fund || log_warning "Failed to install $dep" &
    done
    wait

    cd ..
    log_success "Dependencies installed!"
}

# ==================
# Main Execution
# ==================

main() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}Frontend Website Converter v1.0.0${NC}"
    echo -e "${CYAN}================================${NC}"

    [ -z "$URL" ] && error_exit "Please provide a URL to download"
    
    check_dependencies
    validate_url
    
    log_info "Starting conversion process..."
    
    create_project
    setup_project_structure
    download_frontend
    process_assets
    create_components
    setup_security
    setup_config
    install_dependencies
    
    log_success "Frontend conversion completed successfully! 🎉"
    echo -e "
${GREEN}Next steps:${NC}
1. cd $PROJECT_NAME
2. npm run dev

${BLUE}Access your frontend at:${NC} http://localhost:3000

${YELLOW}Note:${NC} 
- Security headers are relaxed in development mode
- Full security measures are active in production
- Use 'npm run build' for production deployment
- Theme switching is enabled by default
- Parallel processing is enabled for better performance

${PURPLE}Happy coding! 🚀${NC}"
}

# Execute main function with all arguments
main "$@"