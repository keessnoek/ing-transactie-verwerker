"""
Database initialization and configuration
==========================================
Clean separation of database concerns
"""

import sqlite3

def init_database():
    """Initialize database and create tables if they don't exist"""
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
    
    # Indexes voor performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_datum ON transacties(datum)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_categorie ON transacties(categorie_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hash ON transacties(hash)')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection - helper function"""
    return sqlite3.connect('transacties.db')