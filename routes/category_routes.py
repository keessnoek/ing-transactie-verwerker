"""
Category Routes - Category Management and Smart Categorization
==============================================================
Handles all category CRUD operations and smart categorization features
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import re

# Create blueprint for category routes
category_bp = Blueprint('categories', __name__)

@category_bp.route('/')
def categorien():
    """Show all categories with transaction count per category"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all categories with transaction counts
    cursor.execute('''
        SELECT c.id, c.naam, c.beschrijving, c.kleur, 
               COUNT(t.id) as aantal_transacties,
               COALESCE(SUM(CASE WHEN t.bedrag < 0 THEN t.bedrag ELSE 0 END), 0) as totaal_uitgaven,
               COALESCE(SUM(CASE WHEN t.bedrag > 0 THEN t.bedrag ELSE 0 END), 0) as totaal_inkomsten
        FROM categorien c
        LEFT JOIN transacties t ON c.id = t.categorie_id
        GROUP BY c.id, c.naam, c.beschrijving, c.kleur
        ORDER BY aantal_transacties DESC, c.naam
    ''')
    
    categorien_data = cursor.fetchall()
    
    # Count transactions without category
    cursor.execute('SELECT COUNT(*) FROM transacties WHERE categorie_id IS NULL')
    zonder_categorie = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('categorien.html', 
                         categorien=categorien_data, 
                         zonder_categorie=zonder_categorie)

