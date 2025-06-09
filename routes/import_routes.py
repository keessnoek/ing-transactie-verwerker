"""
Import Routes - CSV File Upload and Processing
===============================================
Handles all CSV import functionality with proper separation
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
import sqlite3
import os
from werkzeug.utils import secure_filename
from services.csv_processor import process_ing_csv

# Create blueprint for import routes
import_bp = Blueprint('import', __name__)

@import_bp.route('/', methods=['GET', 'POST'])
def importeren():
    """Upload and process ING CSV files"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Geen bestand geselecteerd', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Geen bestand geselecteerd', 'error')
            return redirect(request.url)
        
        if file and file.filename.lower().endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the CSV file using our service
            result = process_ing_csv(filepath)
            
            # Show results
            if result['imported'] > 0:
                flash(f"Succesvol {result['imported']} transacties geïmporteerd!", 'success')
            if result['duplicates'] > 0:
                flash(f"{result['duplicates']} duplicaten overgeslagen", 'info')
            if result['errors'] > 0:
                flash(f"{result['errors']} fouten opgetreden", 'warning')
                for error in result['error_details'][:5]:  # Show max 5 errors
                    flash(error, 'error')
            
            # Remove temporary file
            os.remove(filepath)
            
        else:
            flash('Alleen CSV bestanden zijn toegestaan', 'error')
    
    # Get most recent date from database for display
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(datum) FROM transacties')
    laatste_datum = cursor.fetchone()[0]
    conn.close()
    
    return render_template('importeren.html', laatste_datum=laatste_datum)