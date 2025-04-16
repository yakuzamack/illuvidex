// Prevent debugger connections and handle loading state
(function() {
  // Block debugger connections
  Object.defineProperty(window, 'debugger', {
    get: function() {
      return false;
    },
    set: function() {
      return false;
    }
  });

  // Override console methods to prevent debugger
  const noop = function() {};
  ['debug', 'debugger'].forEach(function(method) {
    console[method] = noop;
  });

  // Handle loading state
  function removeLoadingState() {
    document.documentElement.classList.remove('has-no-js');
    const loadingElements = document.querySelectorAll('[data-loading]');
    loadingElements.forEach(el => el.removeAttribute('data-loading'));
    
    // Force remove any loading overlays
    const overlays = document.querySelectorAll('.loading-overlay, [class*="loading"], [id*="loading"]');
    overlays.forEach(el => {
      el.style.display = 'none';
      el.remove();
    });
  }

  // Remove loading state when all resources are loaded
  window.addEventListener('load', function() {
    removeLoadingState();
  });

  // Fallback: Force remove loading state after 3 seconds
  setTimeout(removeLoadingState, 3000);

  // Handle failed resource loading
  window.addEventListener('error', function(e) {
    if (e.target.tagName === 'SCRIPT' || e.target.tagName === 'LINK') {
      e.target.remove();
    }
  }, true);
})(); 