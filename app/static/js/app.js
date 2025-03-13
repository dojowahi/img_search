/**
 * app.js - Enhanced functionality for Image Search Frontend
 */

// Wait until DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initializeTabSwitcher();
    initializeImagePreviews();
    initializeSearchHistoryTracking();
    setupImageCardInteractions();
    setupCopyButtons();
});

/**
 * Handle tab switching with smooth transitions
 */
function initializeTabSwitcher() {
    // Set default tab on page load
    if (location.hash) {
        // If URL has a hash, try to switch to that tab
        const tabName = location.hash.substring(1);
        switchTab(tabName);
    } else {
        // Default to text search
        switchTab('text-search');
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', function() {
        if (location.hash) {
            const tabName = location.hash.substring(1);
            switchTab(tabName);
        }
    });
}

/**
 * Switch between different tabs
 */
function switchTab(tabName) {
    // Update URL hash without triggering page jump
    history.replaceState(null, null, '#' + tabName);
    
    // Hide all sections
    const sections = document.querySelectorAll('[id$="-section"]');
    sections.forEach(section => section.classList.add('hidden'));
    
    // Reset all tab buttons
    const tabs = document.querySelectorAll('[id^="tab-"]');
    tabs.forEach(tab => {
        tab.classList.remove('text-indigo-600', 'border-b-2', 'border-indigo-600', 'bg-white');
        tab.classList.add('text-gray-500', 'bg-gray-50');
    });
    
    // Show selected section and highlight tab
    const selectedSection = document.getElementById(tabName + '-section');
    const selectedTab = document.getElementById('tab-' + tabName);
    
    if (selectedSection && selectedTab) {
        selectedSection.classList.remove('hidden');
        selectedTab.classList.remove('text-gray-500', 'bg-gray-50');
        selectedTab.classList.add('text-indigo-600', 'border-b-2', 'border-indigo-600', 'bg-white');
        
        // Add subtle fade-in animation
        selectedSection.style.opacity = '0';
        selectedSection.style.transition = 'opacity 0.3s ease-in-out';
        setTimeout(() => {
            selectedSection.style.opacity = '1';
        }, 10);
    }
    
    // Clear results only if changing to a different input tab
    if (tabName === 'upload' || tabName === 'folder-upload' || tabName === 'text-search' || tabName === 'image-search') {
        document.getElementById('results-area').innerHTML = '';
    }
}

/**
 * Initialize image preview functionality for file inputs
 */
function initializeImagePreviews() {
    // Handle regular file uploads
    const fileInput = document.querySelector('input[name="files"]');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            previewImages(this.files, 'file-previews');
        });
    }
    
    // Handle image search file upload
    const searchFileInput = document.querySelector('input[name="file"]');
    if (searchFileInput) {
        searchFileInput.addEventListener('change', function() {
            previewImages([this.files[0]], 'search-file-preview');
        });
    }
    
    // Handle folder upload
    const folderInput = document.getElementById('folder-files');
    if (folderInput) {
        folderInput.addEventListener('change', function() {
            const numFiles = folderInput.files.length;
            const fileCount = document.getElementById('file-count');
            
            if (numFiles > 0) {
                // Get folder name from the first file's path
                const path = folderInput.files[0].webkitRelativePath;
                const folderName = path.split('/')[0];
                
                // Count image files only
                let imageCount = 0;
                for (let i = 0; i < numFiles; i++) {
                    if (folderInput.files[i].type.startsWith('image/')) {
                        imageCount++;
                    }
                }
                
                fileCount.textContent = `Selected folder: "${folderName}" with ${imageCount} images`;
                
                if (imageCount === 0) {
                    fileCount.innerHTML += '<br><span class="text-red-600">Warning: No image files found in this folder!</span>';
                } else if (imageCount > 50) {
                    fileCount.innerHTML += '<br><span class="text-amber-600">Note: Processing large folders may take some time.</span>';
                }
                
                // Preview first few images
                const imagesToPreview = [];
                let previewCount = 0;
                for (let i = 0; i < numFiles && previewCount < 4; i++) {
                    if (folderInput.files[i].type.startsWith('image/')) {
                        imagesToPreview.push(folderInput.files[i]);
                        previewCount++;
                    }
                }
                previewImages(imagesToPreview, 'folder-previews');
            } else {
                fileCount.textContent = 'No files selected';
            }
        });
    }
}

/**
 * Preview a list of image files
 */
function previewImages(files, containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        // Create container if it doesn't exist
        const parentElement = document.querySelector('.space-y-4');
        if (parentElement) {
            const newContainer = document.createElement('div');
            newContainer.id = containerId;
            newContainer.className = 'grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2';
            parentElement.appendChild(newContainer);
            container = newContainer;
        } else {
            return;
        }
    }
    
    // Clear previous previews
    container.innerHTML = '';
    
    // Create previews for each file (limited to first 8)
    const maxPreviews = 8;
    const filesToPreview = Array.from(files).slice(0, maxPreviews);
    
    filesToPreview.forEach(file => {
        if (!file.type.startsWith('image/')) return;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            const previewWrapper = document.createElement('div');
            previewWrapper.className = 'relative aspect-square border rounded overflow-hidden';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'w-full h-full object-cover';
            img.alt = file.name;
            
            previewWrapper.appendChild(img);
            container.appendChild(previewWrapper);
        };
        reader.readAsDataURL(file);
    });
    
    // Show "more" indicator if there are additional files
    if (files.length > maxPreviews) {
        const moreIndicator = document.createElement('div');
        moreIndicator.className = 'relative aspect-square border rounded bg-gray-100 flex items-center justify-center';
        moreIndicator.innerHTML = `<span class="text-gray-600 font-medium">+${files.length - maxPreviews} more</span>`;
        container.appendChild(moreIndicator);
    }
}

