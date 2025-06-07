from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import csv
import hashlib
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import io
import re

# Test 2

app = Flask(__name__)
app.secret_key = 'jouw_geheime_sleutel_hier'  # Verander dit naar iets veiligs!
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max bestandsgrootte

# Zorg dat de upload folder bestaat
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_database():
    """Maak de database en tabellen aan als ze nog niet bestaan"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Tabel voor categorieën
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorien (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naam TEXT UNIQUE NOT NULL,
            beschrijving TEXT,
            kleur TEXT DEFAULT '#3498db'
        )
    ''')
    
    # Tabel voor transacties
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datum DATE NOT NULL,
            jaar INTEGER NOT NULL,
            maand INTEGER NOT NULL,
            dag INTEGER NOT NULL,
            naam TEXT NOT NULL,
            rekening TEXT NOT NULL,
            tegenrekening TEXT,
            code TEXT NOT NULL,
            bedrag REAL NOT NULL,
            mededelingen TEXT,
            saldo_na_mutatie REAL,
            tag TEXT,
            categorie_id INTEGER,
            hash TEXT UNIQUE NOT NULL,
            FOREIGN KEY (categorie_id) REFERENCES categorien (id)
        )
    ''')
    
    # Index voor snellere queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_datum ON transacties(datum)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_categorie ON transacties(categorie_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hash ON transacties(hash)')
    
    conn.commit()
    conn.close()

def generate_transaction_hash(jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening, saldo_na_mutatie):
    """Genereer een unieke hash voor een transactie - nu inclusief saldo na mutatie"""
    # Maak een string van alle relevante velden (inclusief saldo!)
    hash_string = f"{jaar}-{maand:02d}-{dag:02d}|{naam}|{bedrag}|{code}|{mededelingen or ''}|{tegenrekening or ''}|{saldo_na_mutatie}"
    # Normaliseer: lowercase en strip spaties
    hash_string = hash_string.lower().strip()
    # Genereer SHA256 hash
    return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()


# En natuurlijk moet je de functie-aanroep ook updaten in process_ing_csv:
def process_ing_csv(file_path):
    """Verwerk een ING CSV bestand en importeer transacties"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            # ING CSV heeft vaak een BOM, dus we skippen die
            content = csvfile.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            
            reader = csv.DictReader(io.StringIO(content), delimiter=';')  # Puntkomma als delimiter!
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Parse datum van JJJJMMDD naar aparte velden
                    datum_str = row['Datum']
                    jaar = int(datum_str[:4])
                    maand = int(datum_str[4:6])
                    dag = int(datum_str[6:8])
                    datum = f"{jaar}-{maand:02d}-{dag:02d}"
                    
                    # Kolommen herbenoemen en ophalen
                    naam = row['Naam / Omschrijving']
                    rekening = row['Rekening']
                    tegenrekening = row.get('Tegenrekening', '')
                    code = row['Code']
                    mededelingen = row.get('Mededelingen', '')
                    
                    # Bedrag verwerken - van komma naar punt en Af/Bij logica
                    bedrag_str = row['Bedrag (EUR)'].replace(',', '.')
                    bedrag = float(bedrag_str)
                    
                    if row['Af Bij'] == 'Af':
                        bedrag = -bedrag
                    
                    # Saldo na mutatie - dit was de missing piece!
                    saldo_str = row['Saldo na mutatie'].replace(',', '.')
                    saldo_na_mutatie = float(saldo_str)
                    
                    # Genereer hash voor duplicate checking - NU MET SALDO!
                    transaction_hash = generate_transaction_hash(
                        jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening, saldo_na_mutatie
                    )
                    
                    # Check of transactie al bestaat
                    cursor.execute('SELECT id FROM transacties WHERE hash = ?', (transaction_hash,))
                    if cursor.fetchone():
                        duplicate_count += 1
                        continue
                    
                    # Voeg transactie toe
                    cursor.execute('''
                        INSERT INTO transacties 
                        (datum, jaar, maand, dag, naam, rekening, tegenrekening, code, 
                         bedrag, mededelingen, saldo_na_mutatie, hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (datum, jaar, maand, dag, naam, rekening, tegenrekening, code,
                          bedrag, mededelingen, saldo_na_mutatie, transaction_hash))
                    
                    imported_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"Regel {row_num}: {str(e)}")
                    continue
        
        conn.commit()
        
    except Exception as e:
        errors.append(f"Algemene fout: {str(e)}")
        error_count += 1
    
    finally:
        conn.close()
    
    return {
        'imported': imported_count,
        'duplicates': duplicate_count,
        'errors': error_count,
        'error_details': errors
    }

@app.route('/')
def index():
    """Hoofdpagina met navigatie"""
    return render_template('index.html')

@app.route('/importeren', methods=['GET', 'POST'])
def importeren():
    """Upload en verwerk ING CSV bestanden"""
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
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Verwerk het CSV bestand
            result = process_ing_csv(filepath)
            
            # Toon resultaten
            if result['imported'] > 0:
                flash(f"Succesvol {result['imported']} transacties geïmporteerd!", 'success')
            if result['duplicates'] > 0:
                flash(f"{result['duplicates']} duplicaten overgeslagen", 'info')
            if result['errors'] > 0:
                flash(f"{result['errors']} fouten opgetreden", 'warning')
                for error in result['error_details'][:5]:  # Toon maximaal 5 foutmeldingen
                    flash(error, 'error')
            
            # Verwijder tijdelijk bestand
            os.remove(filepath)
            
        else:
            flash('Alleen CSV bestanden zijn toegestaan', 'error')
    
    # Haal meest recente datum op uit database
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(datum) FROM transacties')
    laatste_datum = cursor.fetchone()[0]
    conn.close()
    
    return render_template('importeren.html', laatste_datum=laatste_datum)
# Vervang de /transacties route in je ing_transactieverwerker.py met deze versie:

# Vervang je huidige /transacties route in ing_transactieverwerker.py met deze versie:

@app.route('/transacties')
def transacties():
    """Toon alle transacties in een tabel met categorieën - nu met server-side sorting en zoeken"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal parameters op uit URL
    zoekterm = request.args.get('zoek', '').strip()
    sort_column = request.args.get('sort', 'datum')  # Default: datum
    sort_order = request.args.get('order', 'desc')   # Default: desc (nieuwste eerst)
    
    # Valideer sort parameters voor security
    valid_columns = {
        'datum': 't.datum',
        'naam': 't.naam', 
        'bedrag': 't.bedrag',
        'code': 't.code',
        'categorie': 'c.naam'
    }
    
    valid_orders = ['asc', 'desc']
    
    # Gebruik defaults als parameters invalid zijn
    if sort_column not in valid_columns:
        sort_column = 'datum'
    if sort_order not in valid_orders:
        sort_order = 'desc'
    
    # Bouw SQL query
    base_query = '''
        SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
               t.tegenrekening, t.saldo_na_mutatie, c.naam as categorie_naam, c.id as categorie_id
        FROM transacties t
        LEFT JOIN categorien c ON t.categorie_id = c.id
    '''
    
    # WHERE clause voor zoeken
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
    
    # Speciale behandeling voor categorie (NULL values onderaan)
    if sort_column == 'categorie':
        if sort_order == 'asc':
            order_clause = f' ORDER BY {sql_column} IS NULL, {sql_column} ASC, t.datum DESC'
        else:
            order_clause = f' ORDER BY {sql_column} IS NULL, {sql_column} DESC, t.datum DESC'
    else:
        # Voor andere kolommen: secundaire sort op datum (nieuwste eerst)
        if sort_column == 'datum':
            order_clause = f' ORDER BY {sql_column} {sort_order.upper()}, t.id {sort_order.upper()}'
        else:
            order_clause = f' ORDER BY {sql_column} {sort_order.upper()}, t.datum DESC'
    
    # Volledige query met limit
    full_query = base_query + order_clause + ' LIMIT 1000'
    
    cursor.execute(full_query, params)
    transacties_data = cursor.fetchall()
    
    # Haal alle categorieën op voor dropdown
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    alle_categorien = cursor.fetchall()
    
    # Tel totaal aantal resultaten
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


@app.route('/categorien')
def categorien():
    """Toon alle categorieën met aantal transacties per categorie"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal alle categorieën op met aantal transacties
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
    
    # Tel ook hoeveel transacties nog geen categorie hebben
    cursor.execute('SELECT COUNT(*) FROM transacties WHERE categorie_id IS NULL')
    zonder_categorie = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('categorien.html', 
                         categorien=categorien_data, 
                         zonder_categorie=zonder_categorie)

@app.route('/categorien/nieuw', methods=['POST'])
def nieuwe_categorie():
    """Voeg een nieuwe categorie toe"""
    naam = request.form.get('naam', '').strip()
    beschrijving = request.form.get('beschrijving', '').strip()
    kleur = request.form.get('kleur', '#3498db')
    
    if not naam:
        flash('Categorienaam is verplicht', 'error')
        return redirect(url_for('categorien'))
    
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
    
    return redirect(url_for('categorien'))

@app.route('/categorien/<int:categorie_id>/bewerken', methods=['POST'])
def bewerk_categorie(categorie_id):
    """Bewerk een bestaande categorie"""
    naam = request.form.get('naam', '').strip()
    beschrijving = request.form.get('beschrijving', '').strip()
    kleur = request.form.get('kleur', '#3498db')
    
    if not naam:
        flash('Categorienaam is verplicht', 'error')
        return redirect(url_for('categorien'))
    
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
    
    return redirect(url_for('categorien'))

@app.route('/categorien/<int:categorie_id>/verwijderen', methods=['POST'])
def verwijder_categorie(categorie_id):
    """Verwijder een categorie (transacties worden niet verwijderd)"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal eerst de naam op voor de melding
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie = cursor.fetchone()
    
    if not categorie:
        flash('Categorie niet gevonden', 'error')
        conn.close()
        return redirect(url_for('categorien'))
    
    naam = categorie[0]
    
    # Zet alle transacties van deze categorie terug naar NULL
    cursor.execute('UPDATE transacties SET categorie_id = NULL WHERE categorie_id = ?', (categorie_id,))
    
    # Verwijder de categorie
    cursor.execute('DELETE FROM categorien WHERE id = ?', (categorie_id,))
    
    conn.commit()
    conn.close()
    
    flash(f'Categorie "{naam}" verwijderd. Transacties zijn behouden maar hebben geen categorie meer.', 'info')
    return redirect(url_for('categorien'))


@app.route('/categorien/bulk-toewijzen', methods=['POST'])
def bulk_toewijzen():
    """Wijs meerdere transacties tegelijk toe aan een categorie"""
    categorie_id = request.form.get('categorie_id')
    transactie_ids = request.form.getlist('transactie_ids')
    
    if not categorie_id or not transactie_ids:
        flash('Geen categorie of transacties geselecteerd', 'error')
        return redirect(url_for('categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Update alle geselecteerde transacties
    placeholders = ','.join('?' * len(transactie_ids))
    cursor.execute(f'''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE id IN ({placeholders})
    ''', [categorie_id] + transactie_ids)
    
    conn.commit()
    conn.close()
    
    flash(f'{len(transactie_ids)} transacties toegewezen aan categorie!', 'success')
    return redirect(url_for('categorien'))

@app.route('/transacties/update-categorie', methods=['POST'])
def update_transactie_categorie():
    """Update de categorie van een transactie"""
    transactie_id = request.form.get('transactie_id')
    categorie_id = request.form.get('categorie_id')
    
    # Lege string naar None converteren voor database
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
    
    return '', 204  # No content response voor AJAX calls



@app.route('/categorien/bulk-winkel', methods=['POST'])
def bulk_winkel_toewijzen():
    """Wijs alle transacties van een specifieke winkel toe aan een categorie"""
    categorie_id = request.form.get('categorie_id')
    winkel_naam = request.form.get('winkel_naam')
    
    if not categorie_id or not winkel_naam:
        flash('Categorie of winkelnaam ontbreekt', 'error')
        return redirect(url_for('categorien'))
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Zoek alle transacties van deze winkel zonder categorie
    cursor.execute('''
        SELECT COUNT(*) FROM transacties 
        WHERE categorie_id IS NULL 
        AND (naam LIKE ? OR naam LIKE ?)
    ''', (f'%{winkel_naam}%', f'{winkel_naam.upper()}%'))
    
    aantal = cursor.fetchone()[0]
    
    if aantal == 0:
        flash(f'Geen ongecategoriseerde {winkel_naam} transacties gevonden', 'info')
        conn.close()
        return redirect(url_for('categorien'))
    
    # Update alle transacties van deze winkel
    cursor.execute('''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE categorie_id IS NULL 
        AND (naam LIKE ? OR naam LIKE ?)
    ''', (categorie_id, f'%{winkel_naam}%', f'{winkel_naam.upper()}%'))
    
    conn.commit()
    conn.close()
    
    # Haal categorienaam op voor melding
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie_naam = cursor.fetchone()[0]
    conn.close()
    
    flash(f'{aantal} {winkel_naam} transacties toegewezen aan "{categorie_naam}"!', 'success')
    return redirect(url_for('categorien'))

# Update ook de bestaande categorie_suggesties route om winkel-patronen te detecteren:

@app.route('/categorien/suggesties/<int:categorie_id>')
def categorie_suggesties(categorie_id):
    """Vind transacties die lijken op deze categorie voor bulk-toewijzing - NU MET GEFIXTE PATTERN MATCHING"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal de categorie info op
    cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
    categorie = cursor.fetchone()
    
    if not categorie:
        flash('Categorie niet gevonden', 'error')
        return redirect(url_for('categorien'))
    
    # Haal alle transacties van deze categorie op om patronen te vinden
    cursor.execute('''
        SELECT DISTINCT naam 
        FROM transacties 
        WHERE categorie_id = ? 
        LIMIT 20
    ''', (categorie_id,))
    
    bestaande_namen = [row[0] for row in cursor.fetchall()]
    
    # Zoek vergelijkbare transacties zonder categorie
    suggesties = []
    winkel_patronen = {}  # Voor bulk-opties
    
    if bestaande_namen:
        # Haal ALLE ongecategoriseerde transacties op en filter met Python regex
        cursor.execute('''
            SELECT DISTINCT t.id, t.datum, t.naam, t.bedrag
            FROM transacties t
            WHERE t.categorie_id IS NULL 
            ORDER BY t.datum DESC
        ''')
        
        alle_ongecategoriseerd = cursor.fetchall()
        
        # Filter met Python regex voor exacte matches
        for transactie_id, datum, naam, bedrag in alle_ongecategoriseerd:
            matched = False
            
            # Check exacte matches
            for bestaande_naam in bestaande_namen:
                if naam == bestaande_naam:
                    suggesties.append((transactie_id, datum, naam, bedrag))
                    matched = True
                    break
            
            # Check partial matches met hele woorden
            if not matched:
                for bestaande_naam in bestaande_namen:
                    # Probeer eerste woord van bestaande naam als pattern
                    eerste_woord = bestaande_naam.split()[0] if bestaande_naam.split() else bestaande_naam
                    if len(eerste_woord) > 3:  # Alleen als het woord lang genoeg is
                        pattern = r'\b' + re.escape(eerste_woord) + r'\b'
                        if re.search(pattern, naam, re.IGNORECASE):
                            suggesties.append((transactie_id, datum, naam, bedrag))
                            break
        
        # Limiteer suggesties tot 50
        suggesties = suggesties[:50]
        
        # Detecteer winkel-patronen voor bulk-opties - NU OOK MET REGEX
        for naam in bestaande_namen:
            winkel_kandidaten = []
            
            # Bekende supermarkt patronen
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
                # Fallback: eerste woord
                eerste_woord = naam.split()[0] if naam.split() else naam
                if len(eerste_woord) > 3:  # Alleen als het woord lang genoeg is
                    winkel_kandidaten.append(eerste_woord)
            
            # Tel hoeveel ongecategoriseerde transacties er zijn per winkel - NU MET REGEX
            for winkel in winkel_kandidaten:
                if winkel not in winkel_patronen:
                    # Haal alle ongecategoriseerde transacties op en filter met Python
                    cursor.execute('''
                        SELECT naam FROM transacties 
                        WHERE categorie_id IS NULL
                    ''')
                    alle_namen = [row[0] for row in cursor.fetchall()]
                    
                    # Tel matches met regex
                    pattern = r'\b' + re.escape(winkel) + r'\b'
                    aantal = sum(1 for n in alle_namen if re.search(pattern, n, re.IGNORECASE))
                    
                    if aantal >= 5:  # Alleen tonen als er minstens 5 transacties zijn
                        winkel_patronen[winkel] = aantal
    
    conn.close()
    
    return render_template('categorie_suggesties.html', 
                         categorie=categorie[0], 
                         categorie_id=categorie_id,
                         suggesties=suggesties,
                         winkel_patronen=winkel_patronen)

# Voeg deze routes toe aan je ing_transactieverwerker.py

@app.route('/rapportages')
def rapportages():
    """Hoofdpagina voor rapportages met kruistabel"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal beschikbare jaren op
    cursor.execute('SELECT DISTINCT jaar FROM transacties ORDER BY jaar DESC')
    jaren = [row[0] for row in cursor.fetchall()]
    
    # Haal het meest recente jaar als default
    huidig_jaar = request.args.get('jaar', str(jaren[0]) if jaren else str(datetime.now().year))
    
    conn.close()
    
    return render_template('rapportages.html', jaren=jaren, huidig_jaar=int(huidig_jaar))
# Vervang je bestaande /rapportages/kruistabel route met deze versie:

@app.route('/rapportages/kruistabel')
def kruistabel_data():
    """API endpoint voor kruistabel data - nu met categorie IDs!"""
    jaar = request.args.get('jaar', type=int)
    
    if not jaar:
        return jsonify({'error': 'Jaar parameter ontbreekt'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal alle categorieën op
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    categorien = cursor.fetchall()
    
    # Bouw de kruistabel data
    kruistabel_data = {}
    categorie_ids = {}  # Nieuwe mapping van naam naar ID
    maand_totalen = {i: 0 for i in range(1, 13)}  # Totalen per maand
    categorie_totalen = {}  # Totalen per categorie
    
    # Voor elke categorie, haal bedragen per maand op
    for cat_id, cat_naam in categorien:
        cursor.execute('''
            SELECT maand, SUM(bedrag) 
            FROM transacties 
            WHERE categorie_id = ? AND jaar = ? 
            GROUP BY maand
        ''', (cat_id, jaar))
        
        maand_bedragen = dict(cursor.fetchall())
        kruistabel_data[cat_naam] = {}
        categorie_ids[cat_naam] = cat_id  # Sla ID op!
        categorie_totaal = 0
        
        for maand in range(1, 13):
            bedrag = maand_bedragen.get(maand, 0)
            kruistabel_data[cat_naam][maand] = bedrag
            maand_totalen[maand] += bedrag
            categorie_totaal += bedrag
        
        categorie_totalen[cat_naam] = categorie_totaal
    
    # Ook transacties zonder categorie
    cursor.execute('''
        SELECT maand, SUM(bedrag) 
        FROM transacties 
        WHERE categorie_id IS NULL AND jaar = ? 
        GROUP BY maand
    ''', (jaar,))
    
    maand_bedragen = dict(cursor.fetchall())
    kruistabel_data['Zonder categorie'] = {}
    categorie_ids['Zonder categorie'] = None  # Expliciet None voor zonder categorie
    zonder_categorie_totaal = 0
    
    for maand in range(1, 13):
        bedrag = maand_bedragen.get(maand, 0)
        kruistabel_data['Zonder categorie'][maand] = bedrag
        maand_totalen[maand] += bedrag
        zonder_categorie_totaal += bedrag
    
    categorie_totalen['Zonder categorie'] = zonder_categorie_totaal
    
    # Bereken grand total
    grand_total = sum(maand_totalen.values())
    
    conn.close()
    
    return jsonify({
        'data': kruistabel_data,
        'categorie_ids': categorie_ids,  # NIEUWE data voor frontend!
        'maand_totalen': maand_totalen,
        'categorie_totalen': categorie_totalen,
        'grand_total': grand_total,
        'jaar': jaar
    })

# Vervang je /rapportages/transactie-details route met deze versie:
# Dit is de originele debug-versie maar dan met de juiste JSON output!

@app.route('/rapportages/transactie-details')
def transactie_details():
    """DEBUG versie - laat alles zien maar met juiste JSON"""
    jaar = request.args.get('jaar', type=int)
    maand = request.args.get('maand', type=int)
    categorie_id_str = request.args.get('categorie_id')
    
    # DEBUG: Print alle parameters
    print(f"DEBUG - Ontvangen parameters:")
    print(f"  jaar: {jaar} (type: {type(jaar)})")
    print(f"  maand: {maand} (type: {type(maand)})")
    print(f"  categorie_id_str: '{categorie_id_str}' (type: {type(categorie_id_str)})")
    
    # Validatie
    if not jaar or not maand:
        return jsonify({'error': 'Jaar en maand parameters zijn verplicht'}), 400
    
    if maand < 1 or maand > 12:
        return jsonify({'error': 'Maand moet tussen 1 en 12 zijn'}), 400
    
    # Converteer categorie_id
    categorie_id = None
    if categorie_id_str and categorie_id_str != 'null':
        try:
            categorie_id = int(categorie_id_str)
            print(f"DEBUG - Geconverteerde categorie_id: {categorie_id} (type: {type(categorie_id)})")
        except ValueError:
            print(f"DEBUG - FOUT bij converteren van categorie_id: '{categorie_id_str}'")
            return jsonify({'error': 'Ongeldige categorie_id'}), 400
    else:
        print(f"DEBUG - categorie_id blijft None (zonder categorie)")
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # DEBUG: Kijk welke categorieën er überhaupt bestaan
    cursor.execute('SELECT id, naam FROM categorien ORDER BY id')
    alle_categorien = cursor.fetchall()
    print(f"DEBUG - Alle categorieën in database:")
    for cat in alle_categorien:
        print(f"  ID {cat[0]}: {cat[1]}")
    
    # Bouw query op basis van categorie
    if categorie_id is not None:
        print(f"DEBUG - Zoeken naar transacties met categorie_id = {categorie_id}")
        
        # TEST: Kijk eerst of de categorie bestaat
        cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
        categorie_check = cursor.fetchone()
        if categorie_check:
            print(f"DEBUG - Categorie {categorie_id} bestaat: {categorie_check[0]}")
            categorie_naam = categorie_check[0]
        else:
            print(f"DEBUG - PROBLEEM: Categorie {categorie_id} bestaat NIET in database!")
            return jsonify({'error': f'Categorie {categorie_id} niet gevonden'}), 404
        
        # TEST: Kijk hoeveel transacties er zijn voor dit jaar/maand
        cursor.execute('SELECT COUNT(*) FROM transacties WHERE jaar = ? AND maand = ?', (jaar, maand))
        totaal_count = cursor.fetchone()[0]
        print(f"DEBUG - Totaal transacties voor {jaar}-{maand}: {totaal_count}")
        
        # TEST: Kijk hoeveel transacties er zijn voor deze categorie in dit jaar/maand
        cursor.execute('SELECT COUNT(*) FROM transacties WHERE jaar = ? AND maand = ? AND categorie_id = ?', 
                      (jaar, maand, categorie_id))
        categorie_count = cursor.fetchone()[0]
        print(f"DEBUG - Transacties voor categorie {categorie_id} in {jaar}-{maand}: {categorie_count}")
        
        # Als er geen transacties zijn, probeer zonder jaar/maand filter
        if categorie_count == 0:
            cursor.execute('SELECT COUNT(*) FROM transacties WHERE categorie_id = ?', (categorie_id,))
            categorie_totaal = cursor.fetchone()[0]
            print(f"DEBUG - Totaal transacties voor categorie {categorie_id} (alle jaren/maanden): {categorie_totaal}")
        
        # Hoofdquery - EXACTE KOPIE VAN ORIGINELE DEBUG
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, c.naam as categorie_naam
            FROM transacties t
            LEFT JOIN categorien c ON t.categorie_id = c.id
            WHERE t.jaar = ? AND t.maand = ? AND t.categorie_id = ?
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (jaar, maand, categorie_id))
        
    else:
        print(f"DEBUG - Zoeken naar transacties ZONDER categorie")
        
        # TEST: Kijk hoeveel transacties er zijn zonder categorie
        cursor.execute('SELECT COUNT(*) FROM transacties WHERE jaar = ? AND maand = ? AND categorie_id IS NULL', 
                      (jaar, maand))
        zonder_count = cursor.fetchone()[0]
        print(f"DEBUG - Transacties zonder categorie in {jaar}-{maand}: {zonder_count}")
        
        cursor.execute('''
            SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
                   t.tegenrekening, 'Zonder categorie' as categorie_naam
            FROM transacties t
            WHERE t.jaar = ? AND t.maand = ? AND t.categorie_id IS NULL
            ORDER BY t.datum DESC, t.bedrag DESC
        ''', (jaar, maand))
        
        categorie_naam = 'Zonder categorie'
    
    transacties = cursor.fetchall()
    print(f"DEBUG - Gevonden transacties: {len(transacties)}")
    
    # Toon eerste paar transacties als voorbeeld
    if transacties:
        print(f"DEBUG - Eerste transactie: {transacties[0]}")
    
    # Bereken statistieken
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Maandnamen voor mooiere weergave
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    conn.close()
    
    # Format transacties voor JSON - NU MET JUISTE STRUCTURE!
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


# Voeg deze routes toe aan je ing_transactieverwerker.py

@app.route('/rapportages/categoriseer-analyse')
def categoriseer_analyse():
    """Analyseer transactienamen voor automatische categorisering - NU MET JUISTE PATTERN MATCHING"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal alle ongecategoriseerde transacties op
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
    
    # Detecteer patronen voor automatische categorisering
    categoriseer_suggesties = []
    
    # Supermarkten/Boodschappen patronen
    boodschappen_patronen = [
        'DEKAMARKT', 'ALBERT HEIJN', 'JUMBO', 'LIDL', 'ALDI', 'PLUS', 'COOP',
        'SPAR', 'VOMAR', 'DIRK', 'PICNIC', 'BONI'
    ]
    
    # Benzinestations/Auto patronen  
    auto_patronen = [
        'SHELL', 'BP', 'ESSO', 'TEXACO', 'TOTAL', 'TANGO', 'GULF', 'Q8',
        'TINQ', 'FASTNED', 'ALLEGO'
    ]
    
    # Restaurants/Horeca patronen
    horeca_patronen = [
        'MCDONALDS', 'BURGER KING', 'KFC', 'SUBWAY', 'DOMINOS', 'NEW YORK PIZZA',
        'CAFE ', 'RESTAURANT', 'BISTRO', 'BRASSERIE'
    ]
    
    # Parkeren patronen
    parkeer_patronen = [
        'PARKEREN', 'Q-PARK', 'APCOA', 'EUROPARKING', 'P+R'
    ]
    
    # GEFIXTE tel_matches functie met Python regex
    def tel_matches(patronen, categorie_naam, suggested_category_id=None):
        totaal_transacties = 0
        totaal_bedrag = 0
        matched_namen = []
        
        for naam_data in naam_statistieken:
            naam, aantal, gem_bedrag, min_bedrag, max_bedrag = naam_data
            
            # Check of een van de patronen in de naam voorkomt - NU MET PYTHON REGEX!
            for patroon in patronen:
                # Regex pattern voor hele woorden, case-insensitive
                pattern = r'\b' + re.escape(patroon) + r'\b'
                
                if re.search(pattern, naam, re.IGNORECASE):
                    totaal_transacties += aantal
                    totaal_bedrag += gem_bedrag * aantal
                    matched_namen.append({
                        'naam': naam,
                        'aantal': aantal,
                        'gemiddeld': gem_bedrag
                    })
                    break  # Stop bij eerste match
        
        if totaal_transacties > 0:
            categoriseer_suggesties.append({
                'categorie': categorie_naam,
                'suggested_category_id': suggested_category_id,
                'patronen': patronen,
                'totaal_transacties': totaal_transacties,
                'totaal_bedrag': totaal_bedrag,
                'matched_namen': matched_namen[:10],  # Top 10 voor weergave
                'voorbeelden': patronen[:3]  # Eerste 3 patronen als voorbeeld
            })
    
    # Zoek naar bestaande categorieën om te koppelen
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    categorien = dict(cursor.fetchall())
    
    # Probeer categorieën te matchen
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
    
    # Analyseer patronen - NU MET GEFIXTE FUNCTIE
    tel_matches(boodschappen_patronen, 'Boodschappen', boodschappen_cat_id)
    tel_matches(auto_patronen, 'Auto/Transport', auto_cat_id)  
    tel_matches(horeca_patronen, 'Restaurants/Eten', horeca_cat_id)
    tel_matches(parkeer_patronen, 'Parkeren', None)
    
    # Zoek ook naar unieke namen met veel transacties (potentiële nieuwe patronen)
    potentiele_patronen = []
    for naam_data in naam_statistieken[:20]:  # Top 20 namen
        naam, aantal, gem_bedrag, min_bedrag, max_bedrag = naam_data
        if aantal >= 10:  # Minimaal 10 transacties
            # Check of het niet al in een patroon zit
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
    
    # Algemene statistieken
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



@app.route('/rapportages/auto-categoriseren', methods=['POST'])
def auto_categoriseren():
    """Voer automatische categorisering uit - NU MET OPTIONELE TRANSACTIE-IDS"""
    data = request.get_json()
    patronen = data.get('patronen', [])
    categorie_id = data.get('categorie_id')
    categorie_naam = data.get('categorie_naam')
    transactie_ids = data.get('transactie_ids', None)  # Optioneel: specifieke IDs
    
    if not patronen or not categorie_id:
        return jsonify({'error': 'Patronen en categorie_id zijn verplicht'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if transactie_ids:
        # Gebruik alleen de geselecteerde transactie IDs
        placeholders = ','.join('?' * len(transactie_ids))
        update_query = f'''
            UPDATE transacties 
            SET categorie_id = ? 
            WHERE id IN ({placeholders}) AND categorie_id IS NULL
        '''
        cursor.execute(update_query, [categorie_id] + transactie_ids)
        aantal_te_updaten = cursor.rowcount
        
    else:
        # Oude manier: alle transacties die matchen met patronen
        cursor.execute('''
            SELECT id, naam FROM transacties 
            WHERE categorie_id IS NULL
        ''')
        
        alle_transacties = cursor.fetchall()
        te_updaten_ids = []
        
        # Filter transacties met Python regex
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

@app.route('/auto-categorisering')
def auto_categorisering():
    """Pagina voor automatische categorisering"""
    return render_template('auto_categorisering.html')


@app.route('/rapportages/preview-transacties', methods=['POST'])
def preview_transacties():
    """Haal alle transacties op voor een specifieke patroon-set (voor preview modal)"""
    data = request.get_json()
    patronen = data.get('patronen', [])
    
    if not patronen:
        return jsonify({'error': 'Patronen zijn verplicht'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal ALLE ongecategoriseerde transacties op
    cursor.execute('''
        SELECT id, datum, naam, bedrag, code, mededelingen
        FROM transacties 
        WHERE categorie_id IS NULL
        ORDER BY datum DESC
    ''')
    
    alle_transacties = cursor.fetchall()
    matched_transacties = []
    
    # Filter transacties met Python regex
    for transactie_data in alle_transacties:
        transactie_id, datum, naam, bedrag, code, mededelingen = transactie_data
        
        for patroon in patronen:
            # Regex pattern voor hele woorden, case-insensitive
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
                break  # Stop bij eerste match
    
    conn.close()
    
    # Sorteer op datum (nieuwste eerst)
    matched_transacties.sort(key=lambda x: x['datum'], reverse=True)
    
    return jsonify({
        'transacties': matched_transacties,
        'aantal': len(matched_transacties)
    })

@app.route('/dashboard')
def dashboard():
    """Dashboard met grafische weergaven van transacties"""
    # Haal beschikbare jaren en maanden op voor dropdowns
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal alle beschikbare jaar/maand combinaties op
    cursor.execute('''
        SELECT DISTINCT jaar, maand 
        FROM transacties 
        ORDER BY jaar DESC, maand DESC
    ''')
    
    beschikbare_periodes = cursor.fetchall()
    
    # Haal unieke jaren op
    jaren = sorted(list(set([periode[0] for periode in beschikbare_periodes])), reverse=True)
    
    # Default: huidige maand/jaar of laatste beschikbare
    if beschikbare_periodes:
        default_jaar = beschikbare_periodes[0][0]  # Meest recente jaar
        default_maand = beschikbare_periodes[0][1]  # Meest recente maand
    else:
        default_jaar = datetime.now().year
        default_maand = datetime.now().month
    
    conn.close()
    
    return render_template('dashboard.html', 
                         jaren=jaren,
                         default_jaar=default_jaar,
                         default_maand=default_maand)

@app.route('/dashboard/uitgaven-per-maand')
def dashboard_uitgaven_per_maand():
    """API voor uitgaven per maand - nu met datum selectie"""
    # Haal parameters op (default = laatste 12 maanden)
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if eind_jaar and eind_maand:
        # Bereken start datum (12 maanden terug)
        if eind_maand == 12:
            # December: start in januari van hetzelfde jaar
            start_jaar = eind_jaar
            start_maand = 1
        else:
            # Andere maanden: start in volgende maand van vorig jaar
            start_jaar = eind_jaar - 1
            start_maand = eind_maand + 1
        
        # Haal data op voor specifieke periode
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
        # Default: laatste 12 maanden
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
    
    # Converteer naar Chart.js formaat
    maanden = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
    
    labels = []
    bedragen = []
    
    # Voor specifieke periode: chronologische volgorde
    # Voor default: reverse voor chronologische volgorde
    data_sorted = data if (eind_jaar and eind_maand) else reversed(data)
    
    for jaar, maand, totaal in data_sorted:
        labels.append(f"{maanden[maand-1]} {jaar}")
        bedragen.append(abs(totaal))
    
    return jsonify({
        'labels': labels,
        'data': bedragen
    })

@app.route('/dashboard/top-categorien')
def dashboard_top_categorien():
    """API voor top uitgaven categorieën - nu met categorie IDs voor drill-down"""
    eind_jaar = request.args.get('jaar', type=int) or datetime.now().year
    eind_maand = request.args.get('maand', type=int) or datetime.now().month
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Bereken periode (12 maanden)
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
    
    # Ook transacties zonder categorie voor deze periode
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
    categorie_ids = []  # NIEUWE ARRAY voor IDs
    
    for cat_id, naam, kleur, totaal in data:
        labels.append(naam)
        bedragen.append(abs(totaal))
        kleuren.append(kleur)
        categorie_ids.append(cat_id)  # Voeg ID toe
    
    if abs(zonder_categorie) > 50:
        labels.append('Zonder categorie')
        bedragen.append(abs(zonder_categorie))
        kleuren.append('#6c757d')
        categorie_ids.append(None)  # null voor zonder categorie
    
    return jsonify({
        'labels': labels,
        'data': bedragen,
        'colors': kleuren,
        'categorie_ids': categorie_ids  # NIEUWE DATA
    })

@app.route('/dashboard/inkomsten-uitgaven')
def dashboard_inkomsten_uitgaven():
    """API voor inkomsten vs uitgaven - nu met datum selectie"""
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    if eind_jaar and eind_maand:
        # Laatste 6 maanden van gekozen periode
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
        # Default: laatste 6 maanden
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
    
    # Voor specifieke periode: al gesorteerd
    # Voor default: reverse
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

@app.route('/dashboard/statistieken')
def dashboard_statistieken():
    """API voor algemene statistieken - nu met datum selectie"""
    eind_jaar = request.args.get('jaar', type=int) or datetime.now().year
    eind_maand = request.args.get('maand', type=int) or datetime.now().month
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Bereken periode (12 maanden)
    if eind_maand == 12:
        start_jaar = eind_jaar
        start_maand = 1
    else:
        start_jaar = eind_jaar - 1
        start_maand = eind_maand + 1
    
    # Totalen voor geselecteerde periode
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
    
    # Aantal categorieën (totaal, niet periode-specifiek)
    cursor.execute('SELECT COUNT(*) FROM categorien')
    aantal_categorien = cursor.fetchone()[0]
    
    # Zonder categorie voor deze periode
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
    netto = totaal_inkomsten + totaal_uitgaven  # uitgaven zijn negatief
    
    # Bepaal periode label
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

@app.route('/dashboard/maand-details')
def dashboard_maand_details():
    """API voor transactie details van een specifieke maand (voor uitgaven chart drill-down)"""
    jaar = request.args.get('jaar', type=int)
    maand = request.args.get('maand', type=int)
    
    if not jaar or not maand:
        return jsonify({'error': 'Jaar en maand parameters zijn verplicht'}), 400
    
    if maand < 1 or maand > 12:
        return jsonify({'error': 'Maand moet tussen 1 en 12 zijn'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal alle transacties voor deze maand op
    cursor.execute('''
        SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
               t.tegenrekening, c.naam as categorie_naam
        FROM transacties t
        LEFT JOIN categorien c ON t.categorie_id = c.id
        WHERE t.jaar = ? AND t.maand = ?
        ORDER BY t.datum DESC, t.bedrag DESC
    ''', (jaar, maand))
    
    transacties = cursor.fetchall()
    
    # Bereken statistieken
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Maandnamen voor mooiere weergave
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    conn.close()
    
    # Format transacties voor JSON
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


@app.route('/dashboard/categorie-details')
def dashboard_categorie_details():
    """API voor transactie details van een specifieke categorie (voor categorie chart drill-down)"""
    categorie_id_str = request.args.get('categorie_id')
    periode_maanden = request.args.get('periode', type=int, default=12)  # Default 12 maanden
    eind_jaar = request.args.get('jaar', type=int)
    eind_maand = request.args.get('maand', type=int)
    
    # Validatie
    if not categorie_id_str:
        return jsonify({'error': 'Categorie_id parameter is verplicht'}), 400
    
    # Converteer categorie_id (kan null zijn voor "zonder categorie")
    categorie_id = None
    if categorie_id_str and categorie_id_str != 'null':
        try:
            categorie_id = int(categorie_id_str)
        except ValueError:
            return jsonify({'error': 'Ongeldige categorie_id'}), 400
    
    # Bereken periode (laatste X maanden tot aan eind_jaar/eind_maand)
    if not eind_jaar or not eind_maand:
        # Default: huidige maand uit de data
        conn = sqlite3.connect('transacties.db')
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(jaar), MAX(maand) FROM transacties WHERE jaar = (SELECT MAX(jaar) FROM transacties)')
        result = cursor.fetchone()
        eind_jaar, eind_maand = result if result[0] else (datetime.now().year, datetime.now().month)
        conn.close()
    
    # Bereken start periode
    if eind_maand > periode_maanden:
        start_jaar = eind_jaar
        start_maand = eind_maand - periode_maanden + 1
    else:
        start_jaar = eind_jaar - 1
        start_maand = eind_maand + 12 - periode_maanden + 1
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal categorie info op
    if categorie_id is not None:
        cursor.execute('SELECT naam FROM categorien WHERE id = ?', (categorie_id,))
        categorie_result = cursor.fetchone()
        if not categorie_result:
            conn.close()
            return jsonify({'error': f'Categorie {categorie_id} niet gevonden'}), 404
        categorie_naam = categorie_result[0]
    else:
        categorie_naam = 'Zonder categorie'
    
    # Bouw query voor periode
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
    
    # Bereken statistieken
    if transacties:
        bedragen = [t[3] for t in transacties]
        totaal_bedrag = sum(bedragen)
        uitgaven = sum(b for b in bedragen if b < 0)
        inkomsten = sum(b for b in bedragen if b > 0)
        gemiddeld = totaal_bedrag / len(bedragen)
    else:
        totaal_bedrag = uitgaven = inkomsten = gemiddeld = 0
    
    # Maandnamen voor periode beschrijving
    maand_namen = [
        '', 'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
        'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
    ]
    
    periode_beschrijving = f"{maand_namen[start_maand]} {start_jaar} - {maand_namen[eind_maand]} {eind_jaar}"
    
    conn.close()
    
    # Format transacties voor JSON
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

if __name__ == '__main__':
    init_database()
    app.run(debug=True)