"""
UI components for the RSS Terminal application.
"""
import tkinter as tk
import time
import webbrowser
from tkinter import font, scrolledtext
import datetime as dt
import threading

from rss_terminal.utils import get_formatted_time, truncate_headline, html_to_text, get_weather_data, get_weather_icon

class TerminalUI:
    """Manages the UI components for the RSS Terminal"""
    
    def __init__(self, root, config_manager, feed_manager):
        self.root = root
        self.config = config_manager
        self.feed_manager = feed_manager
        
        # UI state variables
        self.selected_article_index = -1
        self.goto_mode = False
        self.goto_number = ""
        self.new_article_tags = []
        self.weather_data = None
        self._initial_display_done = False
        
        # Set up the window
        self._setup_window()
        
        # Set up fonts and colors
        self._setup_fonts()
        self._setup_colors()
        
        # Create the UI components
        self.create_ui()
        
        # Show the startup sequence
        self.show_startup_sequence()
        
        # Start weather update
        self.fetch_weather()
    
    def _setup_window(self):
        """Configure the main window"""
        self.root.title("RSS Terminal")
        self.root.configure(bg='black')
        
        # Set window size and position
        window_width = 1000
        window_height = 700
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    def _setup_fonts(self):
        """Set up fonts for the terminal-like display"""
        try:
            self.terminal_font = font.Font(family="IBM Plex Mono", size=9, weight="normal")
            self.header_font = font.Font(family="IBM Plex Mono", size=9, weight="bold")
        except:
            # Fallback to other monospace fonts
            for font_family in ["Consolas", "Lucida Console", "Andale Mono", "Courier New", "Courier"]:
                try:
                    self.terminal_font = font.Font(family=font_family, size=9, weight="normal")
                    self.header_font = font.Font(family=font_family, size=9, weight="bold")
                    break
                except:
                    continue
    
    def _setup_colors(self):
        """Set up colors for terminal display"""
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
    
    def create_ui(self):
        """Create all UI components"""
        # Filter menu bar
        self._create_filter_menu()
        
        # Main content area
        self._create_content_area()
        
        # Status bar
        self._create_status_bar()
        
        # Bind keyboard events
        self._bind_keyboard_events()
    
    def _create_filter_menu(self):
        """Create the filter menu bar at the top"""
        self.filter_frame = tk.Frame(self.root, bg=self.colors['bg'], height=25)
        self.filter_frame.pack(fill=tk.X, padx=0, pady=0)
        
        # Add "ALL" filter option
        all_filter = tk.Label(self.filter_frame, text="ALL", 
                             font=self.header_font, bg=self.colors['bg'],
                             fg=self.colors['highlight'],
                             padx=10, pady=3)
        all_filter.pack(side=tk.LEFT, padx=2)
        all_filter.bind("<Button-1>", lambda e: self.set_filter("ALL"))
        
        # Add separator
        separator = tk.Label(self.filter_frame, text="|", font=self.header_font, 
                            bg=self.colors['bg'], fg=self.colors['text'])
        separator.pack(side=tk.LEFT)
        
        # Add filter for each feed source
        for feed in self.config.feeds:
            feed_filter = tk.Label(self.filter_frame, text=feed['name'], 
                                  font=self.header_font, bg=self.colors['bg'],
                                  fg=self.colors['text'],
                                  padx=10, pady=3)
            feed_filter.pack(side=tk.LEFT, padx=2)
            feed_filter.bind("<Button-1>", lambda e, name=feed['name']: self.set_filter(name))
        
        # Right side information - weather display and time
        self.weather_display = tk.Label(self.filter_frame, text="", 
                              font=self.header_font, bg=self.colors['bg'], fg=self.colors['green'])
        self.weather_display.pack(side=tk.RIGHT, padx=5)
        
        # Time display
        self.time_display = tk.Label(self.filter_frame, text=get_formatted_time(timezone=self.config.timezone), 
                              font=self.header_font, bg=self.colors['bg'], fg=self.colors['yellow'])
        self.time_display.pack(side=tk.RIGHT, padx=5)
        
        # Update time every second
        def update_time():
            self.time_display.config(text=get_formatted_time(timezone=self.config.timezone))
            self.root.after(1000, update_time)
        update_time()
    
    def _create_content_area(self):
        """Create the main content area for displaying articles"""
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
        self.content_text.tag_configure("new_headline", foreground="#FFFFFF", background="#004400")
        self.content_text.tag_configure("number", foreground=self.colors['yellow'])
        self.content_text.tag_configure("source", foreground=self.colors['source'])
        self.content_text.tag_configure("time", foreground=self.colors['time'])
        self.content_text.tag_configure("selected", foreground=self.colors['text'], background=self.colors['selected'])
    
    def _create_status_bar(self):
        """Create the status bar at the bottom"""
        self.status_frame = tk.Frame(self.root, bg='#333333', height=22)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        
        self.status_label = tk.Label(self.status_frame, 
                                     text=f"Monitoring {len(self.config.feeds)} feeds | Refresh: {self.config.refresh_interval}s", 
                                     font=self.terminal_font, bg='#333333', fg='#CCCCCC', anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Add keyboard shortcuts info
        shortcuts_label = tk.Label(self.status_frame,
                                  text="↑/↓: Navigate | Enter: Open | Tab: Cycle Feeds | F5: Refresh | Home: Newest",
                                  font=self.terminal_font, bg='#333333', fg='#AAAAAA', anchor='e')
        shortcuts_label.pack(side=tk.RIGHT, padx=10)
    
    def _bind_keyboard_events(self):
        """Bind keyboard events for navigation and actions"""
        # Basic navigation
        self.root.bind("<Up>", self.select_previous_article)
        self.root.bind("<Down>", self.select_next_article)
        self.root.bind("<Return>", self.open_selected_article)
        self.root.bind("<space>", self.open_selected_article)
        self.root.bind("<Escape>", self.unselect_article)
        
        # Additional shortcuts
        self.root.bind("g", self.start_goto_mode)
        self.root.bind("d", self.show_article_description)
        self.root.bind("<Home>", self.jump_to_newest)
        
        # Page navigation
        self.root.bind("<Command-Up>", self.page_up)
        self.root.bind("<Command-Down>", self.page_down)
        self.root.bind("<Command-Shift-Up>", self.jump_to_first)
        self.root.bind("<Command-Shift-Down>", self.jump_to_last)
        
        # Bind number keys for goto mode
        for i in range(10):
            self.root.bind(str(i), self.handle_number_key)
        
        # Feed cycling
        self.root.bind("<Tab>", self.cycle_next_feed)
        self.root.bind("<Shift-Tab>", self.cycle_previous_feed)
        
        # Refresh key
        self.root.bind("<F5>", lambda e: self.feed_manager.fetch_all_feeds())
    
    def show_startup_sequence(self):
        """Show a startup sequence"""
        self.update_text(f"{'=' * 80}\n", text_style="time")
        self.update_text("  RSS TERMINAL VIEWER\n", text_style="headline")
        self.update_text(f"  Version 1.0 | {dt.datetime.now().strftime('%Y-%m-%d')}\n", text_style="time")
        self.update_text(f"{'=' * 80}\n\n", text_style="time")
        
        # System initialization messages
        messages = [
            "Initializing system...",
            "Configuring feeds...",
            f"Monitoring {len(self.config.feeds)} news sources...",
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
        self.update_text("  ⌘+Shift+↑/↓ : Jump to first/last article\n", text_style="source")
        self.update_text("  Home : Jump to newest articles\n\n", text_style="source")
    
    def update_text(self, text, delay_chars=False, flash=False, text_style=None):
        """Update the text display with the specified style"""
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
        """Update the status bar text"""
        self.status_label.config(text=text)
    
    def update_countdown(self):
        """Update the countdown timer in the status bar"""
        if self.feed_manager.last_check_time:
            elapsed = time.time() - self.feed_manager.last_check_time
            remaining = max(0, self.config.refresh_interval - elapsed)
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
    
    def display_articles(self, maintain_position=False):
        """Display articles based on current filter with incremental line-by-line updates"""
        # Store view info if needed
        if maintain_position and self.content_text.winfo_viewable():
            # Save exact scroll position 
            visible_fraction = self.content_text.yview()[0]
            
            # Also store the selected article if any
            selected_article = None
            if self.selected_article_index >= 0 and self.selected_article_index < len(self.feed_manager.filtered_articles):
                selected_article = self.feed_manager.filtered_articles[self.selected_article_index]
        else:
            visible_fraction = 0
            selected_article = None
        
        # Reset selection state
        self.selected_article_index = -1
        
        # This is our key for split-flap display effect - either rebuild or update incrementally
        if not self.content_text.get("1.0", "end-1c") or not maintain_position:
            # If the text widget is empty or not maintaining position, do a full rebuild
            self._rebuild_article_display()
        else:
            # Otherwise, do an incremental update - this is our split-flap effect
            self._update_article_display_incrementally()
        
        # Restore scroll position if maintaining position
        if maintain_position and visible_fraction > 0:
            # Use yview_moveto for precise scroll position restoration
            self.content_text.yview_moveto(visible_fraction)
            
            # Restore selection if previously selected
            if selected_article:
                for i, article in enumerate(self.feed_manager.filtered_articles):
                    if article.get('title') == selected_article.get('title'):
                        self.selected_article_index = i
                        self.highlight_selected_article(scroll_to_view=False)
                        break
    
    def _rebuild_article_display(self):
        """Completely rebuild the article display from scratch"""
        # Clear display
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)
        
        # Track if any new articles are displayed
        self.new_article_tags = []
        displayed_new_articles = False
        
        # Display each article
        for idx, article in enumerate(self.feed_manager.filtered_articles):
            # Insert the article with proper formatting
            self._format_and_insert_article(idx, article)
            
            # Track if this was a new article
            if article.get('is_new', False):
                displayed_new_articles = True
        
        # Handle flashing effect for new articles
        if displayed_new_articles:
            self.flash_new_articles(0)
            self.root.after(30000, self.reset_new_article_flags)
    
    def _update_article_display_incrementally(self):
        """Update the article display incrementally for the split-flap effect"""
        # Update the header first
        self.content_text.config(state=tk.NORMAL)
        
        # Remove the header line (was line 1)
        self.content_text.delete("1.0", "2.0")
        
        # Get the current content
        current_content = self.content_text.get("2.0", "end-1c")
        current_lines = current_content.split('\n')
        
        # Track new article tags and flags
        self.new_article_tags = []
        displayed_new_articles = False
        
        # Prepare for incremental updates
        line_index = 1  # Start at line 1 since header is removed
        
        # Process each article with a visual delay between updates
        self._incremental_update_with_delay(0, line_index, displayed_new_articles)
    
    def _format_and_insert_article(self, idx, article):
        """Format a single article and insert it into the display"""
        # Format row number
        num_text = f"{idx+1}) "
        self.update_text(num_text, text_style="number")
        
        # Format headline (title) with truncation
        headline_text = truncate_headline(article['title'])
        
        # Check if this is a new article and should be highlighted
        if article.get('is_new', False):
            # Insert with unique tag for this article to enable flashing
            tag_name = f"new_headline_{idx}"
            self.content_text.config(state=tk.NORMAL)
            self.content_text.insert(tk.END, headline_text, tag_name)
            self.content_text.tag_configure(tag_name, foreground="#FFFFFF", background="#004400")
            self.new_article_tags.append(tag_name)
        else:
            self.update_text(headline_text, text_style="headline")
        
        # Calculate space needed for right alignment
        window_width = self.content_text.winfo_width() // 8
        source_time_width = len(article['source']) + len(article['pub_date_str']) + 2
        
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
    
    def _create_formatted_article_line(self, idx, article):
        """Create a fully formatted line for an article without inserting it"""
        parts = []
        
        # Format row number
        num_text = f"{idx+1}) "
        parts.append((num_text, "number"))
        
        # Format headline with truncation
        headline_text = truncate_headline(article['title'])
        
        # Check if this is a new article
        if article.get('is_new', False):
            tag_name = f"new_headline_{idx}"
            parts.append((headline_text, tag_name))
        else:
            parts.append((headline_text, "headline"))
        
        # Calculate space needed for right alignment
        window_width = self.content_text.winfo_width() // 8
        source_time_width = len(article['source']) + len(article['pub_date_str']) + 2
        
        # Ensure enough space
        min_space = 5
        spaces_needed = window_width - len(num_text) - len(headline_text) - source_time_width - min_space
        spaces_needed = max(spaces_needed, min_space)
        spaces = " " * spaces_needed
        
        parts.append((spaces, None))
        
        # Add source and time
        parts.append((f"{article['source']} ", "source"))
        parts.append((f"{article['pub_date_str']}", "time"))
        
        return parts
    
    def _incremental_update_with_delay(self, article_idx, line_idx, any_new_articles):
        """Update articles one by one with a visual delay between updates"""
        # Base case - we've gone through all articles
        if article_idx >= len(self.feed_manager.filtered_articles):
            # Remove any remaining lines 
            self.content_text.config(state=tk.NORMAL)
            self.content_text.delete(f"{line_idx}.0", "end")
            self.content_text.config(state=tk.DISABLED)
            
            # Start flashing effect if any new articles
            if any_new_articles:
                self.flash_new_articles(0)
                self.root.after(30000, self.reset_new_article_flags)
            return
        
        # Get the current article
        article = self.feed_manager.filtered_articles[article_idx]
        
        # Update if this is a new article
        new_article = article.get('is_new', False)
        if new_article:
            any_new_articles = True
        
        # Create the formatted line
        parts = self._create_formatted_article_line(article_idx, article)
        
        # Update the line with a visual flicker effect
        self.content_text.config(state=tk.NORMAL)
        
        # Check if the line exists already - if so, delete it before inserting new content
        try:
            # Delete from beginning of line to beginning of next line (including newline)
            self.content_text.delete(f"{line_idx}.0", f"{line_idx+1}.0")
        except:
            # Line doesn't exist, which is fine for append operations
            pass
            
        # Insert at the specific line position (not at END)
        position = f"{line_idx}.0"
        
        # Insert the new line parts with their tags
        for text, tag in parts:
            if tag:
                if tag.startswith("new_headline_"):
                    self.new_article_tags.append(tag)
                    self.content_text.insert(position, text, tag)
                    self.content_text.tag_configure(tag, foreground="#FFFFFF", background="#004400")
                else:
                    self.content_text.insert(position, text, tag)
            else:
                self.content_text.insert(position, text)
            
            # Update the position for the next insert
            position = self.content_text.index(f"{position}+{len(text)}c")
        
        # Add newline
        self.content_text.insert(position, "\n")
        
        self.content_text.config(state=tk.DISABLED)
        
        # Schedule the next article update with a small delay for visual effect
        delay = 5 if new_article else 2  # Pause slightly longer on new articles
        self.root.after(delay, lambda: self._incremental_update_with_delay(article_idx + 1, line_idx + 1, any_new_articles))
    
    def flash_new_articles(self, step):
        """Create a flashing effect for new articles with improved visibility"""
        if not hasattr(self, 'new_article_tags') or not self.new_article_tags:
            return  # No new articles to flash
            
        # Colors for flashing effect
        colors = [
            {"fg": "#FFFFFF", "bg": "#004400"},  # Dark green
            {"fg": "#FFFFFF", "bg": "#006600"},  # Medium green
            {"fg": "#FFFFFF", "bg": "#008800"},  # Light green
            {"fg": "#FFFFFF", "bg": "#006600"}   # Medium green (transitioning back)
        ]
        
        # Get the current color based on step
        color = colors[step % len(colors)]
        
        # Apply the color to all new article tags
        for tag in self.new_article_tags:
            self.content_text.tag_configure(tag, foreground=color["fg"], background=color["bg"])
        
        # Schedule next flash with next color (faster transition for more dynamic effect)
        self.root.after(150, lambda: self.flash_new_articles((step + 1) % len(colors)))
    
    def reset_new_article_flags(self):
        """Reset the is_new flag on all articles and ensure proper tag handling"""
        # For each flashing tag, properly convert it to regular headline tag
        for tag_name in self.new_article_tags:
            # First find all ranges where this tag is applied
            ranges = self.content_text.tag_ranges(tag_name)
            
            # Process each start-end range pair
            for i in range(0, len(ranges), 2):
                if i+1 < len(ranges):  # Ensure we have both start and end
                    start = ranges[i]
                    end = ranges[i+1]
                    
                    # Remove the flashing tag
                    self.content_text.tag_remove(tag_name, start, end)
                    
                    # Apply the regular headline tag
                    self.content_text.tag_add("headline", start, end)
        
        # Reset the flags in the article data
        for article in self.feed_manager.articles:
            if article.get('is_new', False):
                article['is_new'] = False
        
        # Clear the new article tags list
        self.new_article_tags = []
    
    def set_filter(self, feed_name):
        """Set the current feed filter and refresh display"""
        self.feed_manager.apply_filter(feed_name)
        self.display_articles()
        
        # Update the filter buttons
        for widget in self.filter_frame.winfo_children():
            if isinstance(widget, tk.Label) and widget.cget("text") not in ["|", self.time_display.cget("text")]:
                if widget.cget("text") == feed_name:
                    widget.config(fg=self.colors['highlight'])
                else:
                    widget.config(fg=self.colors['text'])
    
    def select_previous_article(self, event=None):
        """Select the previous article in the list"""
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate
        
        # Decrement the index, wrapping around if necessary
        if self.selected_article_index > 0:
            self.selected_article_index -= 1
        else:
            self.selected_article_index = len(self.feed_manager.filtered_articles) - 1
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling

    def select_next_article(self, event=None):
        """Select the next article in the list"""
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate
        
        # Increment the index, wrapping around if necessary
        if self.selected_article_index < len(self.feed_manager.filtered_articles) - 1:
            self.selected_article_index += 1
        else:
            self.selected_article_index = 0
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling

    def highlight_selected_article(self, scroll_to_view=True):
        """Highlight the currently selected article"""
        if not self.feed_manager.filtered_articles:
            return  # No articles to highlight
            
        # First, remove all selection highlights
        self.content_text.tag_remove("selected", "1.0", tk.END)
        
        # Add 1 instead of 2 since there is no header row
        line_num = self.selected_article_index + 1
        
        # Apply selected style to the current line
        line_start = f"{line_num}.0"
        line_end = f"{line_num}.end"
        
        self.content_text.tag_add("selected", line_start, line_end)
        
        # Ensure the selected line is visible if requested
        if scroll_to_view:
            self.content_text.see(line_start)
        
        # Update status with selected article info
        article = self.feed_manager.filtered_articles[self.selected_article_index]
        self.update_status(f"Selected: {article['title']}")
    
    def open_selected_article(self, event=None):
        """Open the currently selected article in a web browser"""
        if not self.feed_manager.filtered_articles or self.selected_article_index < 0 or \
           self.selected_article_index >= len(self.feed_manager.filtered_articles):
            return "break"  # No articles or invalid index
        
        article = self.feed_manager.filtered_articles[self.selected_article_index]
        self.update_status(f"Opening article: {article['title']}")
        webbrowser.open(article['link'])
        return "break"  # Prevent default handling
    
    def unselect_article(self, event=None):
        """Unselect any selected article and return to default view"""
        # Reset the selection index
        self.selected_article_index = -1
        
        # Remove all selection highlights
        self.content_text.tag_remove("selected", "1.0", tk.END)
        
        # Reset the status bar to default message
        self.update_status(f"Monitoring {len(self.config.feeds)} feeds | Refresh: {self.config.refresh_interval}s")
        
        return "break"  # Prevent default handling
    
    def cycle_next_feed(self, event=None):
        """Cycle to the next feed in the list"""
        feed_names = ["ALL"] + [feed["name"] for feed in self.config.feeds]
        current_index = feed_names.index(self.feed_manager.current_filter)
        next_index = (current_index + 1) % len(feed_names)
        self.set_filter(feed_names[next_index])
        return "break"  # Prevent default tab behavior

    def cycle_previous_feed(self, event=None):
        """Cycle to the previous feed in the list"""
        feed_names = ["ALL"] + [feed["name"] for feed in self.config.feeds]
        current_index = feed_names.index(self.feed_manager.current_filter)
        prev_index = (current_index - 1) % len(feed_names)
        self.set_filter(feed_names[prev_index])
        return "break"  # Prevent default tab behavior
    
    def start_goto_mode(self, event=None):
        """Enter goto mode to jump to a specific article by number"""
        if not self.feed_manager.filtered_articles:
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
        if 1 <= article_num <= len(self.feed_manager.filtered_articles):
            self.selected_article_index = article_num - 1
            self.highlight_selected_article()
            
        # Exit goto mode
        self.goto_mode = False
        self.goto_number = ""
        
        # Restore normal Enter binding
        self.root.bind("<Return>", self.open_selected_article)
        
        return "break"
    
    def page_up(self, event=None):
        """Move the selection up by several items"""
        if not self.feed_manager.filtered_articles:
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
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection if not already set
        if self.selected_article_index < 0:
            self.selected_article_index = 0
        
        # Move selection down by 10 items, but not beyond the last item
        self.selected_article_index = min(len(self.feed_manager.filtered_articles) - 1, self.selected_article_index + 10)
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"
    
    def jump_to_first(self, event=None):
        """Jump to the first article in the list"""
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection to the first article
        self.selected_article_index = 0
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling
        
    def jump_to_last(self, event=None):
        """Jump to the last article in the list"""
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate
        
        # Set selection to the last article
        self.selected_article_index = len(self.feed_manager.filtered_articles) - 1
        
        # Highlight the selected article
        self.highlight_selected_article()
        return "break"  # Prevent default handling
        
    def jump_to_newest(self, event=None):
        """Jump to newest articles (top of list)"""
        if not self.feed_manager.filtered_articles:
            return "break"  # No articles to navigate to
        
        # Set selection to the newest article (first in the list)
        self.selected_article_index = 0
        
        # Highlight the selected article
        self.highlight_selected_article()
        
        # Scroll to show the newest articles
        self.content_text.see("2.0")  # First article after header
        
        # Remove the new content indicator if it exists
        try:
            self.content_text.tag_remove("new_content_indicator", "1.0", "1.end")
            
            # Restore normal header format
            if self.feed_manager.current_filter == "ALL":
                filter_text = "All Feeds"
            else:
                filter_text = f"{self.feed_manager.current_filter} Feed"
            
            self.content_text.config(state=tk.NORMAL)
            self.content_text.delete("1.0", "1.end")
            self.content_text.insert("1.0", f"{filter_text} - {len(self.feed_manager.filtered_articles)} Headlines", "headline")
            self.content_text.config(state=tk.DISABLED)
        except:
            # If no indicator exists, just continue
            pass
        
        # Update status
        self.update_status("Showing newest headlines")
        
        return "break"  # Prevent default handling
    
    def show_article_description(self, event=None):
        """Show description for the selected article in terminal style"""
        if not self.feed_manager.filtered_articles or self.selected_article_index < 0:
            self.update_status("No article selected")
            return "break"
            
        article = self.feed_manager.filtered_articles[self.selected_article_index]
        
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
        
        # Terminal-style top header bar in blue
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
        current_time_str = get_formatted_time(timezone=self.config.timezone)
        
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
        
        # Publication date info
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
        
        pubdate_value = tk.Label(
            metadata_frame,
            text=article['pub_date_str'],
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
            text="ARTICLE DESCRIPTION",
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
        description = html_to_text(article.get('description'))
            
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

    def handle_feed_update(self, new_articles, error=False):
        """Handle feed update completion or error with true split-flap display style"""
        if error and isinstance(new_articles, str):
            # Handle error message
            self.update_status(new_articles)
            return
        
        # Update the display with new articles
        if new_articles:
            # Count how many new articles match the current filter
            new_for_current_filter = 0
            for article in new_articles:
                if self.feed_manager.current_filter == "ALL" or article['source'] == self.feed_manager.current_filter:
                    new_for_current_filter += 1
            
            # Update status to show new article count (removed reference to number of new headlines)
            self.update_status(f"Total: {len(self.feed_manager.articles)}")
            
            # Determine if this is the initial display or an update
            if not self._initial_display_done:
                # For initial display, use regular display method and make sure we're at the top
                self.display_articles(maintain_position=False)
                # Explicitly scroll to top of the list after initial load
                self.root.after(100, lambda: self.content_text.see("1.0"))
                self._initial_display_done = True
            else:
                # For updates, ALWAYS maintain position (split-flap style)
                # This ensures the view doesn't jump when new content arrives
                self.display_articles(maintain_position=True)
        else:
            self.update_status(f"No new updates | Last check: {dt.datetime.now().strftime('%H:%M:%S')}")
            
    def fetch_weather(self):
        """Fetch weather data from the API in a separate thread"""
        def _fetch():
            try:
                weather = get_weather_data(self.config.airport_code)
                if weather:
                    # Update UI from the main thread
                    self.root.after(0, lambda: self.update_weather_display(weather))
            except Exception as e:
                print(f"Weather update error: {e}")
        
        # Start the weather fetching in a separate thread
        thread = threading.Thread(target=_fetch)
        thread.daemon = True
        thread.start()
        
        # Schedule next weather update based on config (convert seconds to milliseconds)
        self.root.after(self.config.weather_update_interval * 1000, self.fetch_weather)
    
    def update_weather_display(self, weather):
        """Update the weather display with current temperature and weather icon"""
        temp_f = weather['temp_f']
        temp_color = self.colors['green']
        
        # Get weather icon based on conditions
        weather_icon = get_weather_icon(weather)
        
        # Change color based on temperature - adjusted for Tucson's desert climate
        if temp_f > 105:
            temp_color = self.colors['red']  # Very hot (>105°F)
        elif temp_f > 95:
            temp_color = self.colors['yellow']  # Hot (95-105°F)
        elif temp_f > 80:
            temp_color = self.colors['green']  # Warm/pleasant (80-95°F)
        elif temp_f > 60:
            temp_color = self.colors['blue']  # Cool (60-80°F)
        else:
            temp_color = "#9370DB"  # Cold for Tucson (<60°F) - use purple
        
        # Format the display: weather icon, airport code, and temperature
        self.weather_display.config(
            text=f"{weather_icon} {weather['airport']} {temp_f}°F",
            fg=temp_color
        )