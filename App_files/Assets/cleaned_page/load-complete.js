// Handle loading state completion
(function() {
    'use strict';

    // Function to check if all assets are loaded
    function checkAssetsLoaded() {
        // Check if all images are loaded
        const images = document.getElementsByTagName('img');
        for (let img of images) {
            if (!img.complete) return false;
        }

        // Check if all scripts are loaded
        const scripts = document.getElementsByTagName('script');
        for (let script of scripts) {
            if (script.src && !script.loaded) return false;
        }

        // Check if all stylesheets are loaded
        const stylesheets = document.getElementsByTagName('link');
        for (let sheet of stylesheets) {
            if (sheet.rel === 'stylesheet' && !sheet.loaded) return false;
        }

        return true;
    }

    // Function to remove loading state
    function removeLoadingState() {
        // Remove loading overlay if it exists
        const loadingOverlay = document.querySelector('.loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.remove();
        }

        // Remove loading class from body
        document.body.classList.remove('loading');

        // Show main content
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.style.display = 'block';
        }
    }

    // Check assets periodically
    const checkInterval = setInterval(() => {
        if (checkAssetsLoaded()) {
            clearInterval(checkInterval);
            removeLoadingState();
        }
    }, 100);

    // Also check on window load
    window.addEventListener('load', () => {
        clearInterval(checkInterval);
        removeLoadingState();
    });

    // Force remove loading state after 5 seconds
    setTimeout(() => {
        clearInterval(checkInterval);
        removeLoadingState();
    }, 5000);
})(); 