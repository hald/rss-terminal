"""
Main application module for RSS Terminal.
This module coordinates between the UI, feed manager, and configuration.
"""
import tkinter as tk

from rss_terminal.config import ConfigManager
from rss_terminal.feed_manager import FeedManager
from rss_terminal.ui import TerminalUI

class RSSTerminalApp:
    """
    Main application class that coordinates all components
    """
    
    def __init__(self, root):
        """Initialize the application with all necessary components"""
        self.root = root
        
        # Initialize configuration
        self.config_manager = ConfigManager()
        
        # Initialize feed manager
        self.feed_manager = FeedManager(self.config_manager)
        
        # Initialize UI 
        self.ui = TerminalUI(self.root, self.config_manager, self.feed_manager)
        
        # Set up the feed update callback
        self.feed_manager.fetch_callback = self.ui.handle_feed_update
        
        # Start background feed fetching
        self.initial_setup()
    
    def initial_setup(self):
        """Perform initial setup tasks"""
        # Start countdown timer
        self.ui.update_countdown()
        
        # Schedule initial feed fetch
        self.root.after(1000, self.feed_manager.initial_fetch)
    
    def on_closing(self):
        """Cleanup when closing the application"""
        self.feed_manager.stop_fetching()
        self.root.destroy()