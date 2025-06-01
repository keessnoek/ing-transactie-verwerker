from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import csv
import hashlib
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import io

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

@app.route('/transacties')
def transacties():
    """Toon alle transacties in een tabel met categorieën - nu met backend zoeken"""
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Haal zoekterm op uit URL parameters
    zoekterm = request.args.get('zoek', '').strip()
    
    # Bouw SQL query met optionele WHERE clause
    base_query = '''
        SELECT t.id, t.datum, t.naam, t.bedrag, t.code, t.mededelingen, 
               t.tegenrekening, t.saldo_na_mutatie, c.naam as categorie_naam, c.id as categorie_id
        FROM transacties t
        LEFT JOIN categorien c ON t.categorie_id = c.id
    '''
    
    if zoekterm:
        # Zoek in alle relevante velden
        where_clause = '''
            WHERE (t.datum LIKE ? OR 
                   t.naam LIKE ? OR 
                   t.bedrag LIKE ? OR 
                   t.code LIKE ? OR 
                   t.mededelingen LIKE ? OR 
                   t.tegenrekening LIKE ? OR
                   c.naam LIKE ?)
        '''
        
        # Voeg wildcards toe aan zoekterm
        search_pattern = f'%{zoekterm}%'
        search_params = [search_pattern] * 7  # Voor elke LIKE clause
        
        full_query = base_query + where_clause + ' ORDER BY t.datum DESC, t.id DESC LIMIT 1000'
        cursor.execute(full_query, search_params)
    else:
        # Geen zoekterm - toon gewoon de laatste 1000
        full_query = base_query + ' ORDER BY t.datum DESC, t.id DESC LIMIT 1000'
        cursor.execute(full_query)
    
    transacties_data = cursor.fetchall()
    
    # Haal alle beschikbare categorieën op voor de dropdown
    cursor.execute('SELECT id, naam FROM categorien ORDER BY naam')
    alle_categorien = cursor.fetchall()
    
    # Tel totaal aantal resultaten voor de melding
    if zoekterm:
        cursor.execute('''
            SELECT COUNT(*) FROM transacties t
            LEFT JOIN categorien c ON t.categorie_id = c.id
            WHERE (t.datum LIKE ? OR 
                   t.naam LIKE ? OR 
                   t.bedrag LIKE ? OR 
                   t.code LIKE ? OR 
                   t.mededelingen LIKE ? OR 
                   t.tegenrekening LIKE ? OR
                   c.naam LIKE ?)
        ''', search_params)
        totaal_resultaten = cursor.fetchone()[0]
    else:
        cursor.execute('SELECT COUNT(*) FROM transacties')
        totaal_resultaten = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('transacties.html', 
                         transacties=transacties_data,
                         alle_categorien=alle_categorien,
                         zoekterm=zoekterm,
                         totaal_resultaten=totaal_resultaten,
                         getoond_resultaten=len(transacties_data))


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
    """Vind transacties die lijken op deze categorie voor bulk-toewijzing"""
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
        placeholders = ','.join('?' * len(bestaande_namen))
        cursor.execute(f'''
            SELECT DISTINCT t.id, t.datum, t.naam, t.bedrag
            FROM transacties t
            WHERE t.categorie_id IS NULL 
            AND (t.naam IN ({placeholders}) OR {' OR '.join(['t.naam LIKE ?' for _ in bestaande_namen])})
            ORDER BY t.datum DESC
            LIMIT 50
        ''', bestaande_namen + [f'%{naam.split()[0]}%' for naam in bestaande_namen])
        
        suggesties = cursor.fetchall()
        
        # Detecteer winkel-patronen voor bulk-opties
        for naam in bestaande_namen:
            # Probeer winkelnaam te extraheren (eerste woord vaak, of bekende patronen)
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
            
            # Tel hoeveel ongecategoriseerde transacties er zijn per winkel
            for winkel in winkel_kandidaten:
                if winkel not in winkel_patronen:
                    cursor.execute('''
                        SELECT COUNT(*) FROM transacties 
                        WHERE categorie_id IS NULL 
                        AND (naam LIKE ? OR naam LIKE ?)
                    ''', (f'%{winkel}%', f'{winkel.upper()}%'))
                    aantal = cursor.fetchone()[0]
                    
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
    """Analyseer transactienamen voor automatische categorisering"""
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
    
    # Parkeren patronen (vaak cijfers/codes)
    parkeer_patronen = [
        'PARKEREN', 'Q-PARK', 'APCOA', 'EUROPARKING', 'P+R'
    ]
    
    # Tel matches voor elke categorie
    def tel_matches(patronen, categorie_naam, suggested_category_id=None):
        totaal_transacties = 0
        totaal_bedrag = 0
        matched_namen = []
        
        for naam_data in naam_statistieken:
            naam, aantal, gem_bedrag, min_bedrag, max_bedrag = naam_data
            
            # Check of een van de patronen in de naam voorkomt
            for patroon in patronen:
                if patroon.upper() in naam.upper():
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
    
    # Analyseer patronen
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
    """Voer automatische categorisering uit op basis van patronen"""
    data = request.get_json()
    patronen = data.get('patronen', [])
    categorie_id = data.get('categorie_id')
    categorie_naam = data.get('categorie_naam')
    
    if not patronen or not categorie_id:
        return jsonify({'error': 'Patronen en categorie_id zijn verplicht'}), 400
    
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    # Bouw WHERE clause voor de patronen
    where_conditions = []
    params = []
    
    for patroon in patronen:
        where_conditions.append('naam LIKE ?')
        params.append(f'%{patroon}%')
    
    where_clause = ' OR '.join(where_conditions)
    
    # Tel eerst hoeveel transacties geraakt worden
    count_query = f'''
        SELECT COUNT(*) FROM transacties 
        WHERE categorie_id IS NULL AND ({where_clause})
    '''
    cursor.execute(count_query, params)
    aantal_te_updaten = cursor.fetchone()[0]
    
    if aantal_te_updaten == 0:
        return jsonify({'aantal_updated': 0, 'message': 'Geen transacties gevonden voor deze patronen'})
    
    # Voer de update uit
    update_query = f'''
        UPDATE transacties 
        SET categorie_id = ? 
        WHERE categorie_id IS NULL AND ({where_clause})
    '''
    cursor.execute(update_query, [categorie_id] + params)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'aantal_updated': aantal_te_updaten,
        'message': f'{aantal_te_updaten} transacties toegewezen aan "{categorie_naam}"'
    })

# Voeg deze route toe aan je ing_transactieverwerker.py

@app.route('/auto-categorisering')
def auto_categorisering():
    """Pagina voor automatische categorisering"""
    return render_template('auto_categorisering.html')

if __name__ == '__main__':
    init_database()
    app.run(debug=True)