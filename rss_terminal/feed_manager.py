"""
Feed management for RSS Terminal application.
"""
import time
import threading
import feedparser
from rss_terminal.utils import parse_date, get_formatted_time

class FeedManager:
    """Manages RSS feeds, fetches articles and maintains article lists"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.articles = []  # All articles
        self.filtered_articles = []  # Articles filtered by current selection
        self.current_filter = "ALL"  # Default filter showing all feeds
        self.last_check_time = None
        self.running = True
        self.fetch_thread = None
        self.fetch_callback = None
    
    def start_fetching(self, callback=None):
        """Start the background thread that fetches feeds periodically"""
        self.fetch_callback = callback
        self.running = True
        self.fetch_thread = threading.Thread(target=self.fetch_feeds_periodically)
        self.fetch_thread.daemon = True
        self.fetch_thread.start()
    
    def stop_fetching(self):
        """Stop the background thread"""
        self.running = False
        if self.fetch_thread:
            self.fetch_thread.join(timeout=1)
    
    def fetch_feeds_periodically(self):
        """Periodically fetch all feeds based on refresh interval"""
        while self.running:
            time.sleep(self.config.refresh_interval)
            self.fetch_all_feeds()
    
    def initial_fetch(self):
        """Perform first fetch of feeds in background"""
        threading.Thread(target=self.fetch_all_feeds).start()
    
    def fetch_all_feeds(self):
        """Fetch all configured RSS feeds and process articles"""
        self.last_check_time = time.time()
        
        new_articles = []
        seen_headlines = set()  # Track duplicate headlines
        
        for i, feed in enumerate(self.config.feeds):
            try:
                parsed_feed = feedparser.parse(feed['url'])
                feed_title = feed['name']  # Use the standardized feed name
                
                # Initialize last_seen_guids for this feed if it doesn't exist
                if feed['name'] not in self.config.last_seen_guids:
                    self.config.last_seen_guids[feed['name']] = []
                
                for entry in parsed_feed.entries:
                    # Parse the publication date
                    pub_date = parse_date(entry)
                    
                    # Get headline
                    title = entry.title if hasattr(entry, 'title') else "No title"
                    
                    # Check for duplicate headlines
                    if title in seen_headlines:
                        # Skip this duplicate headline but still mark it as seen if it's new
                        if hasattr(entry, 'id') and not self.config.is_guid_seen(feed['name'], entry.id):
                            self.config.update_last_seen_guid(feed['name'], entry.id)
                        continue
                        
                    # Add this headline to seen set
                    seen_headlines.add(title)
                    
                    # Determine if this is a new article (not seen before)
                    is_new = hasattr(entry, 'id') and not self.config.is_guid_seen(feed['name'], entry.id)
                    
                    # Add to articles list
                    new_articles.append({
                        'title': title,
                        'pub_date': pub_date,
                        'pub_date_str': get_formatted_time(pub_date, self.config.timezone),
                        'link': entry.link if hasattr(entry, 'link') else "",
                        'source': feed_title,
                        'is_new': is_new,  # Mark as new for highlighting if it's new
                        'description': entry.description if hasattr(entry, 'description') else None
                    })
                    
                    # Mark as seen if it's new
                    if is_new and hasattr(entry, 'id'):
                        self.config.update_last_seen_guid(feed['name'], entry.id)
            
            except Exception as e:
                if self.fetch_callback:
                    self.fetch_callback(f"Error fetching {feed['name']}: {str(e)}", error=True)
        
        # Check for duplicate headlines in existing articles
        if new_articles and self.articles:
            existing_headlines = {article['title'] for article in self.articles}
            new_articles = [article for article in new_articles if article['title'] not in existing_headlines]
        
        # If we have new articles, add them to our list
        if new_articles:
            # Sort new articles by publication date (newest first)
            new_articles.sort(key=lambda x: x['pub_date'], reverse=True)
            
            # Add to the beginning of our master list (newest first approach)
            self.articles = new_articles + self.articles
            self.config.save_last_seen()
            
        # Clean up old articles if needed
        self.cleanup_old_articles()
        
        # Apply the current filter
        self.apply_filter(self.current_filter)
        
        # Notify about completion
        if self.fetch_callback:
            self.fetch_callback(new_articles)
        
        return new_articles
    
    def cleanup_old_articles(self):
        """Remove old articles to prevent memory issues during long-term use"""
        current_time = time.time()
        orig_count = len(self.articles)
        
        # Time-based cleanup - keep articles less than 2 days old
        max_age_seconds = 2 * 24 * 60 * 60  # 2 days in seconds
        self.articles = [article for article in self.articles 
                        if (current_time - article['pub_date']) < max_age_seconds]
        
        # Maximum count limit - keep at most 1000 articles
        max_articles = 1000
        if len(self.articles) > max_articles:
            # Keep only the newest max_articles (since they're already sorted newest first)
            self.articles = self.articles[:max_articles]
        
        # Return true if any articles were removed
        return len(self.articles) < orig_count
    
    def apply_filter(self, feed_filter):
        """Filter articles based on the selected feed"""
        self.current_filter = feed_filter
        
        if feed_filter == "ALL":
            self.filtered_articles = self.articles.copy()
        else:
            self.filtered_articles = [a for a in self.articles if a['source'] == feed_filter]
        
        return self.filtered_articles
    
    def reset_new_article_flags(self):
        """Reset the is_new flag on all articles"""
        for article in self.articles:
            if article.get('is_new', False):
                article['is_new'] = False