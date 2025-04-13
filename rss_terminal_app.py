import tkinter as tk
import threading
import time
import configparser
import os
import feedparser
import datetime
import random
import json
import webbrowser
from tkinter import font, scrolledtext
from datetime import datetime as dt
import pytz
from dateutil import parser

class RSSTerminalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RSS Terminal")
        self.root.configure(bg='black')
        
        # Set window size and position
        window_width = 1000
        window_height = 700
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        # Terminal fonts - using Bloomberg font if available, otherwise fallbacks
        try:
            self.terminal_font = font.Font(family="Bloomberg", size=9, weight="normal")
            self.header_font = font.Font(family="Bloomberg", size=9, weight="bold")
        except:
            # Fallback to other monospace fonts
            for font_family in ["Consolas", "Lucida Console", "Courier New", "Courier"]:
                try:
                    self.terminal_font = font.Font(family=font_family, size=9, weight="normal")
                    self.header_font = font.Font(family=font_family, size=9, weight="bold")
                    break
                except:
                    continue
        
        # Configuration
        self.config_file = "rss_config.ini"
        self.feeds = []
        self.refresh_interval = 60  # default to 60 seconds
        self.last_seen_guids = {}
        self.articles = []  # Will store all articles
        self.timezone = "America/Los_Angeles"  # Default timezone (GMT-7/8)
        self.last_check_time = None
        self.current_filter = "ALL"  # Default to show all feeds
        self.load_config()
        
        # Bloomberg-like colors
        self.colors = {
            'bg': 'black',
            'header_bg': '#0f3562',  # Dark blue
            'text': 'white',
            'highlight': '#FF8C00',  # Orange
            'yellow': '#FFD700',
            'green': '#00FF00',
            'red': '#FF4500',
            'blue': '#1E90FF',
            'source': '#FF8C00',  # Orange
            'time': '#808080'  # Gray
        }
        
        # Create UI
        self.create_ui()
        
        # Start RSS fetching thread
        self.running = True
        self.fetch_thread = threading.Thread(target=self.fetch_feeds_periodically)
        self.fetch_thread.daemon = True
        self.fetch_thread.start()
        
        # Start countdown timer
        self.update_countdown()

    def create_ui(self):
        # Filter menu bar
        filter_frame = tk.Frame(self.root, bg=self.colors['bg'], height=25)
        filter_frame.pack(fill=tk.X, padx=0, pady=0)
        
        # Add "ALL" filter option
        all_filter = tk.Label(filter_frame, text="ALL", 
                             font=self.header_font, bg=self.colors['bg'],
                             fg=self.colors['highlight'] if self.current_filter == "ALL" else self.colors['text'],
                             padx=10, pady=3)
        all_filter.pack(side=tk.LEFT, padx=2)
        all_filter.bind("<Button-1>", lambda e: self.set_filter("ALL"))
        
        # Add separator
        separator = tk.Label(filter_frame, text="|", font=self.header_font, 
                            bg=self.colors['bg'], fg=self.colors['text'])
        separator.pack(side=tk.LEFT)
        
        # Add filter for each feed source
        for feed in self.feeds:
            feed_filter = tk.Label(filter_frame, text=feed['name'], 
                                  font=self.header_font, bg=self.colors['bg'],
                                  fg=self.colors['highlight'] if self.current_filter == feed['name'] else self.colors['text'],
                                  padx=10, pady=3)
            feed_filter.pack(side=tk.LEFT, padx=2)
            feed_filter.bind("<Button-1>", lambda e, name=feed['name']: self.set_filter(name))
        
        # Right side information
        time_display = tk.Label(filter_frame, text=self.get_formatted_time(), 
                              font=self.header_font, bg=self.colors['bg'], fg=self.colors['yellow'])
        time_display.pack(side=tk.RIGHT, padx=10)
        
        # Update time every second
        def update_time():
            time_display.config(text=self.get_formatted_time())
            self.root.after(1000, update_time)
        update_time()
        
        # Main content area with scrolling - Bloomberg terminal style
        content_frame = tk.Frame(self.root, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        self.content_text = scrolledtext.ScrolledText(content_frame, bg=self.colors['bg'], fg=self.colors['text'],
                                                    font=self.terminal_font, wrap=tk.NONE,
                                                    insertbackground=self.colors['text'],
                                                    selectbackground='#333333',
                                                    selectforeground=self.colors['text'],
                                                    cursor="hand2")  # Change cursor to hand when hovering
        self.content_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.content_text.config(state=tk.DISABLED)  # Make read-only
        
        # Configure tags for different text styles
        self.content_text.tag_configure("headline", foreground=self.colors['highlight'])
        self.content_text.tag_configure("new_headline", foreground="#FFFFFF", background="#004400")  # Highlight for new articles
        self.content_text.tag_configure("number", foreground=self.colors['yellow'])
        self.content_text.tag_configure("source", foreground=self.colors['source'])
        self.content_text.tag_configure("time", foreground=self.colors['time'])
        
        # Bind click event to content text
        self.content_text.bind("<Button-1>", self.on_text_click)
        
        # Status bar at bottom
        self.status_frame = tk.Frame(self.root, bg='#333333', height=22)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        
        self.status_label = tk.Label(self.status_frame, 
                                     text=f"Monitoring {len(self.feeds)} feeds | Refresh: {self.refresh_interval}s", 
                                     font=self.terminal_font, bg='#333333', fg='#CCCCCC', anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Add startup sequence
        self.show_startup_sequence()
    
    def set_filter(self, feed_name):
        """Set the current feed filter and refresh display"""
        self.current_filter = feed_name
        self.display_articles()
        
        # Update the filter buttons
        for widget in self.root.winfo_children()[0].winfo_children():
            if isinstance(widget, tk.Label) and widget.cget("text") not in ["|", self.get_formatted_time()]:
                if widget.cget("text") == feed_name:
                    widget.config(fg=self.colors['highlight'])
                else:
                    widget.config(fg=self.colors['text'])
    
    def show_startup_sequence(self):
        """Show a Bloomberg-like startup sequence"""
        self.update_text(f"{'=' * 80}\n", text_style="time")
        self.update_text("  RSS TERMINAL VIEWER\n", text_style="headline")
        self.update_text(f"  Version 1.0 | {dt.now().strftime('%Y-%m-%d')}\n", text_style="time")
        self.update_text(f"{'=' * 80}\n\n", text_style="time")
        
        # System initialization messages
        messages = [
            "Initializing system...",
            "Configuring feeds...",
            f"Monitoring {len(self.feeds)} news sources...",
            "Loading previous session data...",
            "Ready for operation",
            ""
        ]
        
        for msg in messages:
            self.update_text(f"  {msg}\n", text_style="source", delay_chars=True)
            self.root.update()
            time.sleep(0.3)
        
        # Final instructions
        self.update_text("Click on any headline to open the full article in your browser.\n\n", 
                        text_style="headline")
        
        # Perform first fetch after a short delay
        self.root.after(1000, self.initial_fetch)

    def get_formatted_time(self, timestamp=None):
        """Get time formatted for display in the specified timezone"""
        tz = pytz.timezone(self.timezone)
        if timestamp:
            # Convert timestamp to datetime and localize
            dt_obj = dt.fromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
            local_time = dt_obj.astimezone(tz)
        else:
            # Current time
            local_time = dt.now(tz)
        
        return local_time.strftime("%H:%M")
    
    def load_config(self):
        # Create default config if not exists
        if not os.path.exists(self.config_file):
            self.create_default_config()
            
        config = configparser.ConfigParser()
        config.read(self.config_file)
        
        if 'Settings' in config:
            self.refresh_interval = config.getint('Settings', 'refresh_interval', fallback=60)
            self.timezone = config.get('Settings', 'timezone', fallback="America/Los_Angeles")
        
        if 'Feeds' in config:
            self.feeds = []
            for key, url in config['Feeds'].items():
                self.feeds.append({'name': key.upper(), 'url': url})
    
    def create_default_config(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'refresh_interval': '300',
            'timezone': 'America/Los_Angeles'
        }
        config['Feeds'] = {
            'BBGMKT': 'https://www.bloomberg.com/feed/markets/sitemap_index.xml',
            'RTRSFI': 'https://www.reutersagency.com/feed/',
            'BBCNWS': 'http://feeds.bbci.co.uk/news/rss.xml',
            'CNNTOP': 'http://rss.cnn.com/rss/edition.rss'
        }
        
        with open(self.config_file, 'w') as f:
            config.write(f)
    
    def save_last_seen(self):
        with open("last_seen.json", "w") as f:
            json.dump(self.last_seen_guids, f)
    
    def load_last_seen(self):
        try:
            if os.path.exists("last_seen.json"):
                with open("last_seen.json", "r") as f:
                    self.last_seen_guids = json.load(f)
        except:
            self.last_seen_guids = {}
    
    def update_text(self, text, delay_chars=False, flash=False, text_style=None):
        self.content_text.config(state=tk.NORMAL)
        
        if flash:
            # Insert with flash effect
            self.content_text.insert(tk.END, text, 'flash')
            self.content_text.tag_configure('flash', foreground='#FFFFFF', background='#444444')
            self.content_text.see(tk.END)
            
            # Schedule removal of flash effect
            def remove_flash():
                self.content_text.tag_configure('flash', foreground=self.colors['highlight'], background=self.colors['bg'])
            self.root.after(500, remove_flash)
        elif text_style:
            # Insert with specific style
            self.content_text.insert(tk.END, text, text_style)
            self.content_text.see(tk.END)
        elif delay_chars:
            # Insert with typing animation
            for char in text:
                self.content_text.insert(tk.END, char)
                self.content_text.see(tk.END)
                self.content_text.update()
                time.sleep(0.01)
        else:
            # Normal insert
            self.content_text.insert(tk.END, text)
            self.content_text.see(tk.END)
        
        self.content_text.config(state=tk.DISABLED)
    
    def update_status(self, text):
        self.status_label.config(text=text)
    
    def update_countdown(self):
        """Update the countdown timer in the status bar"""
        if self.last_check_time:
            elapsed = time.time() - self.last_check_time
            remaining = max(0, self.refresh_interval - elapsed)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            
            # Format the countdown text
            countdown_text = f"Next refresh in {mins:02d}:{secs:02d}"
            
            # Update the status text
            current_status = self.status_label.cget("text")
            if "Next refresh in" in current_status:
                # Replace the countdown part
                new_status = current_status.split(" | ")[0] + f" | {countdown_text}"
            else:
                # Add the countdown
                new_status = current_status + f" | {countdown_text}"
            
            self.status_label.config(text=new_status)
        
        # Schedule the next update
        self.root.after(1000, self.update_countdown)
    
    def on_text_click(self, event):
        """Handle click on text widget to open article"""
        # Get the index of the click
        index = self.content_text.index(f"@{event.x},{event.y}")
        
        # Get the line number (convert index to integer)
        line_num = int(index.split('.')[0])
        
        # Get all the text of that line
        line_start = f"{line_num}.0"
        line_end = f"{line_num}.end"
        line = self.content_text.get(line_start, line_end)
        
        # Extract the article number from the beginning of the line (format: "1) ")
        try:
            num_end = line.find(')')
            if num_end > 0:
                article_num = int(line[:num_end].strip())
                # Articles are 1-indexed in display, so subtract 1 for array index
                if 0 < article_num <= len(self.filtered_articles):
                    article = self.filtered_articles[article_num - 1]
                    self.update_status(f"Opening article: {article['title']}")
                    webbrowser.open(article['link'])
        except:
            pass
    
    def fetch_feeds_periodically(self):
        while self.running:
            time.sleep(self.refresh_interval)
            self.fetch_all_feeds()
    
    def initial_fetch(self):
        # Load last seen articles
        self.load_last_seen()
        
        # Perform first fetch in the background
        threading.Thread(target=self.fetch_all_feeds).start()
    
    def parse_date(self, entry):
        """Try to parse date from entry in various formats"""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return time.mktime(entry.published_parsed)
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            return time.mktime(entry.updated_parsed)
        elif hasattr(entry, 'published') and entry.published:
            try:
                dt_obj = parser.parse(entry.published)
                return dt_obj.timestamp()
            except:
                pass
        elif hasattr(entry, 'updated') and entry.updated:
            try:
                dt_obj = parser.parse(entry.updated)
                return dt_obj.timestamp()
            except:
                pass
        
        # If all else fails, use current time
        return time.time()
    
    def truncate_headline(self, headline, max_length=90):
        """Truncate headline if it's too long"""
        if len(headline) > max_length:
            return headline[:max_length] + "..."
        return headline
    
    def display_articles(self):
        """Display articles based on current filter"""
        # Filter articles based on current selection
        if self.current_filter == "ALL":
            self.filtered_articles = self.articles.copy()
        else:
            self.filtered_articles = [a for a in self.articles if a['source'] == self.current_filter]
        
        # Clear display
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)
        
        # Display filter information
        if self.current_filter == "ALL":
            filter_text = "All Feeds"
        else:
            filter_text = f"{self.current_filter} Feed"
        
        self.update_text(f"{filter_text} - {len(self.filtered_articles)} Headlines\n", text_style="headline")
        
        # Display each article as a Bloomberg-like news item
        for idx, article in enumerate(self.filtered_articles):
            # Format row number
            num_text = f"{idx+1}) "
            self.update_text(num_text, text_style="number")
            
            # Format headline (title) with truncation
            headline_text = self.truncate_headline(article['title'])
            
            # Check if this is a new article and should be highlighted
            if article.get('is_new', False):
                self.update_text(headline_text, text_style="new_headline")
            else:
                self.update_text(headline_text, text_style="headline")
            
            # Calculate space needed for right alignment
            # Get width of the window in characters
            window_width = self.content_text.winfo_width() // 8  # Approximate char width
            source_time_width = len(article['source']) + len(article['pub_date_str']) + 2  # +2 for spacing
            
            # Ensure we have enough space for source and time
            min_space = 5
            
            # Calculate spaces needed for right alignment
            spaces_needed = window_width - len(num_text) - len(headline_text) - source_time_width - min_space
            spaces_needed = max(spaces_needed, min_space)
            spaces = " " * spaces_needed
            
            self.update_text(spaces)
            
            # Add source code and time
            self.update_text(f"{article['source']} ", text_style="source")
            self.update_text(f"{article['pub_date_str']}\n", text_style="time")
    
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
            # Sort by date (newest first) and keep only the newest max_articles
            self.articles.sort(key=lambda x: x['pub_date'], reverse=True)
            self.articles = self.articles[:max_articles]
            # Re-sort to put newest at the bottom
            self.articles.sort(key=lambda x: x['pub_date'])
        
        # Return true if any articles were removed
        return len(self.articles) < orig_count
    
    def fetch_all_feeds(self):
        self.update_status(f"Starting update...")
        self.last_check_time = time.time()
        
        new_articles = []
        seen_headlines = set()  # Track duplicate headlines
        
        for i, feed in enumerate(self.feeds):
            # Update status with progress
            self.update_status(f"Updating {i+1} of {len(self.feeds)}: {feed['name']}")
            self.root.update()  # Force UI update
            
            try:
                parsed_feed = feedparser.parse(feed['url'])
                feed_title = feed['name']  # Use the standardized feed name
                
                # Get new items (not seen before)
                if feed['name'] not in self.last_seen_guids:
                    self.last_seen_guids[feed['name']] = []
                
                for entry in parsed_feed.entries:
                    if hasattr(entry, 'id') and entry.id not in self.last_seen_guids[feed['name']]:
                        # Parse the publication date
                        pub_date = self.parse_date(entry)
                        
                        # Get headline
                        title = entry.title if hasattr(entry, 'title') else "No title"
                        
                        # Check for duplicate headlines
                        if title in seen_headlines:
                            # Skip this duplicate headline but still mark it as seen
                            self.last_seen_guids[feed['name']].append(entry.id)
                            continue
                            
                        # Add this headline to seen set
                        seen_headlines.add(title)
                        
                        # Add to new articles
                        new_articles.append({
                            'title': title,
                            'pub_date': pub_date,
                            'pub_date_str': self.get_formatted_time(pub_date),
                            'link': entry.link if hasattr(entry, 'link') else "",
                            'source': feed_title
                        })
                        
                        # Mark as seen
                        self.last_seen_guids[feed['name']].append(entry.id)
            
            except Exception as e:
                error_msg = f"\n[ERROR] Failed to fetch feed '{feed['name']}': {str(e)}\n"
                self.update_text(error_msg, text_style="time")
        
        # Check for duplicate headlines in existing articles
        if new_articles and self.articles:
            existing_headlines = {article['title'] for article in self.articles}
            new_articles = [article for article in new_articles if article['title'] not in existing_headlines]
        
        display_needed = False
        
        # If we have new articles, add them to our list
        if new_articles:
            # Sort all articles by publication date
            new_articles.sort(key=lambda x: x['pub_date'])
            
            # Add to our master list and save the updated last seen GUIDs
            self.articles.extend(new_articles)
            self.save_last_seen()
            display_needed = True
        
        # Clean up old articles - only if we have articles to clean
        if len(self.articles) > 0:
            # Only set display_needed if something was actually removed
            if self.cleanup_old_articles():
                display_needed = True
        
        # Only update the display if we've made changes to the list
        if display_needed:
            self.display_articles()
        
        # Always update the status
        if new_articles:
            self.update_status(f"Updated with {len(new_articles)} new articles. Total: {len(self.articles)} | Last check: {dt.now().strftime('%H:%M:%S')}")
        else:
            self.update_status(f"No new updates | Last check: {dt.now().strftime('%H:%M:%S')}")
    
    def on_closing(self):
        self.running = False
        self.root.destroy()

def main():
    # Try to import required modules, offer helpful error if missing
    missing_modules = []
    
    try:
        import pytz
    except ImportError:
        missing_modules.append("pytz")
    
    try:
        from dateutil import parser
    except ImportError:
        missing_modules.append("python-dateutil")
    
    if missing_modules:
        print(f"ERROR: Missing required modules: {', '.join(missing_modules)}")
        print(f"Please install them using: pip install {' '.join(missing_modules)}")
        return
    
    root = tk.Tk()
    app = RSSTerminalApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()