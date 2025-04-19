// Configuration
const buttonSelectors = {
  // Add your specific button selectors here
  // Examples:
  'connect-wallet': '.connect-wallet-button, [data-connect-wallet]',
  'submit-button': '.submit-btn, button[type="submit"]',
  // Add more as needed
};

// Text replacements
const textReplacements = {
  'Connect Wallet': 'Connect',
  'Sign In': 'Login',
  'Submit': 'Confirm',
  // Add more text replacements as needed
};

// Function to modify button text
function modifyButtonText() {
  console.log('🔄 Running button text modification');
  
  // Process each selector group
  Object.entries(buttonSelectors).forEach(([key, selector]) => {
    const elements = document.querySelectorAll(selector);
    
    elements.forEach(element => {
      // Check if the element's text needs replacement
      Object.entries(textReplacements).forEach(([original, replacement]) => {
        if (element.textContent.trim() === original) {
          console.log(`✅ Replacing "${original}" with "${replacement}" on element:`, element);
          element.textContent = replacement;
          
          // Add a data attribute to mark as processed
          element.setAttribute('data-text-modified', 'true');
        }
      });
    });
  });
}

// Set up MutationObserver to watch for DOM changes
function setupMutationObserver() {
  console.log('🔍 Setting up MutationObserver');
  
  const observer = new MutationObserver((mutations) => {
    let shouldModify = false;
    
    // Check if any relevant mutations occurred
    mutations.forEach(mutation => {
      // If nodes were added
      if (mutation.addedNodes.length > 0) {
        shouldModify = true;
      }
      
      // If attributes changed on a button or potential button container
      if (mutation.type === 'attributes' && 
          (mutation.target.tagName === 'BUTTON' || 
           mutation.target.querySelector('button'))) {
        shouldModify = true;
      }
    });
    
    if (shouldModify) {
      modifyButtonText();
    }
  });
  
  // Start observing with configuration
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'style', 'disabled']
  });
  
  return observer;
}

// Also use setInterval as a fallback to ensure modifications are applied
function setupInterval() {
  console.log('⏱️ Setting up interval for button text modification');
  
  // Run every 2 seconds
  const intervalId = setInterval(modifyButtonText, 2000);
  return intervalId;
}

// Initialize when DOM is ready
function initialize() {
  console.log('🚀 Initializing button text modifier');
  
  // Run immediately
  modifyButtonText();
  
  // Set up observers
  const observer = setupMutationObserver();
  const intervalId = setupInterval();
  
  // Return cleanup function
  return function cleanup() {
    observer.disconnect();
    clearInterval(intervalId);
  };
}

// Run when DOM is fully loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}

// Add cache control headers for the script
// Note: This needs to be handled server-side in your wsgi.py file
// The following is already implemented in your wsgi.py:
// response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'