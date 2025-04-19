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
   
})(); 