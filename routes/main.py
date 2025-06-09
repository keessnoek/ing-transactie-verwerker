"""
Main Routes - Homepage and Navigation
=====================================
Clean homepage routing with proper blueprint structure
"""

from flask import Blueprint, render_template

# Create blueprint for main routes
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Homepage with navigation to all features"""
    return render_template('index.html')