"""
Transaction Routes - Transaction Display and Management
=======================================================
Handles transaction listing, searching, sorting, and category assignment
"""

from flask import Blueprint, render_template, request, jsonify
import sqlite3

# Create blueprint for transaction routes
transaction_bp = Blueprint('transactions', __name__)

@transaction_bp.route('/')
def transacties():
    """Show all transactions in a table with categories - with server-side sorting and searching"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get parameters from URL
    zoekterm = request.args.get('zoek', '').strip()
    sort_column = request.args.get('sort', 'datum')  # Default: datum
    sort_order = request.args.get('order', 'desc')   # Default: desc (newest first)
    
    # Validate sort parameters for security
    valid_columns = {
        'datum': 't.datum',
        'naam': 't.naam', 
        'bedrag': 't.bedrag',
        'code': 't.code',
        'categorie': 'c.naam'
    }
    
    valid_orders = ['asc', 'desc']
    
    # Use defaults if parameters are invalid
    if sort_column not in valid_columns:
        sort_column = 'datum'
    if sort_order not in valid_orders:
        sort_order = 'desc'
    
    # Build SQL query
    base_query = '''
        SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
               t.tegenrekening, t.saldo_na_mutatie, c.naam as categorie_naam, c.id as categorie_id
        FROM transacties t
        LEFT JOIN categorien c ON t.categorie_id = c.id
    '''
    
    # WHERE clause for searching
    params = []
    if zoekterm:
        where_clause = '''
            WHERE (t.datum LIKE ? OR 
                   t.naam LIKE ? OR 
                   t.bedrag LIKE ? OR 
                   t.code LIKE ? OR 
                   t.mededelingen LIKE ? OR 
                   t.tegenrekening LIKE ? OR
                   c.naam LIKE ?)
        '''
        search_pattern = f'%{zoekterm}%'
        params = [search_pattern] * 7
        base_query += where_clause
    
    # ORDER BY clause
    sql_column = valid_columns[sort_column]
    
    # Special handling for category (NULL values at bottom)
    if sort_column == 'categorie':
        if sort_order == 'asc':
            order_clause = f' ORDER BY {sql_column} IS NULL, {sql_column} ASC, t.datum DESC'
        else:
            order_clause = f' ORDER BY {sql_column} IS NULL, {sql_column} DESC, t.datum DESC'
    else:
        # For other columns: secondary sort on date (newest first)
        if sort_column == 'datum':
            order_clause = f' ORDER BY {sql_column} {sort_order.upper()}, t.id {sort_order.upper()}'
        else:
            order_clause = f' ORDER BY {sql_column} {sort_order.upper()}, t.datum DESC'
    
    # Complete query with limit
    full_query = base_query + order_clause + ' LIMIT 1000'
    
    cursor.execute(full_query, params)
    transacties_data = cursor.fetchall()
    
    # Get all categories for dropdown
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    alle_categorien = cursor.fetchall()
    
    # Count total results
    if zoekterm:
        count_query = '''
            SELECT COUNT(*) FROM transacties t
            LEFT JOIN categorien c ON t.categorie_id = c.id
            WHERE (t.datum LIKE ? OR 
                   t.naam LIKE ? OR 
                   t.bedrag LIKE ? OR 
                   t.code LIKE ? OR 
                   t.mededelingen LIKE ? OR 
                   t.tegenrekening LIKE ? OR
                   c.naam LIKE ?)
        '''
        cursor.execute(count_query, params)
    else:
        cursor.execute('SELECT COUNT(*) FROM transacties')
    
    totaal_resultaten = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('transacties.html', 
                         transacties=transacties_data,
                         alle_categorien=alle_categorien,
                         zoekterm=zoekterm,
                         totaal_resultaten=totaal_resultaten,
                         getoond_resultaten=len(transacties_data),
                         current_sort=sort_column,
                         current_order=sort_order)

@transaction_bp.route('/update-categorie', methods=['POST'])
def update_transactie_categorie():
    """Update the category of a transaction"""
    transactie_id = request.form.get('transactie_id')
    categorie_id = request.form.get('categorie_id')
    
    # Convert empty string to None for database
    if categorie_id == '':
        categorie_id = None
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE id = ?
    ''', (categorie_id, transactie_id))
    
    conn.commit()
    conn.close()
    
    return '', 204  # No content response for AJAX calls