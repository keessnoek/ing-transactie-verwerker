"""
Transaction Hash Generation Service
===================================
Responsible for generating unique transaction hashes for duplicate detection
"""

import hashlib

def generate_transaction_hash(jaar, maand, dag, naam, bedrag, code, mededelingen, tegenrekening, saldo_na_mutatie):
    """
    Generate a unique hash for a transaction including saldo na mutatie
    
    This ensures that split transactions (same transaction data but different ending balance)
    are treated as separate transactions, as discovered during Kees' testing.
    
    Args:
        jaar (int): Transaction year
        maand (int): Transaction month  
        dag (int): Transaction day
        naam (str): Transaction name/description
        bedrag (float): Transaction amount
        code (str): Transaction code
        mededelingen (str): Transaction details/remarks
        tegenrekening (str): Counter account
        saldo_na_mutatie (float): Balance after transaction
        
    Returns:
        str: SHA256 hash of transaction data
    """
    # Convert amount to string with fixed precision
    bedrag_str = f"{bedrag:.2f}"
    
    # Create string from all relevant fields including balance
    hash_components = [
        f"{jaar:04d}{maand:02d}{dag:02d}",  # Date as YYYYMMDD
        naam.strip() if naam else '',
        bedrag_str,
        code.strip() if code else '',
        mededelingen.strip() if mededelingen else '',
        tegenrekening.strip() if tegenrekening else '',
        f"{saldo_na_mutatie:.2f}"  # Include balance - this was the missing piece!
    ]
    
    # Join with unique separator
    hash_string = '||'.join(hash_components)
    
    # Generate SHA256 hash
    return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()