/**
 * Track and display search history
 */
function initializeSearchHistoryTracking() {
    // Track text searches
    const textSearchForm = document.querySelector('form[hx-get="/api/v1/search_by_text/"]');
    if (textSearchForm) {
        textSearchForm.addEventListener('submit', function() {
            const queryInput = this.querySelector('input[name="query"]');
            if (queryInput && queryInput.value) {
                addToSearchHistory('text', queryInput.value);
            }
        });
    }
    
    // Track image searches
    const imageSearchForm = document.querySelector('form[hx-post="/api/v1/search_by_image/"]');
    if (imageSearchForm) {
        imageSearchForm.addEventListener('submit', function() {
            const fileInput = this.querySelector('input[name="file"]');
            if (fileInput && fileInput.files[0]) {
                addToSearchHistory('image', fileInput.files[0].name);
            }
        });
    }
    
    // Initialize search history display
    updateSearchHistoryDisplay();
}

/**
 * Add a new search to history
 */
function addToSearchHistory(type, value) {
    // Get existing history from localStorage
    let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    
    // Add new search
    history.unshift({
        type: type,
        value: value,
        timestamp: new Date().toISOString()
    });
    
    // Keep only the 10 most recent searches
    history = history.slice(0, 10);
    
    // Save back to localStorage
    localStorage.setItem('searchHistory', JSON.stringify(history));
    
    // Update display
    updateSearchHistoryDisplay();
}

/**
 * Update search history display
 */
function updateSearchHistoryDisplay() {
    const container = document.getElementById('search-history');
    if (!container) return;
    
    // Get history
    const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    
    // Clear container
    container.innerHTML = '';
    
    // Create history items
    if (history.length > 0) {
        const historyList = document.createElement('div');
        historyList.className = 'mt-4 space-y-2';
        
        history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'flex items-center px-3 py-2 bg-gray-50 rounded hover:bg-gray-100 transition cursor-pointer text-sm';
            
            // Icon based on search type
            const icon = document.createElement('span');
            if (item.type === 'text') {
                icon.innerHTML = '<svg class="w-4 h-4 text-gray-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>';
            } else {
                icon.innerHTML = '<svg class="w-4 h-4 text-gray-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>';
            }
            
            // Add click handler to repeat search
            historyItem.addEventListener('click', function() {
                if (item.type === 'text') {
                    // Fill text search and submit
                    const input = document.querySelector('input[name="query"]');
                    if (input) {
                        input.value = item.value;
                        switchTab('text-search');
                        input.form.dispatchEvent(new Event('submit'));
                    }
                }
            });
            
            const text = document.createElement('span');
            text.textContent = item.value;
            text.className = 'truncate flex-1';
            
            const time = document.createElement('span');
            time.textContent = new Date(item.timestamp).toLocaleDateString();
            time.className = 'text-xs text-gray-500 ml-2';
            
            historyItem.appendChild(icon);
            historyItem.appendChild(text);
            historyItem.appendChild(time);
            historyList.appendChild(historyItem);
        });
        
        container.appendChild(historyList);
    } else {
        container.innerHTML = '<p class="text-sm text-gray-500 mt-2">No search history yet</p>';
    }
}

/**
 * Set up interactions for image cards in results
 */
function setupImageCardInteractions() {
    // This uses event delegation since the cards are added dynamically
    document.addEventListener('click', function(e) {
        // Find the card element (if any)
        const card = e.target.closest('.image-card');
        if (!card) return;
        
        // If clicked on the card itself (not a button or tag)
        if (e.target === card || e.target.tagName === 'IMG') {
            // Get image URL
            const img = card.querySelector('img');
            if (img && img.src) {
                // Open image in a new tab
                window.open(img.src, '_blank');
            }
        }
    });
}

/**
 * Setup copy-to-clipboard functionality for tags and IDs
 */
function setupCopyButtons() {
    document.addEventListener('click', function(e) {
        // Look for copy buttons
        if (e.target.matches('.copy-button, .copy-button *')) {
            const button = e.target.closest('.copy-button');
            const textToCopy = button.dataset.copy;
            
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(function() {
                    // Show a success indicator
                    const originalText = button.innerHTML;
                    button.innerHTML = '<svg class="h-4 w-4 text-green-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>';
                    
                    // Revert after 1 second
                    setTimeout(function() {
                        button.innerHTML = originalText;
                    }, 1000);
                });
            }
        }
    });
}

/**
 * Check if the database has content
 */
function checkDatabaseStatus() {
    // Make a request to check if database is empty
    fetch('/api/v1/status')
        .then(response => response.json())
        .then(data => {
            if (data.empty) {
                // Show empty database warning
                const warning = document.createElement('div');
                warning.className = 'bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4';
                warning.innerHTML = `
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm text-yellow-700">
                                The database appears to be empty. Please upload some images first.
                            </p>
                        </div>
                    </div>
                `;
                
                document.querySelector('.container').insertBefore(warning, document.querySelector('.mb-8'));
            }
        })
        .catch(error => console.error('Error checking database status:', error));
}