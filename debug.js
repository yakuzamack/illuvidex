// Debug script to monitor asset loading and prevent error pages
(function() {
    // Store original fetch and XMLHttpRequest
    const originalFetch = window.fetch;
    const originalXHR = window.XMLHttpRequest;

    // Override fetch
    window.fetch = async function(resource, options) {
        try {
            const response = await originalFetch(resource, options);
            if (!response.ok) {
                console.warn(`[Debug] Fetch failed for ${resource}:`, response.status);
                // Return empty response instead of throwing
                return new Response('', { status: 200, statusText: 'OK' });
            }
            return response;
        } catch (error) {
            console.warn(`[Debug] Fetch error for ${resource}:`, error);
            // Return empty response instead of throwing
            return new Response('', { status: 200, statusText: 'OK' });
        }
    };

    // Override XMLHttpRequest
    window.XMLHttpRequest = function() {
        const xhr = new originalXHR();
        const originalOpen = xhr.open;
        const originalSend = xhr.send;

        xhr.open = function(method, url) {
            this._url = url;
            return originalOpen.apply(this, arguments);
        };

        xhr.send = function() {
            this.addEventListener('error', (e) => {
                console.warn(`[Debug] XHR error for ${this._url}:`, e);
                // Prevent error from propagating
                e.stopPropagation();
            });
            return originalSend.apply(this, arguments);
        };

        return xhr;
    };

    // Monitor script loading
    const originalCreateElement = document.createElement;
    document.createElement = function(tagName) {
        const element = originalCreateElement.call(document, tagName);
        if (tagName.toLowerCase() === 'script') {
            element.addEventListener('error', (e) => {
                console.warn(`[Debug] Script load error:`, e);
                // Prevent error from propagating
                e.stopPropagation();
            });
        }
        return element;
    };

    // Monitor image loading
    const originalImage = window.Image;
    window.Image = function() {
        const img = new originalImage();
        img.addEventListener('error', (e) => {
            console.warn(`[Debug] Image load error:`, e);
            // Prevent error from propagating
            e.stopPropagation();
        });
        return img;
    };

    // Prevent Next.js error page
    window.addEventListener('error', (e) => {
        console.warn(`[Debug] Global error:`, e);
        // Prevent error from propagating
        e.stopPropagation();
        e.preventDefault();
        return false;
    });

    // Log all asset requests
    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            if (entry.initiatorType === 'script' || entry.initiatorType === 'img' || entry.initiatorType === 'css') {
                console.log(`[Debug] Asset loaded: ${entry.name}`);
            }
        }
    });
    observer.observe({ entryTypes: ['resource'] });

    console.log('[Debug] Debug script loaded successfully');
})(); 