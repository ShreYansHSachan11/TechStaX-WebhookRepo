// GitHub Webhook System - Frontend JavaScript
// Polls GET /events endpoint every 15 seconds and updates the UI

class WebhookEventUI {
    constructor() {
        this.pollingInterval = 15000; // 15 seconds
        this.pollingTimer = null;
        this.isPolling = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        
        // DOM elements
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.statusMessage = document.getElementById('status-message');
        this.eventsList = document.getElementById('events-list');
        this.eventsContainer = document.getElementById('events-container');
        
        // Initialize the UI
        this.init();
    }
    
    init() {
        console.log('GitHub Webhook System UI initialized');
        this.updateConnectionStatus('connecting', 'Connecting...');
        
        // Start polling immediately
        this.startPolling();
        
        // Handle page visibility changes to pause/resume polling
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pausePolling();
            } else {
                this.resumePolling();
            }
        });
    }
    
    startPolling() {
        if (this.isPolling) return;
        
        this.isPolling = true;
        console.log('Starting event polling...');
        
        // Fetch events immediately
        this.fetchEvents();
        
        // Set up recurring polling
        this.pollingTimer = setInterval(() => {
            this.fetchEvents();
        }, this.pollingInterval);
    }
    
    pausePolling() {
        if (!this.isPolling) return;
        
        console.log('Pausing event polling...');
        this.isPolling = false;
        
        if (this.pollingTimer) {
            clearInterval(this.pollingTimer);
            this.pollingTimer = null;
        }
    }
    
    resumePolling() {
        if (this.isPolling) return;
        
        console.log('Resuming event polling...');
        this.startPolling();
    }
    
    async fetchEvents() {
        try {
            console.log('Fetching events from API...');
            
            const response = await fetch('/events', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.handleSuccessfulResponse(data);
                this.retryCount = 0; // Reset retry count on success
            } else {
                throw new Error(data.message || 'API returned error status');
            }
            
        } catch (error) {
            console.error('Error fetching events:', error);
            this.handleFetchError(error);
        }
    }
    
    handleSuccessfulResponse(data) {
        console.log(`Successfully fetched ${data.count} events`);
        
        // Update connection status
        this.updateConnectionStatus('connected', `Connected • ${data.count} events`);
        
        // Hide status message
        this.statusMessage.style.display = 'none';
        
        // Update events display
        this.updateEventsDisplay(data.events);
    }
    
    handleFetchError(error) {
        console.error('Fetch error:', error.message);
        
        this.retryCount++;
        
        if (this.retryCount <= this.maxRetries) {
            // Show temporary error status
            this.updateConnectionStatus('error', `Connection error (retry ${this.retryCount}/${this.maxRetries})`);
            
            // Implement exponential backoff for retries
            const backoffDelay = Math.min(1000 * Math.pow(2, this.retryCount - 1), 10000);
            setTimeout(() => {
                if (this.isPolling) {
                    this.fetchEvents();
                }
            }, backoffDelay);
        } else {
            // Max retries reached
            this.updateConnectionStatus('error', 'Unable to load events');
            this.showErrorMessage('Unable to connect to the server. Please check your connection and refresh the page.');
        }
    }
    
    updateConnectionStatus(status, text) {
        // Update status indicator
        this.statusIndicator.className = `status-indicator ${status}`;
        
        // Update status text
        this.statusText.textContent = text;
    }
    
    showErrorMessage(message) {
        // Show error in the events container
        this.statusMessage.style.display = 'block';
        this.statusMessage.innerHTML = `
            <div class="error-message">
                ${message}
            </div>
        `;
        
        // Hide events list
        this.eventsList.style.display = 'none';
    }
    
    updateEventsDisplay(events) {
        if (!events || events.length === 0) {
            this.showNoEventsMessage();
            return;
        }
        
        // Show events list
        this.eventsList.style.display = 'block';
        
        // Clear existing events
        this.eventsList.innerHTML = '';
        
        // Add each event to the display
        events.forEach(event => {
            const eventElement = this.createEventElement(event);
            this.eventsList.appendChild(eventElement);
        });
        
        console.log(`Updated display with ${events.length} events`);
    }
    
    showNoEventsMessage() {
        this.eventsList.style.display = 'block';
        this.eventsList.innerHTML = `
            <div class="no-events">
                No webhook events received yet. Push to your repository or create a pull request to see events here.
            </div>
        `;
    }
    
    createEventElement(event) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'event-item';
        
        // Format the event text (will be implemented in subtask 6.3)
        const eventText = this.formatEventText(event);
        
        eventDiv.innerHTML = eventText;
        
        return eventDiv;
    }
    
    // Event formatting functions as per requirements 6.2, 6.3, 6.4, 6.5
    formatEventText(event) {
        const formattedTimestamp = this.formatTimestamp(event.timestamp);
        
        switch (event.action) {
            case 'PUSH':
                // Format: "{author} pushed to {to_branch} on {timestamp}"
                return `${event.author} pushed to ${event.to_branch} on ${formattedTimestamp}`;
                
            case 'PULL_REQUEST':
                // Format: "{author} submitted a pull request from {from_branch} to {to_branch} on {timestamp}"
                return `${event.author} submitted a pull request from ${event.from_branch} to ${event.to_branch} on ${formattedTimestamp}`;
                
            case 'MERGE':
                // Format: "{author} merged branch {from_branch} to {to_branch} on {timestamp}"
                return `${event.author} merged branch ${event.from_branch} to ${event.to_branch} on ${formattedTimestamp}`;
                
            default:
                // Fallback for unknown event types
                return `${event.author} performed ${event.action} on ${formattedTimestamp}`;
        }
    }
    
    formatTimestamp(timestamp) {
        try {
            // Parse ISO 8601 timestamp and format for display
            // The timestamp from API is in UTC (ends with Z)
            const date = new Date(timestamp);
            
            // Check if date is valid
            if (isNaN(date.getTime())) {
                return timestamp; // Return original if parsing fails
            }
            
            // Format as readable date and time in local timezone
            const options = {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                timeZoneName: 'short'
            };
            
            return date.toLocaleString('en-US', options);
        } catch (error) {
            console.error('Error formatting timestamp:', error);
            return timestamp; // Return original timestamp if formatting fails
        }
    }
}

// Initialize the UI when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.webhookUI = new WebhookEventUI();
});