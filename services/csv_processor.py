"""
CSV Processing Service
======================
Handles ING CSV file processing and transaction import
"""

import csv
import io
import sqlite3
from .hash_generator import generate_transaction_hash

def process_ing_csv(file_path):
    """
    Process an ING CSV file and import transactions
    
    Args:
        file_path (str): Path to the CSV file
        
    Returns:
        dict: Processing results with counts and errors
    """
    conn = sqlite3.connect('transacties.db')
    cursor = conn.cursor()
    
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            # Skip BOM if present
            content = csvfile.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            
            reader = csv.DictReader(io.StringIO(content), delimiter=';')
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Parse datum from YYYYMMDD format
                    datum_str = row['Datum']
                    jaar = int(datum_str[:4])
                    maand = int(datum_str[4:6])
                    dag = int(datum_str[6:8])
                    datum = f"{jaar}-{maand:02d}-{dag:02d}"
                    
                    # Extract transaction details
                    naam = row['Naam / Omschrijving']
                    rekening = row['Rekening']
                    tegenrekening = row.get('Tegenrekening', '')
                    code = row['Code']
                    mededelingen = row.get('Mededelingen', '')
                    
                    # Process amount - convert comma to dot and handle Af/Bij logic
                    bedrag_str = row['Bedrag (EUR)'].replace(',', '.')
                    bedrag = float(bedrag_str)
                    
                    if row['Af Bij'] == 'Af':
                        bedrag = -bedrag
                    
                    # Process balance after transaction
                    saldo_str = row['Saldo na mutatie'].replace(',', '.')
                    saldo_na_mutatie = float(saldo_str)
                    
                    # Generate hash for duplicate checking
                    transaction_hash = generate_transaction_hash(
                        jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening, saldo_na_mutatie
                    )
                    
                    # Check if transaction already exists
                    cursor.execute('SELECT id FROM transacties WHERE hash = ?', (transaction_hash,))
                    if cursor.fetchone():
                        duplicate_count += 1
                        continue
                    
                    # Insert transaction
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