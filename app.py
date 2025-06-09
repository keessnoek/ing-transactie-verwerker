"""
ING Transactie Verwerker - Gerefactorde Flask Application
=========================================================
Clean, maintainable architecture met proper separation of concerns
"""

from flask import Flask
import os

# Import onze nieuwe modules
from models.database import init_database
from routes.main import main_bp
from routes.import_routes import import_bp  
from routes.transaction_routes import transaction_bp
from routes.category_routes import category_bp
from routes.report_routes import report_bp

def create_app():
    """Application factory pattern - zoals de professionals het doen"""
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = 'jouw_geheime_sleutel_hier'  # TODO: Move to config.py
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize database
    with app.app_context():
        init_database()
    
    # Register blueprints - modular route organization
    app.register_blueprint(main_bp)
    app.register_blueprint(import_bp, url_prefix='/import')
    app.register_blueprint(transaction_bp, url_prefix='/transactions')
    app.register_blueprint(category_bp, url_prefix='/categories')
    app.register_blueprint(report_bp, url_prefix='/reports')
    
    return app

# Application instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)