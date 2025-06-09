"""
Report Routes - Analytics, Dashboard and Reports
================================================
Handles all reporting functionality including dashboard, kruistabel, and smart categorization
"""

from flask import Blueprint, render_template, request, jsonify
import sqlite3
import re
from datetime import datetime

# Create blueprint for report routes
report_bp = Blueprint('reports', __name__)

@report_bp.route('/dashboard')
def dashboard():
    """Dashboard with graphical displays of transactions"""
    # Get available years and months for dropdowns
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all available year/month combinations
    cursor.execute('''
        SELECT DISTINCT jaar, maand 
        FROM transacties 
        ORDER BY jaar DESC, maand DESC
    ''')
    
    beschikbare_periodes = cursor.fetchall()
    
    # Get unique years
    jaren = sorted(list(set([periode[0] for periode in beschikbare_periodes])), reverse=True)
    
    # Default: current month/year or latest available
    if beschikbare_periodes:
        default_jaar = beschikbare_periodes[0][0]  # Most recent year
        default_maand = beschikbare_periodes[0][1]  # Most recent month
    else:
        default_jaar = datetime.now().year
        default_maand = datetime.now().month
    
    conn.close()
    
    return render_template('dashboard.html', 
                         jaren=jaren,
                         default_jaar=default_jaar,
                         default_maand=default_maand)

