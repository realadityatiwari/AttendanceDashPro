import { APP_VERSION } from './utils.js';
import { triggerCloudSync } from './storage.js';

let deferredPrompt;

export function initPWA() {
  // Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(`/service-worker.js?v=${APP_VERSION}`)
        .then(registration => {
          console.log('[PWA] ServiceWorker registration successful with scope:', registration.scope);
        })
        .catch(err => {
          console.error('[PWA] ServiceWorker registration failed:', err);
        });
    });
  }

  // Handle Offline/Online Status
  const offlineBanner = document.getElementById('offlineBanner');
  
  const updateOnlineStatus = () => {
    if (navigator.onLine) {
      if (offlineBanner) offlineBanner.style.display = 'none';
      triggerCloudSync();
    } else {
      if (offlineBanner) offlineBanner.style.display = 'block';
    }
  };

  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  
  // Initial check
  updateOnlineStatus();

  // Handle Install Prompt
  const installBtn = document.getElementById('profileInstallAppBtn');
  
  // Check if already installed
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (isStandalone && installBtn) {
    installBtn.style.display = 'none';
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    // Stash the event so it can be triggered later.
    deferredPrompt = e;
    
    // Show the install button
    if (installBtn && !isStandalone) {
      installBtn.style.display = 'flex';
    }
  });

  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      
      // Show the install prompt
      deferredPrompt.prompt();
      
      // Wait for the user to respond to the prompt
      const { outcome } = await deferredPrompt.userChoice;
      console.log(`[PWA] User response to the install prompt: ${outcome}`);
      
      // We've used the prompt, and can't use it again, throw it away
      deferredPrompt = null;
      
      // Hide the button if they accepted
      if (outcome === 'accepted') {
        installBtn.style.display = 'none';
      }
    });
  }

  window.addEventListener('appinstalled', () => {
    // Hide the app-provided install promotion
    if (installBtn) installBtn.style.display = 'none';
    
    // Clear the deferredPrompt so it can be garbage collected
    deferredPrompt = null;
    
    console.log('[PWA] PWA was installed');
  });
}
