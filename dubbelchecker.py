import csv
import hashlib
import io

def generate_transaction_hash(jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening):
    """Verbeterde hash functie - meer robuust voor subtiele verschillen"""
    # Converteer bedrag naar string met vaste precisie
    bedrag_str = f"{bedrag:.2f}"
    
    # Maak een string van alle relevante velden
    hash_components = [
        f"{jaar:04d}{maand:02d}{dag:02d}",  # Datum als YYYYMMDD
        naam.strip() if naam else '',
        bedrag_str,
        code.strip() if code else '',
        mededelingen.strip() if mededelingen else '',  # Behoud originele tekst
        tegenrekening.strip() if tegenrekening else ''
    ]
    
    # Join met unieke separator
    hash_string = '||'.join(hash_components)
    
    # Geen aggressive normalization
    return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()

def find_duplicates_in_csv(csv_file_path):
    """Vind alle duplicaten in een CSV bestand"""
    seen_hashes = {}
    duplicates = []
    
    with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
        # Skip BOM if present
        content = csvfile.read()
        if content.startswith('\ufeff'):
            content = content[1:]
        
        reader = csv.DictReader(io.StringIO(content), delimiter=';')
        
        for row_num, row in enumerate(reader, 1):
            try:
                # Parse datum
                datum_str = row['Datum']
                jaar = int(datum_str[:4])
                maand = int(datum_str[4:6])
                dag = int(datum_str[6:8])
                
                # Get transaction details
                naam = row['Naam / Omschrijving']
                rekening = row['Rekening']
                tegenrekening = row.get('Tegenrekening', '')
                code = row['Code']
                mededelingen = row.get('Mededelingen', '')
                
                # Process amount
                bedrag_str = row['Bedrag (EUR)'].replace(',', '.')
                bedrag = float(bedrag_str)
                if row['Af Bij'] == 'Af':
                    bedrag = -bedrag
                
                # Generate hash
                transaction_hash = generate_transaction_hash(
                    jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening
                )
                
                # Check for duplicates
                if transaction_hash in seen_hashes:
                    duplicates.append({
                        'current_row': row_num,
                        'original_row': seen_hashes[transaction_hash],
                        'datum': f"{jaar}-{maand:02d}-{dag:02d}",
                        'naam': naam,
                        'mededelingen': mededelingen,
                        'bedrag': bedrag,
                        'hash': transaction_hash
                    })
                else:
                    seen_hashes[transaction_hash] = row_num
                    
            except Exception as e:
                print(f"Fout bij regel {row_num}: {e}")
                continue
    
    return duplicates

# Main execution
if __name__ == "__main__":
    csv_file = "test.csv"  # Pas aan naar jouw bestandsnaam
    
    print("🔍 Zoeken naar duplicaten in CSV...")
    duplicates = find_duplicates_in_csv(csv_file)
    
    if duplicates:
        print(f"\n📋 Gevonden duplicaten: {len(duplicates)}")
        print("-" * 80)
        
        for dup in duplicates:
            print(f"Regel {dup['current_row']:4d} is duplicaat van regel {dup['original_row']:4d}")
            print(f"     Datum: {dup['datum']}")
            print(f"     Naam:  {dup['naam'][:250]}...")
            print(f"     Bedrag:€{dup['bedrag']:8.2f}")
            print(f"     Mededelingen: {dup['mededelingen']}")
            print(f"     Hash:  {dup['hash']}")
            print()
    else:
        print("\n✅ Geen duplicaten gevonden!")