@report_bp.route('/dashboard/uitgaven-per-maand')
def dashboard_uitgaven_per_maand():
    """API for expenses per month with date selection"""
    # Get parameters (default = last 12 months)
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if eind_jaar and eind_maand:
        # Calculate start date (12 months back)
        if eind_maand == 12:
            start_jaar = eind_jaar
            start_maand = 1
        else:
            start_jaar = eind_jaar - 1
            start_maand = eind_maand + 1
        
        # Get data for specific period
        cursor.execute('''
            SELECT jaar, maand, SUM(bedrag) as totaal
            FROM transacties 
            WHERE bedrag < 0 
            AND ((jaar = ? AND maand >= ?) OR 
                 (jaar > ? AND jaar < ?) OR 
                 (jaar = ? AND maand <= ?))
            GROUP BY jaar, maand
            ORDER BY jaar, maand
        ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    else:
        # Default: last 12 months
        cursor.execute('''
            SELECT jaar, maand, SUM(bedrag) as totaal
            FROM transacties 
            WHERE bedrag < 0
            GROUP BY jaar, maand
            ORDER BY jaar DESC, maand DESC
            LIMIT 12
        ''')
    
    data = cursor.fetchall()
    conn.close()
    
    # Convert to Chart.js format
    maanden = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
    
    labels = []
    bedragen = []
    
    # For specific period: chronological order
    # For default: reverse for chronological order
    data_sorted = data if (eind_jaar and eind_maand) else reversed(data)
    
    for jaar, maand, totaal in data_sorted:
        labels.append(f"{maanden[maand-1]} {jaar}")
        bedragen.append(abs(totaal))
    
    return jsonify({
        'labels': labels,
        'data': bedragen
    })

@report_bp.route('/dashboard/top-categorien')
def dashboard_top_categorien():
    """API for top expense categories with category IDs for drill-down"""
    eind_jaar = request.args.get('jaar', type=int) or datetime.now().year
    eind_maand = request.args.get('maand', type=int) or datetime.now().month
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Calculate period (12 months)
    if eind_maand == 12:
        start_jaar = eind_jaar
        start_maand = 1
    else:
        start_jaar = eind_jaar - 1
        start_maand = eind_maand + 1
    
    cursor.execute('''
        SELECT c.id, c.naam, c.kleur, SUM(t.bedrag) as totaal
        FROM transacties t
        JOIN categorien c ON t.categorie_id = c.id
        WHERE t.bedrag < 0 
        AND ((t.jaar = ? AND t.maand >= ?) OR 
             (t.jaar > ? AND t.jaar < ?) OR 
             (t.jaar = ? AND t.maand <= ?))
        GROUP BY c.id, c.naam, c.kleur
        ORDER BY SUM(t.bedrag) ASC
        LIMIT 8
    ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    
    data = cursor.fetchall()
    
    # Also uncategorized transactions for this period
    cursor.execute('''
        SELECT SUM(bedrag) as totaal
        FROM transacties 
        WHERE bedrag < 0 AND categorie_id IS NULL
        AND ((jaar = ? AND maand >= ?) OR 
             (jaar > ? AND jaar < ?) OR 
             (jaar = ? AND maand <= ?))
    ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    
    zonder_categorie = cursor.fetchone()[0] or 0
    
    conn.close()
    
    labels = []
    bedragen = []
    kleuren = []
    categorie_ids = []
    
    for cat_id, naam, kleur, totaal in data:
        labels.append(naam)
        bedragen.append(abs(totaal))
        kleuren.append(kleur)
        categorie_ids.append(cat_id)
    
    if abs(zonder_categorie) > 50:
        labels.append('Zonder categorie')
        bedragen.append(abs(zonder_categorie))
        kleuren.append('#6c757d')
        categorie_ids.append(None)
    
    return jsonify({
        'labels': labels,
        'data': bedragen,
        'colors': kleuren,
        'categorie_ids': categorie_ids
    })

@report_bp.route('/dashboard/inkomsten-uitgaven')
def dashboard_inkomsten_uitgaven():
    """API for income vs expenses with date selection"""
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if eind_jaar and eind_maand:
        # Last 6 months from chosen period
        if eind_maand > 6:
            start_jaar = eind_jaar
            start_maand = eind_maand - 5
        else:
            start_jaar = eind_jaar - 1
            start_maand = eind_maand + 6
        
        cursor.execute('''
            SELECT jaar, maand,
                   SUM(CASE WHEN bedrag > 0 THEN bedrag ELSE 0 END) as inkomsten,
                   SUM(CASE WHEN bedrag < 0 THEN bedrag ELSE 0 END) as uitgaven
            FROM transacties 
            WHERE ((jaar = ? AND maand >= ?) OR 
                   (jaar > ? AND jaar < ?) OR 
                   (jaar = ? AND maand <= ?))
            GROUP BY jaar, maand
            ORDER BY jaar, maand
        ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    else:
        # Default: last 6 months
        cursor.execute('''
            SELECT jaar, maand,
                   SUM(CASE WHEN bedrag > 0 THEN bedrag ELSE 0 END) as inkomsten,
                   SUM(CASE WHEN bedrag < 0 THEN bedrag ELSE 0 END) as uitgaven
            FROM transacties 
            GROUP BY jaar, maand
            ORDER BY jaar DESC, maand DESC
            LIMIT 6
        ''')
    
    data = cursor.fetchall()
    conn.close()
    
    maanden = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
    
    labels = []
    inkomsten_data = []
    uitgaven_data = []
    
    data_sorted = data if (eind_jaar and eind_maand) else reversed(data)
    
    for jaar, maand, inkomsten, uitgaven in data_sorted:
        labels.append(f"{maanden[maand-1]} {jaar}")
        inkomsten_data.append(inkomsten)
        uitgaven_data.append(abs(uitgaven))
    
    return jsonify({
        'labels': labels,
        'inkomsten': inkomsten_data,
        'uitgaven': uitgaven_data
    })

@report_bp.route('/dashboard/statistieken')
def dashboard_statistieken():
    """API for general statistics with date selection"""
    eind_jaar = request.args.get('jaar', type=int) or datetime.now().year
    eind_maand = request.args.get('maand', type=int) or datetime.now().month
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Calculate period (12 months)
    if eind_maand == 12:
        start_jaar = eind_jaar
        start_maand = 1
    else:
        start_jaar = eind_jaar - 1
        start_maand = eind_maand + 1
    
    # Totals for selected period
    cursor.execute('''
        SELECT 
            COUNT(*) as totaal_transacties,
            SUM(CASE WHEN bedrag > 0 THEN bedrag ELSE 0 END) as totaal_inkomsten,
            SUM(CASE WHEN bedrag < 0 THEN bedrag ELSE 0 END) as totaal_uitgaven,
            COUNT(DISTINCT categorie_id) as gecategoriseerd
        FROM transacties 
        WHERE ((jaar = ? AND maand >= ?) OR 
               (jaar > ? AND jaar < ?) OR 
               (jaar = ? AND maand <= ?))
    ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    
    stats = cursor.fetchone()
    
    # Number of categories (total, not period-specific)
    cursor.execute('SELECT COUNT(*) FROM categorien')
    aantal_categorien = cursor.fetchone()[0]
    
    # Without category for this period
    cursor.execute('''
        SELECT COUNT(*) FROM transacties 
        WHERE categorie_id IS NULL
        AND ((jaar = ? AND maand >= ?) OR 
             (jaar > ? AND jaar < ?) OR 
             (jaar = ? AND maand <= ?))
    ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    
    zonder_categorie = cursor.fetchone()[0]
    
    conn.close()
    
    totaal_transacties, totaal_inkomsten, totaal_uitgaven, gecategoriseerd = stats
    netto = totaal_inkomsten + totaal_uitgaven  # expenses are negative
    
    # Determine period label
    maanden = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
    periode_label = f"{maanden[start_maand-1]} {start_jaar} - {maanden[eind_maand-1]} {eind_jaar}"
    
    return jsonify({
        'totaal_transacties': totaal_transacties,
        'totaal_inkomsten': totaal_inkomsten,
        'totaal_uitgaven': abs(totaal_uitgaven),
        'netto_resultaat': netto,
        'aantal_categorien': aantal_categorien,
        'zonder_categorie': zonder_categorie,
        'periode': periode_label,
        'eind_jaar': eind_jaar,
        'eind_maand': eind_maand
    })

@report_bp.route('/')
def rapportages():
    """Main reports page with kruistabel"""
    # Get available years for dropdowns
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT jaar FROM transacties ORDER BY jaar DESC')
    jaren = [row[0] for row in cursor.fetchall()]
    
    # Get most recent year as default
    huidig_jaar = request.args.get('jaar', str(jaren[0]) if jaren else str(datetime.now().year))
    
    conn.close()
    
    return render_template('rapportages.html', jaren=jaren, huidig_jaar=int(huidig_jaar))

@report_bp.route('/kruistabel')
def kruistabel_data():
    """API endpoint for kruistabel data with category IDs"""
    jaar = request.args.get('jaar', type=int)
    
    if not jaar:
        return jsonify({'error': 'Jaar parameter ontbreekt'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all categories
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    categorien = cursor.fetchall()
    
    # Build kruistabel data
    kruistabel_data = {}
    categorie_ids = {}
    maand_totalen = {i: 0 for i in range(1, 13)}
    categorie_totalen = {}
    
    # For each category, get amounts per month
    for cat_id, cat_naam in categorien:
        cursor.execute('''
            SELECT maand, SUM(bedrag) 
            FROM transacties 
            WHERE categorie_id = ? AND jaar = ? 
            GROUP BY maand
        ''', (cat_id, jaar))
        
        maand_bedragen = dict(cursor.fetchall())
        kruistabel_data[cat_naam] = {}
        categorie_ids[cat_naam] = cat_id
        categorie_totaal = 0
        
        for maand in range(1, 13):
            bedrag = maand_bedragen.get(maand, 0)
            kruistabel_data[cat_naam][maand] = bedrag
            maand_totalen[maand] += bedrag
            categorie_totaal += bedrag
        
        categorie_totalen[cat_naam] = categorie_totaal
    
    # Also transactions without category
    cursor.execute('''
        SELECT maand, SUM(bedrag) 
        FROM transacties 
        WHERE categorie_id IS NULL AND jaar = ? 
        GROUP BY maand
    ''', (jaar,))
    
    maand_bedragen = dict(cursor.fetchall())
    kruistabel_data['Zonder categorie'] = {}
    categorie_ids['Zonder categorie'] = None
    zonder_categorie_totaal = 0
    
    for maand in range(1, 13):
        bedrag = maand_bedragen.get(maand, 0)
        kruistabel_data['Zonder categorie'][maand] = bedrag
        maand_totalen[maand] += bedrag
        zonder_categorie_totaal += bedrag
    
    categorie_totalen['Zonder categorie'] = zonder_categorie_totaal
    
    # Calculate grand total
    grand_total = sum(maand_totalen.values())
    
    conn.close()
    
    return jsonify({
        'data': kruistabel_data,
        'categorie_ids': categorie_ids,
        'maand_totalen': maand_totalen,
        'categorie_totalen': categorie_totalen,
        'grand_total': grand_total,
        'jaar': jaar
    })

@report_bp.route('/transactie-details')
def transactie_details():
    """API for transaction details drill-down"""
    jaar = request.args.get('jaar', type=int)
    maand = request.args.get('maand', type=int)
    categorie_id_str = request.args.get('categorie_id')
    
    # Validation
    if not jaar or not maand:
        return jsonify({'error': 'Jaar en maand parameters zijn verplicht'}), 400
    
    if maand < 1 or maand > 12:
        return jsonify({'error': 'Maand moet tussen 1 en 12 zijn'}), 400
    
    # Convert categorie_id
    categorie_id = None
    if categorie_id_str and categorie_id_str != 'null':
        try:
            categorie_id = int(categorie_id_str)
        except ValueError:
            return jsonify({'error': 'Ongeldige categorie_id'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Build query based on category
    if categorie_id is not None:
        cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
        categorie_result = cursor.fetchone()
        if not categorie_result:
            conn.close()
            return jsonify({'error': f'Categorie {categorie_id} niet gevonden'}), 404
        categorie_naam = categorie_result[0]
        
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, c.naam as categorie_naam
            FROM transacties t
            LEFT JOIN categorien c ON t.categorie_id = c.id
            WHERE t.jaar = ? AND t.maand = ? AND t.categorie_id = ?
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (jaar, maand, categorie_id))
        
    else:
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, 'Zonder categorie' as categorie_naam
            FROM transacties t
            WHERE t.jaar = ? AND t.maand = ? AND t.categorie_id IS NULL
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (jaar, maand))
        
        categorie_naam = 'Zonder categorie'
    
    transacties = cursor.fetchall()
    
    # Calculate statistics
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Month names for display
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    conn.close()
    
    # Format transactions for JSON
    transacties_formatted = []
    for t in transacties:
        transacties_formatted.append({
            'id': t[0],
            'datum': t[1],
            'naam': t[2],
            'bedrag': t[3],
            'bedrag_formatted': f"€{abs(t[3]):.2f}" if t[3] >= 0 else f"-€{abs(t[3]):.2f}",
            'code': t[4],
            'mededelingen': t[5] or '',
            'tegenrekening': t[6] or '',
            'categorie': t[7]
        })
    
    return jsonify({
        'transacties': transacties_formatted,
        'statistieken': {
            'aantal': len(transacties),
            'totaal': totaal_bedrag,
            'totaal_formatted': f"€{abs(totaal_bedrag):.2f}" if totaal_bedrag >= 0 else f"-€{abs(totaal_bedrag):.2f}",
            'uitgaven': uitgaven,
            'uitgaven_formatted': f"-€{abs(uitgaven):.2f}" if uitgaven < 0 else "€0,00",
            'inkomsten': inkomsten, 
            'inkomsten_formatted': f"€{inkomsten:.2f}",
            'gemiddeld': gemiddeld,
            'gemiddeld_formatted': f"€{abs(gemiddeld):.2f}" if gemiddeld >= 0 else f"-€{abs(gemiddeld):.2f}"
        },
        'context': {
            'jaar': jaar,
            'maand': maand,
            'maand_naam': maand_namen[maand],
            'categorie': categorie_naam,
            'categorie_id': categorie_id
        }
    })

@report_bp.route('/auto-categorisering')
def auto_categorisering():
    """Page for automatic categorization"""
    return render_template('auto_categorisering.html')

@report_bp.route('/categoriseer-analyse')
def categoriseer_analyse():
    """Analyze transaction names for automatic categorization with proper pattern matching"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all uncategorized transactions
    cursor.execute('''
        SELECT naam, COUNT(*) as aantal, 
               AVG(bedrag) as gemiddeld_bedrag,
               MIN(bedrag) as min_bedrag,
               MAX(bedrag) as max_bedrag
        FROM transacties 
        WHERE categorie_id IS NULL 
        GROUP BY naam 
        ORDER BY COUNT(*) DESC
    ''')
    
    naam_statistieken = cursor.fetchall()
    
    # Detect patterns for automatic categorization
    categoriseer_suggesties = []
    
    # Supermarket/Grocery patterns
    boodschappen_patronen = [
        'DEKAMARKT', 'ALBERT HEIJN', 'JUMBO', 'LIDL', 'ALDI', 'PLUS', 'COOP',
        'SPAR', 'VOMAR', 'DIRK', 'PICNIC', 'BONI'
    ]
    
    # Gas stations/Auto patterns  
    auto_patronen = [
        'SHELL', 'BP', 'ESSO', 'TEXACO', 'TOTAL', 'TANGO', 'GULF', 'Q8',
        'TINQ', 'FASTNED', 'ALLEGO'
    ]
    
    # Restaurant/Horeca patterns
    horeca_patronen = [
        'MCDONALDS', 'BURGER KING', 'KFC', 'SUBWAY', 'DOMINOS', 'NEW YORK PIZZA',
        'CAFE ', 'RESTAURANT', 'BISTRO', 'BRASSERIE'
    ]
    
    # Parking patterns
    parkeer_patronen = [
        'PARKEREN', 'Q-PARK', 'APCOA', 'EUROPARKING', 'P+R'
    ]
    
    def tel_matches(patronen, categorie_naam, suggested_category_id=None):
        totaal_transacties = 0
        totaal_bedrag = 0
        matched_namen = []
        
        for naam_data in naam_statistieken:
            naam, aantal, gem_bedrag, min_bedrag, max_bedrag = naam_data
            
            # Check if any pattern occurs in the name with Python regex
            for patroon in patronen:
                pattern = r'\b' + re.escape(patroon) + r'\b'
                
                if re.search(pattern, naam, re.IGNORECASE):
                    totaal_transacties += aantal
                    totaal_bedrag += gem_bedrag * aantal
                    matched_namen.append({
                        'naam': naam,
                        'aantal': aantal,
                        'gemiddeld': gem_bedrag
                    })
                    break
        
        if totaal_transacties > 0:
            categoriseer_suggesties.append({
                'categorie': categorie_naam,
                'suggested_category_id': suggested_category_id,
                'patronen': patronen,
                'totaal_transacties': totaal_transacties,
                'totaal_bedrag': totaal_bedrag,
                'matched_namen': matched_namen[:10],
                'voorbeelden': patronen[:3]
            })
    
    # Search for existing categories to link
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    categorien = dict(cursor.fetchall())
    
    # Try to match categories
    boodschappen_cat_id = None
    auto_cat_id = None
    horeca_cat_id = None
    
    for cat_id, cat_naam in categorien.items():
        if 'boodschap' in cat_naam.lower() or 'supermarkt' in cat_naam.lower():
            boodschappen_cat_id = cat_id
        elif 'auto' in cat_naam.lower() or 'benzine' in cat_naam.lower() or 'transport' in cat_naam.lower():
            auto_cat_id = cat_id
        elif 'restaurant' in cat_naam.lower() or 'eten' in cat_naam.lower() or 'horeca' in cat_naam.lower():
            horeca_cat_id = cat_id
    
    # Analyze patterns
    tel_matches(boodschappen_patronen, 'Boodschappen', boodschappen_cat_id)
    tel_matches(auto_patronen, 'Auto/Transport', auto_cat_id)  
    tel_matches(horeca_patronen, 'Restaurants/Eten', horeca_cat_id)
    tel_matches(parkeer_patronen, 'Parkeren', None)
    
    # Look for unique names with many transactions (potential new patterns)
    potentiele_patronen = []
    for naam_data in naam_statistieken[:20]:
        naam, aantal, gem_bedrag, min_bedrag, max_bedrag = naam_data
        if aantal >= 10:
            # Check if it's not already in a pattern
            already_matched = False
            for suggestie in categoriseer_suggesties:
                for matched in suggestie['matched_namen']:
                    if matched['naam'] == naam:
                        already_matched = True
                        break
                if already_matched:
                    break
            
            if not already_matched:
                potentiele_patronen.append({
                    'naam': naam,
                    'aantal': aantal,
                    'gemiddeld_bedrag': gem_bedrag
                })
    
    # General statistics
    cursor.execute('SELECT COUNT(*) FROM transacties WHERE categorie_id IS NULL')
    totaal_ongecategoriseerd = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM transacties WHERE categorie_id IS NOT NULL')
    totaal_gecategoriseerd = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'totaal_ongecategoriseerd': totaal_ongecategoriseerd,
        'totaal_gecategoriseerd': totaal_gecategoriseerd,
        'categoriseer_suggesties': categoriseer_suggesties,
        'potentiele_patronen': potentiele_patronen,
        'bestaande_categorien': categorien
    })

@report_bp.route('/auto-categoriseren', methods=['POST'])
def auto_categoriseren():
    """Perform automatic categorization with optional transaction IDs"""
    data = request.get_json()
    patronen = data.get('patronen', [])
    categorie_id = data.get('categorie_id')
    categorie_naam = data.get('categorie_naam')
    transactie_ids = data.get('transactie_ids', None)
    
    if not patronen or not categorie_id:
        return jsonify({'error': 'Patronen en categorie_id zijn verplicht'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if transactie_ids:
        # Use only selected transaction IDs
        placeholders = ','.join('?' * len(transactie_ids))
        update_query = f'''
            UPDATE transacties 
            SET categorie_id = ? 
            WHERE id IN ({placeholders}) AND categorie_id IS NULL
        '''
        cursor.execute(update_query, [categorie_id] + transactie_ids)
        aantal_te_updaten = cursor.rowcount
        
    else:
        # Old way: all transactions matching patterns
        cursor.execute('''
            SELECT id, naam FROM transacties 
            WHERE categorie_id IS NULL
        ''')
        
        alle_transacties = cursor.fetchall()
        te_updaten_ids = []
        
        # Filter transactions with Python regex
        for transactie_id, naam in alle_transacties:
            for patroon in patronen:
                pattern = r'\b' + re.escape(patroon) + r'\b'
                if re.search(pattern, naam, re.IGNORECASE):
                    te_updaten_ids.append(transactie_id)
                    break
        
        aantal_te_updaten = len(te_updaten_ids)
        
        if aantal_te_updaten > 0:
            placeholders = ','.join('?' * len(te_updaten_ids))
            update_query = f'''
                UPDATE transacties 
                SET categorie_id = ? 
                WHERE id IN ({placeholders})
            '''
            cursor.execute(update_query, [categorie_id] + te_updaten_ids)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'aantal_updated': aantal_te_updaten,
        'message': f'{aantal_te_updaten} transacties toegewezen aan "{categorie_naam}"'
    })

@report_bp.route('/preview-transacties', methods=['POST'])
def preview_transacties():
    """Get all transactions for a specific pattern set (for preview modal)"""
    data = request.get_json()
    patronen = data.get('patronen', [])
    
    if not patronen:
        return jsonify({'error': 'Patronen zijn verplicht'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get ALL uncategorized transactions
    cursor.execute('''
        SELECT id, datum, naam, bedrag, code, mededelingen
        FROM transacties 
        WHERE categorie_id IS NULL
        ORDER BY datum DESC
    ''')
    
    alle_transacties = cursor.fetchall()
    matched_transacties = []
    
    # Filter transactions with Python regex
    for transactie_data in alle_transacties:
        transactie_id, datum, naam, bedrag, code, mededelingen = transactie_data
        
        for patroon in patronen:
            # Regex pattern for whole words, case-insensitive
            pattern = r'\b' + re.escape(patroon) + r'\b'
            if re.search(pattern, naam, re.IGNORECASE):
                matched_transacties.append({
                    'id': transactie_id,
                    'datum': datum,
                    'naam': naam,
                    'bedrag': bedrag,
                    'bedrag_formatted': f"€{abs(bedrag):.2f}" if bedrag >= 0 else f"-€{abs(bedrag):.2f}",
                    'code': code,
                    'mededelingen': mededelingen or ''
                })
                break
    
    conn.close()
    
    # Sort by date (newest first)
    matched_transacties.sort(key=lambda x: x['datum'], reverse=True)
    
    return jsonify({
        'transacties': matched_transacties,
        'aantal': len(matched_transacties)
    })

@report_bp.route('/dashboard/maand-details')
def dashboard_maand_details():
    """API for transaction details of a specific month (for expenses chart drill-down)"""
    jaar = request.args.get('jaar', type=int)
    maand = request.args.get('maand', type=int)
    
    if not jaar or not maand:
        return jsonify({'error': 'Jaar en maand parameters zijn verplicht'}), 400
    
    if maand < 1 or maand > 12:
        return jsonify({'error': 'Maand moet tussen 1 en 12 zijn'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get all transactions for this month
    cursor.execute('''
        SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
               t.tegenrekening, c.naam as categorie_naam
        FROM transacties t
        LEFT JOIN categorien c ON t.categorie_id = c.id
        WHERE t.jaar = ? AND t.maand = ?
        ORDER BY t.datum DESC, t.bedrag DESC
    ''', (jaar, maand))
    
    transacties = cursor.fetchall()
    
    # Calculate statistics
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Month names for display
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    conn.close()
    
    # Format transactions for JSON
    transacties_formatted = []
    for t in transacties:
        transacties_formatted.append({
            'id': t[0],
            'datum': t[1],
            'naam': t[2],
            'bedrag': t[3],
            'bedrag_formatted': f"€{abs(t[3]):.2f}" if t[3] >= 0 else f"-€{abs(t[3]):.2f}",
            'code': t[4],
            'mededelingen': t[5] or '',
            'tegenrekening': t[6] or '',
            'categorie': t[7] or 'Zonder categorie'
        })
    
    return jsonify({
        'transacties': transacties_formatted,
        'statistieken': {
            'aantal': len(transacties),
            'totaal': totaal_bedrag,
            'totaal_formatted': f"€{abs(totaal_bedrag):.2f}" if totaal_bedrag >= 0 else f"-€{abs(totaal_bedrag):.2f}",
            'uitgaven': uitgaven,
            'uitgaven_formatted': f"-€{abs(uitgaven):.2f}" if uitgaven < 0 else "€0,00",
            'inkomsten': inkomsten, 
            'inkomsten_formatted': f"€{inkomsten:.2f}",
            'gemiddeld': gemiddeld,
            'gemiddeld_formatted': f"€{abs(gemiddeld):.2f}" if gemiddeld >= 0 else f"-€{abs(gemiddeld):.2f}"
        },
        'context': {
            'jaar': jaar,
            'maand': maand,
            'maand_naam': maand_namen[maand],
            'type': 'maand_overzicht'
        }
    })

@report_bp.route('/dashboard/categorie-details')
def dashboard_categorie_details():
    """API for transaction details of a specific category (for category chart drill-down)"""
    categorie_id_str = request.args.get('categorie_id')
    periode_maanden = request.args.get('periode', type=int, default=12)
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    # Validation
    if not categorie_id_str:
        return jsonify({'error': 'Categorie_id parameter is verplicht'}), 400
    
    # Convert categorie_id (can be null for "zonder categorie")
    categorie_id = None
    if categorie_id_str and categorie_id_str != 'null':
        try:
            categorie_id = int(categorie_id_str)
        except ValueError:
            return jsonify({'error': 'Ongeldige categorie_id'}), 400
    
    # Calculate period (last X months until eind_jaar/eind_maand)
    if not eind_jaar or not eind_maand:
        # Default: current month from data
        conn = sqlite3.connect('transacties.db')
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(jaar), MAX(maand) FROM transacties WHERE jaar = (SELECT MAX(jaar) FROM transacties)')
        result = cursor.fetchone()
        eind_jaar, eind_maand = result if result[0] else (datetime.now().year, datetime.now().month)
        conn.close()
    
    # Calculate start period
    if eind_maand > periode_maanden:
        start_jaar = eind_jaar
        start_maand = eind_maand - periode_maanden + 1
    else:
        start_jaar = eind_jaar - 1
        start_maand = eind_maand + 12 - periode_maanden + 1
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Get category info
    if categorie_id is not None:
        cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
        categorie_result = cursor.fetchone()
        if not categorie_result:
            conn.close()
            return jsonify({'error': f'Categorie {categorie_id} niet gevonden'}), 404
        categorie_naam = categorie_result[0]
    else:
        categorie_naam = 'Zonder categorie'
    
    # Build query for period
    if categorie_id is not None:
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, c.naam as categorie_naam
            FROM transacties t
            LEFT JOIN categorien c ON t.categorie_id = c.id
            WHERE t.categorie_id = ?
            AND ((t.jaar = ? AND t.maand >= ?) OR 
                 (t.jaar > ? AND t.jaar < ?) OR 
                 (t.jaar = ? AND t.maand <= ?))
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (categorie_id, start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    else:
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, 'Zonder categorie' as categorie_naam
            FROM transacties t
            WHERE t.categorie_id IS NULL
            AND ((t.jaar = ? AND t.maand >= ?) OR 
                 (t.jaar > ? AND t.jaar < ?) OR 
                 (t.jaar = ? AND t.maand <= ?))
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (start_jaar, start_maand, start_jaar, eind_jaar, eind_jaar, eind_maand))
    
    transacties = cursor.fetchall()
    
    # Calculate statistics
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Month names for period description
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    periode_beschrijving = f"{maand_namen[start_maand]} {start_jaar} - {maand_namen[eind_maand]} {eind_jaar}"
    
    conn.close()
    
    # Format transactions for JSON
    transacties_formatted = []
    for t in transacties:
        transacties_formatted.append({
            'id': t[0],
            'datum': t[1],
            'naam': t[2],
            'bedrag': t[3],
            'bedrag_formatted': f"€{abs(t[3]):.2f}" if t[3] >= 0 else f"-€{abs(t[3]):.2f}",
            'code': t[4],
            'mededelingen': t[5] or '',
            'tegenrekening': t[6] or '',
            'categorie': t[7]
        })
    
    return jsonify({
        'transacties': transacties_formatted,
        'statistieken': {
            'aantal': len(transacties),
            'totaal': totaal_bedrag,
            'totaal_formatted': f"€{abs(totaal_bedrag):.2f}" if totaal_bedrag >= 0 else f"-€{abs(totaal_bedrag):.2f}",
            'uitgaven': uitgaven,
            'uitgaven_formatted': f"-€{abs(uitgaven):.2f}" if uitgaven < 0 else "€0,00",
            'inkomsten': inkomsten, 
            'inkomsten_formatted': f"€{inkomsten:.2f}",
            'gemiddeld': gemiddeld,
            'gemiddeld_formatted': f"€{abs(gemiddeld):.2f}" if gemiddeld >= 0 else f"-€{abs(gemiddeld):.2f}"
        },
        'context': {
            'categorie_id': categorie_id,
            'categorie_naam': categorie_naam,
            'periode': periode_beschrijving,
            'periode_maanden': periode_maanden,
            'type': 'categorie_overzicht'
        }
    })