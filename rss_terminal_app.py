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
import html
import re
from tkinter import font, scrolledtext
from datetime import datetime as dt
import pytz
from dateutil import parser
import html2text

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
        self.filtered_articles = []  # Will store filtered articles
        self.selected_article_index = -1  # -1 means no selection
        self.has_selection = False  # Track if any article is currently selected
        self.timezone = "America/Los_Angeles"  # Default timezone (GMT-7/8)
        self.last_check_time = None
        self.current_filter = "ALL"  # Default to show all feeds
        
        # Jump to number feature
        self.goto_mode = False
        self.goto_number = ""
        
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
            'time': '#808080',  # Gray
            'selected': '#0066CC'  # Blue for selected item
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
                                                    selectforeground=self.colors['text'])
        self.content_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.content_text.config(state=tk.DISABLED)  # Make read-only
        
        # Configure tags for different text styles
        self.content_text.tag_configure("headline", foreground=self.colors['highlight'])
        self.content_text.tag_configure("new_headline", foreground="#FFFFFF", background="#004400")  # Highlight for new articles
        self.content_text.tag_configure("number", foreground=self.colors['yellow'])
        self.content_text.tag_configure("source", foreground=self.colors['source'])
        self.content_text.tag_configure("time", foreground=self.colors['time'])
        self.content_text.tag_configure("selected", foreground=self.colors['text'], background=self.colors['selected'])  # Selected item
        
        # Bind keyboard events for navigation
        self.root.bind("<Up>", self.select_previous_article)
        self.root.bind("<Down>", self.select_next_article)
        self.root.bind("<Return>", self.open_selected_article)
        self.root.bind("<space>", self.open_selected_article)
        self.root.bind("<Escape>", self.unselect_article)  # Add ESC to unselect
        
        # New keyboard shortcuts
        self.root.bind("g", self.start_goto_mode)                   # Go to article by number
        self.root.bind("d", self.show_article_description)          # Show description for selected article
        
        # Command for paging up/down with selection
        self.root.bind("<Command-Up>", self.page_up)                # Page up with Command+Up (Mac)
        self.root.bind("<Command-Down>", self.page_down)            # Page down with Command+Down (Mac)
        
        # Command+Shift for jumping to first/last (replacing Option/Alt bindings)
        self.root.bind("<Command-Shift-Up>", self.jump_to_first)    # Jump to first article
        self.root.bind("<Command-Shift-Down>", self.jump_to_last)   # Jump to last article
        
        # Bind number keys for goto mode
        for i in range(10):
            self.root.bind(str(i), self.handle_number_key)
        
        # Key bindings for feed switching
        self.root.bind("<Alt-a>", lambda e: self.set_filter("ALL"))
        self.root.bind("<F5>", lambda e: self.fetch_all_feeds())
        
        # Cycling through feeds with Tab and Shift+Tab
        self.root.bind("<Tab>", self.cycle_next_feed)
        self.root.bind("<Shift-Tab>", self.cycle_previous_feed)
        
        # Status bar at bottom
        self.status_frame = tk.Frame(self.root, bg='#333333', height=22)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        
        self.status_label = tk.Label(self.status_frame, 
                                     text=f"Monitoring {len(self.feeds)} feeds | Refresh: {self.refresh_interval}s", 
                                     font=self.terminal_font, bg='#333333', fg='#CCCCCC', anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Add keyboard shortcuts info
        shortcuts_label = tk.Label(self.status_frame,
                                  text="↑/↓: Navigate | Enter: Open | Tab: Cycle Feeds | F5: Refresh",
                                  font=self.terminal_font, bg='#333333', fg='#AAAAAA', anchor='e')
        shortcuts_label.pack(side=tk.RIGHT, padx=10)
        
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
        
        # Final instructions with keyboard navigation info
        self.update_text("KEYBOARD SHORTCUTS:\n", text_style="headline")
        self.update_text("  ↑/↓ : Navigate between headlines\n", text_style="source")
        self.update_text("  Enter/Space : Open selected article in browser\n", text_style="source")
        self.update_text("  ESC : Unselect current article\n", text_style="source")
        self.update_text("  Tab/Shift+Tab : Cycle between feeds\n", text_style="source")
        self.update_text("  F5 : Refresh all feeds\n", text_style="source")
        self.update_text("  g  : Go to article by number\n", text_style="source")
        self.update_text("  d  : Show description of selected article\n", text_style="source")
        self.update_text("  ⌘+↑/↓ : Page up/down in article list\n", text_style="source")
        self.update_text("  ⌘+Shift+↑/↓ : Jump to first/last article\n\n", text_style="source")
        
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
        
        # Don't automatically select any article by default - user must use arrow keys
        self.selected_article_index = -1
        
        # Clear display
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)
        
        # Display filter information
        if self.current_filter == "ALL":
            filter_text = "All Feeds"
        else:
            filter_text = f"{self.current_filter} Feed"
        
        self.update_text(f"{filter_text} - {len(self.filtered_articles)} Headlines\n", text_style="headline")
        
        # Track if any new articles are displayed
        self.new_article_tags = []  # Store tags for flashing effect
        displayed_new_articles = False
        
        # Display each article as a Bloomberg-like news item
        for idx, article in enumerate(self.filtered_articles):
            # Format row number
            num_text = f"{idx+1}) "
            self.update_text(num_text, text_style="number")
            
            # Format headline (title) with truncation
            headline_text = self.truncate_headline(article['title'])
            
            # Check if this is a new article and should be highlighted
            if article.get('is_new', False):
                # Insert with unique tag for this article to enable flashing
                tag_name = f"new_headline_{idx}"
                self.content_text.config(state=tk.NORMAL)
                position = self.content_text.index(tk.END)
                self.content_text.insert(tk.END, headline_text, tag_name)
                self.content_text.tag_configure(tag_name, foreground="#FFFFFF", background="#004400")
                self.new_article_tags.append(tag_name)
                displayed_new_articles = True
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
        
        # If we displayed any new articles, start flashing and schedule them to be "un-highlighted" after a delay
        if displayed_new_articles:
            # Start flashing effect for new articles
            self.flash_new_articles(0)
            # Schedule the reset of is_new flags after 30 seconds
            self.root.after(30000, self.reset_new_article_flags)
    
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
                
                # Initialize last_seen_guids for this feed if it doesn't exist
                if feed['name'] not in self.last_seen_guids:
                    self.last_seen_guids[feed['name']] = []
                
                for entry in parsed_feed.entries:
                    # Parse the publication date
                    pub_date = self.parse_date(entry)
                    
                    # Get headline
                    title = entry.title if hasattr(entry, 'title') else "No title"
                    
                    # Check for duplicate headlines
                    if title in seen_headlines:
                        # Skip this duplicate headline but still mark it as seen if it's new
                        if hasattr(entry, 'id') and entry.id not in self.last_seen_guids[feed['name']]:
                            self.last_seen_guids[feed['name']].append(entry.id)
                        continue
                        
                    # Add this headline to seen set
                    seen_headlines.add(title)
                    
                    # Determine if this is a new article (not seen before)
                    is_new = hasattr(entry, 'id') and entry.id not in self.last_seen_guids[feed['name']]
                    
                    # Add to articles list
                    new_articles.append({
                        'title': title,
                        'pub_date': pub_date,
                        'pub_date_str': self.get_formatted_time(pub_date),
                        'link': entry.link if hasattr(entry, 'link') else "",
                        'source': feed_title,
                        'is_new': is_new,  # Mark as new for highlighting if it's new
                        'description': entry.description if hasattr(entry, 'description') else None
                    })
                    
                    # Mark as seen if it's new
                    if is_new and hasattr(entry, 'id'):
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
    
    def reset_new_article_flags(self):
        """Reset the is_new flag on all articles and refresh the display"""
        # Reset the is_new flag on all articles
        for article in self.articles:
            if article.get('is_new', False):
                article['is_new'] = False
        
        # Refresh the display to show articles without highlighting
        self.display_articles()
    
    def flash_new_articles(self, step):
        """Create a flashing effect for new articles
        Alternates between different highlighting colors"""
        if not hasattr(self, 'new_article_tags') or not self.new_article_tags:
            return  # No new articles to flash
            
        # Colors for flashing effect (alternating between darker and lighter green)
        colors = [
            {"fg": "#FFFFFF", "bg": "#004400"},  # Dark green
            {"fg": "#FFFFFF", "bg": "#006600"},  # Medium green
            {"fg": "#FFFFFF", "bg": "#008800"},  # Light green
            {"fg": "#FFFFFF", "bg": "#006600"}   # Medium green (transitioning back to dark)
        ]
        
        # Get the current color based on step
        color = colors[step % len(colors)]
        
        # Apply the color to all new article tags
        for tag in self.new_article_tags:
            self.content_text.tag_configure(tag, foreground=color["fg"], background=color["bg"])
        
        # Schedule next flash with next color (every 400ms)
        self.root.after(400, lambda: self.flash_new_articles((step + 1) % len(colors)))
    
    def select_previous_article(self, event=None):
        """Select the previous article in the list"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Decrement the index, wrapping around if necessary
        if self.selected_article_index > 0:
            self.selected_article_index -= 1
        else:
            self.selected_article_index = len(self.filtered_articles) - 1
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling

    def select_next_article(self, event=None):
        """Select the next article in the list"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Increment the index, wrapping around if necessary
        if self.selected_article_index < len(self.filtered_articles) - 1:
            self.selected_article_index += 1
        else:
            self.selected_article_index = 0
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling

    def open_selected_article(self, event=None):
        """Open the currently selected article in a web browser"""
        if not self.filtered_articles or self.selected_article_index >= len(self.filtered_articles):
            return "break"  # No articles or invalid index
        
        article = self.filtered_articles[self.selected_article_index]
        self.update_status(f"Opening article: {article['title']}")
        webbrowser.open(article['link'])
        return "break"  # Prevent default handling

    def highlight_selected_article(self):
        """Highlight the currently selected article"""
        if not self.filtered_articles:
            return  # No articles to highlight
            
        # First, remove all selection highlights
        self.content_text.tag_remove("selected", "1.0", tk.END)
        
        # Add 2 for the header lines
        line_num = self.selected_article_index + 2
        
        # Apply selected style to the current line
        line_start = f"{line_num}.0"
        line_end = f"{line_num}.end"
        
        self.content_text.tag_add("selected", line_start, line_end)
        
        # Ensure the selected line is visible
        self.content_text.see(line_start)
        
        # Update status with selected article info
        article = self.filtered_articles[self.selected_article_index]
        self.update_status(f"Selected: {article['title']}")
    
    def cycle_next_feed(self, event=None):
        """Cycle to the next feed in the list"""
        feed_names = ["ALL"] + [feed["name"] for feed in self.feeds]
        current_index = feed_names.index(self.current_filter)
        next_index = (current_index + 1) % len(feed_names)
        self.set_filter(feed_names[next_index])
        return "break"  # Prevent default tab behavior

    def cycle_previous_feed(self, event=None):
        """Cycle to the previous feed in the list"""
        feed_names = ["ALL"] + [feed["name"] for feed in self.feeds]
        current_index = feed_names.index(self.current_filter)
        prev_index = (current_index - 1) % len(feed_names)
        self.set_filter(feed_names[prev_index])
        return "break"  # Prevent default tab behavior
    
    def unselect_article(self, event=None):
        """Unselect any selected article and return to default view"""
        # Reset the selection index
        self.selected_article_index = -1
        
        # Remove all selection highlights
        self.content_text.tag_remove("selected", "1.0", tk.END)
        
        # Reset the status bar to default message
        self.update_status(f"Monitoring {len(self.feeds)} feeds | Refresh: {self.refresh_interval}s")
        
        return "break"  # Prevent default handling
    
    def start_goto_mode(self, event=None):
        """Enter goto mode to jump to a specific article by number"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate to
            
        self.goto_mode = True
        self.goto_number = ""
        self.update_status("Go to article #: _")
        return "break"
        
    def handle_number_key(self, event=None):
        """Handle number key press - either in goto mode or normal mode"""
        if self.goto_mode:
            # In goto mode, add the number to the goto_number string
            self.goto_number += event.char
            self.update_status(f"Go to article #: {self.goto_number}_")
            
            # If Enter is pressed or Return key is pressed, jump to that article
            self.root.bind("<Return>", self.execute_goto)
            
            return "break"
        return None  # Let the event propagate if not in goto mode
        
    def execute_goto(self, event=None):
        """Execute the goto command with the entered number"""
        if not self.goto_mode or not self.goto_number.isdigit():
            self.goto_mode = False
            # Restore normal Enter behavior
            self.root.bind("<Return>", self.open_selected_article)
            return "break"
            
        article_num = int(self.goto_number)
        
        # Article numbers are 1-indexed in display, but 0-indexed in the list
        if 1 <= article_num <= len(self.filtered_articles):
            self.selected_article_index = article_num - 1
            self.highlight_selected_article()
            
        # Exit goto mode
        self.goto_mode = False
        self.goto_number = ""
        
        # Restore normal Enter binding
        self.root.bind("<Return>", self.open_selected_article)
        
        return "break"
        
    def show_article_description(self, event=None):
        """Show description for the selected article in Bloomberg terminal style"""
        if not self.filtered_articles or self.selected_article_index < 0:
            self.update_status("No article selected")
            return "break"
            
        article = self.filtered_articles[self.selected_article_index]
        
        # Create a popup window for description
        desc_window = tk.Toplevel(self.root)
        desc_window.title(f"{article['source']} - Article Detail")
        desc_window.configure(bg=self.colors['bg'])
        
        # Set window size and position relative to main window
        window_width = 700
        window_height = 500
        x = self.root.winfo_x() + (self.root.winfo_width() - window_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - window_height) // 2
        desc_window.geometry(f'{window_width}x{window_height}+{x}+{y}')
        
        # Bloomberg-style top header bar in blue
        header_frame = tk.Frame(desc_window, bg=self.colors['header_bg'], height=30)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        # Header with article number and source identifier
        header_label = tk.Label(
            header_frame, 
            text=f"{self.selected_article_index + 1}) {article['source']} ARTICLE DETAIL",
            font=self.header_font, 
            bg=self.colors['header_bg'],
            fg=self.colors['text'], 
            anchor='w', 
            padx=10, 
            pady=5
        )
        header_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Current time on the right side of header
        current_time_str = self.get_formatted_time()  # Use the same time formatting function as the main view
        
        date_label = tk.Label(
            header_frame,
            text=current_time_str,
            font=self.header_font,
            bg=self.colors['header_bg'],
            fg=self.colors['yellow'],
            padx=10,
            pady=5
        )
        date_label.pack(side=tk.RIGHT)
        
        # Main content area with metadata and description
        content_frame = tk.Frame(desc_window, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Article title section with orange headline color
        title_frame = tk.Frame(content_frame, bg=self.colors['bg'], padx=10, pady=5)
        title_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            title_frame, 
            text=article['title'],
            font=self.header_font, 
            bg=self.colors['bg'],
            fg=self.colors['highlight'],  # Orange highlight color
            anchor='w',
            wraplength=window_width-40,
            justify='left'
        )
        title_label.pack(fill=tk.X)
        
        # Article metadata section
        metadata_frame = tk.Frame(content_frame, bg='#111111', padx=10, pady=10)
        metadata_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Source info
        source_label = tk.Label(
            metadata_frame,
            text="SOURCE:",
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['blue'],
            anchor='w',
            width=15
        )
        source_label.grid(row=0, column=0, sticky='w', pady=2)
        
        source_value = tk.Label(
            metadata_frame,
            text=article['source'],
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['source'],
            anchor='w'
        )
        source_value.grid(row=0, column=1, sticky='w', pady=2)
        
        # Publication date info - using the same format as in the main list
        pubdate_label = tk.Label(
            metadata_frame,
            text="PUBLISH TIME:",
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['blue'],
            anchor='w',
            width=15
        )
        pubdate_label.grid(row=1, column=0, sticky='w', pady=2)
        
        # Use the same formatted time that's displayed in the main list view
        pubdate_value = tk.Label(
            metadata_frame,
            text=article['pub_date_str'],  # Using the pre-formatted time string from the article
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['yellow'],
            anchor='w'
        )
        pubdate_value.grid(row=1, column=1, sticky='w', pady=2)
        
        # Article link
        link_label = tk.Label(
            metadata_frame,
            text="ARTICLE URL:",
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['blue'],
            anchor='w',
            width=15
        )
        link_label.grid(row=2, column=0, sticky='w', pady=2)
        
        # Truncate link if too long
        link_text = article['link']
        if len(link_text) > 50:
            link_text = link_text[:47] + "..."
            
        link_value = tk.Label(
            metadata_frame,
            text=link_text,
            font=self.terminal_font,
            bg='#111111',
            fg=self.colors['green'],
            anchor='w',
            cursor="hand2"
        )
        link_value.grid(row=2, column=1, sticky='w', pady=2)
        link_value.bind("<Button-1>", lambda e: webbrowser.open(article['link']))
        
        # Divider line
        divider = tk.Frame(content_frame, bg=self.colors['header_bg'], height=2)
        divider.pack(fill=tk.X, padx=10, pady=5)
        
        # Article content label
        content_label = tk.Label(
            content_frame,
            text="ARTICLE CONTENT",
            font=self.header_font,
            bg=self.colors['bg'],
            fg=self.colors['blue'],
            anchor='w',
            padx=10,
            pady=5
        )
        content_label.pack(fill=tk.X)
        
        # Description text area with terminal-like styling
        desc_text = scrolledtext.ScrolledText(
            content_frame, 
            bg='#0a0a0a', 
            fg=self.colors['text'], 
            font=self.terminal_font,
            wrap=tk.WORD, 
            padx=15, 
            pady=15,
            borderwidth=0,
            highlightthickness=0
        )
        desc_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Get description if available, convert HTML to text if needed
        description = "No description available for this article."
        if 'description' in article and article['description']:
            # First try direct HTML unescaping (simpler and often works better for simple HTML)
            description = html.unescape(article['description'])
            
            # If it still looks like HTML, use html2text for conversion
            if "<" in description and ">" in description:
                # Initialize html2text converter with some configuration
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = True
                h.body_width = 0  # Don't wrap text at a specific width
                h.unicode_snob = True  # Use Unicode instead of ASCII
                
                try:
                    # Convert HTML to markdown-style text
                    description = h.handle(description)
                except Exception:
                    # If html2text fails, go back to the unescaped version
                    pass
            
            # Clean up the description text for better readability
            description = self.clean_description_text(description)
            
        desc_text.insert(tk.END, description)
        desc_text.config(state=tk.DISABLED)  # Make read-only
        
        # Status bar at bottom
        status_frame = tk.Frame(desc_window, bg='#333333', height=22)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        
        # Action buttons in status bar
        open_button = tk.Button(
            status_frame, 
            text="OPEN [O]", 
            command=lambda: webbrowser.open(article['link']),
            bg='#333333', 
            fg=self.colors['yellow'],
            activebackground='#444444', 
            activeforeground=self.colors['text'],
            borderwidth=0,
            padx=10
        )
        open_button.pack(side=tk.LEFT, padx=5, pady=2)
        
        close_button = tk.Button(
            status_frame, 
            text="CLOSE [ESC]", 
            command=desc_window.destroy,
            bg='#333333', 
            fg=self.colors['text'],
            activebackground='#444444', 
            activeforeground=self.colors['text'],
            borderwidth=0,
            padx=10
        )
        close_button.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Keyboard shortcuts info
        shortcuts_label = tk.Label(
            status_frame,
            text="O: Open in Browser | ESC: Close | SPACE: Scroll Down",
            font=self.terminal_font, 
            bg='#333333', 
            fg='#AAAAAA', 
            anchor='e'
        )
        shortcuts_label.pack(side=tk.RIGHT, padx=10)
        
        # Add keyboard shortcuts
        desc_window.bind("<Escape>", lambda e: desc_window.destroy())
        desc_window.bind("o", lambda e: webbrowser.open(article['link']))
        desc_window.bind("O", lambda e: webbrowser.open(article['link']))
        
        # Make the window modal
        desc_window.transient(self.root)
        desc_window.grab_set()
        desc_window.focus_set()
        
        return "break"
        
    def clean_description_text(self, text):
        """Clean up HTML or markdown text for better readability"""
        if not text:
            return text
            
        # Remove empty markdown links like [](url)
        text = re.sub(r'\[\]\(([^)]+)\)', r'\1', text)
        
        # Replace markdown links with text and URL
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
        
        # Replace consecutive spaces with a single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove multiple asterisks (bold/italic formatting)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # Remove multiple underscores (bold/italic formatting)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Clean up quotes
        text = re.sub(r'> ', '', text)
        
        # Convert multiple new lines to double new lines for paragraph breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Replace horizontal rules (--- or ***) with a clean separator
        text = re.sub(r'(\-{3,}|\*{3,})', '\n' + '-' * 40 + '\n', text)
        
        # Add proper spacing after periods if missing
        text = re.sub(r'\.([A-Z])', r'. \1', text)
        
        # Cleanup any HTML entities that might remain
        text = html.unescape(text)
        
        # Handle common HTML tags that might remain
        text = re.sub(r'</?br\s*/?>', '\n', text)
        text = re.sub(r'</?p\s*/?>', '\n\n', text)
        
        # General cleanup of any remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()
    
    def page_up(self, event=None):
        """Move the selection up by several items"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection if not already set
        if self.selected_article_index < 0:
            self.selected_article_index = 0
        
        # Move selection up by 10 items, but not less than 0
        self.selected_article_index = max(0, self.selected_article_index - 10)
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"
        
    def page_down(self, event=None):
        """Move the selection down by several items"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection if not already set
        if self.selected_article_index < 0:
            self.selected_article_index = 0
        
        # Move selection down by 10 items, but not beyond the last item
        self.selected_article_index = min(len(self.filtered_articles) - 1, self.selected_article_index + 10)
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"
    
    def jump_to_first(self, event=None):
        """Jump to the first article in the list"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection to the first article
        self.selected_article_index = 0
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling
        
    def jump_to_last(self, event=None):
        """Jump to the last article in the list"""
        if not self.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection to the last article
        self.selected_article_index = len(self.filtered_articles) - 1
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling
    
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