@category_bp.route('/nieuw', methods=['POST'])
def nieuwe_categorie():
    """Add a new category"""
    naam = request.form.get('naam', '').strip()
    beschrijving = request.form.get('beschrijving', '').strip()
    kleur = request.form.get('kleur', '#3498db')
    
    if not naam:
        flash('Categorienaam is verplicht', 'error')
        return redirect(url_for('categories.categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO categorien (naam, beschrijving, kleur)
            VALUES (?, ?, ?)
        ''', (naam, beschrijving, kleur))
        conn.commit()
        flash(f'Categorie "{naam}" toegevoegd!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Categorie "{naam}" bestaat al', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('categories.categorien'))

@category_bp.route('/<int:categorie_id>/bewerken', methods=['POST'])
def bewerk_categorie(categorie_id):
    """Edit an existing category"""
    naam = request.form.get('naam', '').strip()
    beschrijving = request.form.get('beschrijving', '').strip()
    kleur = request.form.get('kleur', '#3498db')
    
    if not naam:
        flash('Categorienaam is verplicht', 'error')
        return redirect(url_for('categories.categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE categorien 
            SET naam = ?, beschrijving = ?, kleur = ?
            WHERE id = ?
        ''', (naam, beschrijving, kleur, categorie_id))
        conn.commit()
        flash(f'Categorie "{naam}" bijgewerkt!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Categorienaam "{naam}" bestaat al', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('categories.categorien'))

@category_bp.route('/<int:categorie_id>/verwijderen', methods=['POST'])
def verwijder_categorie(categorie_id):
    """Delete a category (transactions are kept but unlinked)"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get category name for confirmation message
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie = cursor.fetchone()
    
    if not categorie:
        flash('Categorie niet gevonden', 'error')
        conn.close()
        return redirect(url_for('categories.categorien'))
    
    naam = categorie[0]
    
    # Unlink all transactions from this category
    cursor.execute('UPDATE transacties SET categorie_id = NULL WHERE categorie_id = ?', (categorie_id,))
    
    # Delete the category
    cursor.execute('DELETE FROM categorien WHERE id = ?', (categorie_id,))
    
    conn.commit()
    conn.close()
    
    flash(f'Categorie "{naam}" verwijderd. Transacties zijn behouden maar hebben geen categorie meer.', 'info')
    return redirect(url_for('categories.categorien'))

@category_bp.route('/bulk-toewijzen', methods=['POST'])
def bulk_toewijzen():
    """Assign multiple transactions to a category at once"""
    categorie_id = request.form.get('categorie_id')
    transactie_ids = request.form.getlist('transactie_ids')
    
    if not categorie_id or not transactie_ids:
        flash('Geen categorie of transacties geselecteerd', 'error')
        return redirect(url_for('categories.categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Update all selected transactions
    placeholders = ','.join('?' * len(transactie_ids))
    cursor.execute(f'''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE id IN ({placeholders})
    ''', [categorie_id] + transactie_ids)
    
    conn.commit()
    conn.close()
    
    flash(f'{len(transactie_ids)} transacties toegewezen aan categorie!', 'success')
    return redirect(url_for('categories.categorien'))

@category_bp.route('/bulk-winkel', methods=['POST'])
def bulk_winkel_toewijzen():
    """Assign all transactions from a specific store to a category"""
    categorie_id = request.form.get('categorie_id')
    winkel_naam = request.form.get('winkel_naam')
    
    if not categorie_id or not winkel_naam:
        flash('Categorie of winkelnaam ontbreekt', 'error')
        return redirect(url_for('categories.categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all uncategorized transactions from this store and filter with Python regex
    cursor.execute('''
        SELECT id FROM transacties 
        WHERE categorie_id IS NULL
    ''')
    
    alle_transacties = cursor.fetchall()
    
    # Filter with Python regex for whole word matching
    pattern = r'\b' + re.escape(winkel_naam) + r'\b'
    to_update_ids = []
    
    for (transactie_id,) in alle_transacties:
        cursor.execute('SELECT naam FROM transacties WHERE id = ?', (transactie_id,))
        naam = cursor.fetchone()[0]
        if re.search(pattern, naam, re.IGNORECASE):
            to_update_ids.append(transactie_id)
    
    if not to_update_ids:
        flash(f'Geen ongecategoriseerde {winkel_naam} transacties gevonden', 'info')
        conn.close()
        return redirect(url_for('categories.categorien'))
    
    # Update all matching transactions
    placeholders = ','.join('?' * len(to_update_ids))
    cursor.execute(f'''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE id IN ({placeholders})
    ''', [categorie_id] + to_update_ids)
    
    conn.commit()
    
    # Get category name for confirmation message
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie_naam = cursor.fetchone()[0]
    conn.close()
    
    flash(f'{len(to_update_ids)} {winkel_naam} transacties toegewezen aan "{categorie_naam}"!', 'success')
    return redirect(url_for('categories.categorien'))

@category_bp.route('/suggesties/<int:categorie_id>')
def categorie_suggesties(categorie_id):
    """Find transactions similar to this category for bulk assignment"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get category info
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie = cursor.fetchone()
    
    if not categorie:
        flash('Categorie niet gevonden', 'error')
        return redirect(url_for('categories.categorien'))
    
    # Get all transactions from this category to find patterns
    cursor.execute('''
        SELECT DISTINCT naam 
        FROM transacties 
        WHERE categorie_id = ? 
        LIMIT 20
    ''', (categorie_id,))
    
    bestaande_namen = [row[0] for row in cursor.fetchall()]
    
    # Find similar uncategorized transactions
    suggesties = []
    winkel_patronen = {}
    
    if bestaande_namen:
        # Get ALL uncategorized transactions and filter with Python regex
        cursor.execute('''
            SELECT DISTINCT t.id, t.datum, t.naam, t.bedrag
            FROM transacties t
            WHERE t.categorie_id IS NULL 
            ORDER BY t.datum DESC
        ''')
        
        alle_ongecategoriseerd = cursor.fetchall()
        
        # Filter with Python regex for exact matches
        for transactie_id, datum, naam, bedrag in alle_ongecategoriseerd:
            matched = False
            
            # Check exact matches
            for bestaande_naam in bestaande_namen:
                if naam == bestaande_naam:
                    suggesties.append((transactie_id, datum, naam, bedrag))
                    matched = True
                    break
            
            # Check partial matches with whole words
            if not matched:
                for bestaande_naam in bestaande_namen:
                    # Try first word of existing name as pattern
                    eerste_woord = bestaande_naam.split()[0] if bestaande_naam.split() else bestaande_naam
                    if len(eerste_woord) > 3:  # Only if word is long enough
                        pattern = r'\b' + re.escape(eerste_woord) + r'\b'
                        if re.search(pattern, naam, re.IGNORECASE):
                            suggesties.append((transactie_id, datum, naam, bedrag))
                            break
        
        # Limit suggestions to 50
        suggesties = suggesties[:50]
        
        # Detect store patterns for bulk options
        for naam in bestaande_namen:
            winkel_kandidaten = []
            
            # Known supermarket patterns
            if 'ALBERT HEIJN' in naam.upper():
                winkel_kandidaten.append('ALBERT HEIJN')
            elif 'JUMBO' in naam.upper():
                winkel_kandidaten.append('JUMBO')
            elif 'LIDL' in naam.upper():
                winkel_kandidaten.append('LIDL')
            elif 'DEKAMARKT' in naam.upper():
                winkel_kandidaten.append('DEKAMARKT')
            elif 'ALDI' in naam.upper():
                winkel_kandidaten.append('ALDI')
            elif 'PLUS' in naam.upper():
                winkel_kandidaten.append('PLUS')
            else:
                # Fallback: first word
                eerste_woord = naam.split()[0] if naam.split() else naam
                if len(eerste_woord) > 3:
                    winkel_kandidaten.append(eerste_woord)
            
            # Count uncategorized transactions per store with regex
            for winkel in winkel_kandidaten:
                if winkel not in winkel_patronen:
                    cursor.execute('''
                        SELECT naam FROM transacties 
                        WHERE categorie_id IS NULL
                    ''')
                    alle_namen = [row[0] for row in cursor.fetchall()]
                    
                    # Count matches with regex
                    pattern = r'\b' + re.escape(winkel) + r'\b'
                    aantal = sum(1 for n in alle_namen if re.search(pattern, n, re.IGNORECASE))
                    
                    if aantal >= 5:  # Only show if at least 5 transactions
                        winkel_patronen[winkel] = aantal
    
    conn.close()
    
    return render_template('categorie_suggesties.html', 
                         categorie=categorie[0], 
                         categorie_id=categorie_id,
                         suggesties=suggesties,
                         winkel_patronen=winkel_patronen)