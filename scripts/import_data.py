"""
Data import script to load Excel data from local Excel files into PostgreSQL database.
"""
import sys
import pandas as pd
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import Dealer, BacklinkDirectory, Citation

DATA_DIR = PROJECT_ROOT / 'Data'


def read_local_excel(file_name, sheet_name=None):
    """Read an Excel file from the local Data directory."""
    file_path = DATA_DIR / file_name
    if not file_path.exists():
        print(f"✗ Error: {file_name} not found in {DATA_DIR}")
        return None

    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print(f"✓ Read {file_path}")
        return df
    except Exception as exc:
        print(f"✗ Error reading {file_path}: {exc}")
        return None


def import_backlink_directories():
    """Import backlink directories from the local Excel file."""
    print("Importing backlink directories from local Data/...")

    df = read_local_excel('Backlink_Directories.xlsx', sheet_name='Backlink Directories')
    
    if df is None:
        print("Error: Could not read Backlink_Directories.xlsx from Data/!")
        return False
    
    try:
        for idx, row in df.iterrows():
            if pd.isna(row.get('Directory Name')) or pd.isna(row.get('Directory Link')):
                continue
            
            # Check if already exists
            existing = BacklinkDirectory.query.filter_by(name=row['Directory Name']).first()
            if existing:
                continue
            
            directory = BacklinkDirectory(
                name=row['Directory Name'],
                url=row['Directory Link'],
                active=True
            )
            db.session.add(directory)
        
        db.session.commit()
        count = BacklinkDirectory.query.count()
        print(f"✓ Imported {count} backlink directories from local Data/")
        return True
        
        
    except Exception as e:
        print(f"✗ Error importing directories: {str(e)}")
        db.session.rollback()
        return False


def import_dealers_and_citations():
    """Import dealers and their citation history from the local Excel file."""
    print("Importing dealers and citations from local Data/...")

    df = read_local_excel('Cafe_Clients_Backlinks.xlsx', sheet_name='Cafe Backlinks')
    
    if df is None:
        print("Error: Could not read Cafe_Clients_Backlinks.xlsx from Data/!")
        return False
    
    try:
        # First row contains dealer IDs, second contains names, rest are citations
        dealer_ids = df.iloc[0].values
        dealer_names = df.iloc[1].values
        
        # Import dealers (skip NaN values)
        dealers_imported = 0
        citations_imported = 0
        
        for col_idx, dealer_id in enumerate(dealer_ids):
            if pd.isna(dealer_id):
                continue
            
            dealer_id = str(int(dealer_id)) if isinstance(dealer_id, float) else str(dealer_id)
            dealer_name = dealer_names[col_idx]
            
            if pd.isna(dealer_name):
                dealer_name = f"Dealer {dealer_id}"

            dealer_name = str(dealer_name).strip()

            if not dealer_name or dealer_name.lower() == 'nan':
                dealer_name = dealer_id

            if Dealer.query.filter_by(name=dealer_name).first() and not Dealer.query.filter_by(id=dealer_id).first():
                dealer_name = dealer_id
            
            # Check if dealer exists
            existing_dealer = Dealer.query.filter_by(id=dealer_id).first()
            if not existing_dealer:
                existing_dealer = Dealer.query.filter_by(name=dealer_name).first()

            if existing_dealer:
                dealer = existing_dealer
            else:
                dealer = Dealer(
                    id=dealer_id,
                    name=dealer_name,
                    contact_info=None
                )
                db.session.add(dealer)
                dealers_imported += 1
            
            db.session.flush()  # Flush to get the dealer in the session
            
            # Import citations for this dealer (from row 2 onwards)
            for row_idx in range(2, len(df)):
                citation_name = df.iloc[row_idx, col_idx]
                
                if pd.isna(citation_name) or citation_name == '':
                    continue
                
                citation_name = str(citation_name).strip()
                
                # Find the directory
                directory = BacklinkDirectory.query.filter_by(name=citation_name).first()
                if not directory:
                    # Skip if directory not found
                    print(f"  Warning: Directory '{citation_name}' not found for dealer {dealer_id}")
                    continue
                
                # Check if citation already exists
                existing_citation = Citation.query.filter_by(
                    dealer_id=dealer_id,
                    directory_id=directory.id
                ).first()
                
                if not existing_citation:
                    # Create citation with a date offset (to simulate past citations)
                    # Assign random dates within last 6 months for demo purposes
                    created_date = datetime.now(timezone.utc) - timedelta(days=int((row_idx - 2) * 10))
                    
                    citation = Citation(
                        dealer_id=dealer_id,
                        directory_id=directory.id,
                        created_at=created_date
                    )
                    db.session.add(citation)
                    citations_imported += 1
        
        db.session.commit()
        
        total_dealers = Dealer.query.count()
        total_citations = Citation.query.count()
        
        print(f"✓ Imported {dealers_imported} new dealers from local Data/ (Total: {total_dealers})")
        print(f"✓ Imported {citations_imported} new citations from local Data/ (Total: {total_citations})")
        return True
        
    except Exception as e:
        print(f"✗ Error importing dealers/citations: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False


def main():
    """Main import function"""
    print("=" * 60)
    print("Citation Building Management System - Data Import")
    print("=" * 60)
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Create tables
        print("\nInitializing database...")
        db.create_all()
        print("✓ Database tables created")
        
        # Import data
        print("\n" + "-" * 60)
        if import_backlink_directories():
            import_dealers_and_citations()
        
        print("-" * 60)
        print("\n✓ Data import completed successfully!")
        
        # Print summary
        dealers = Dealer.query.count()
        directories = BacklinkDirectory.query.count()
        citations = Citation.query.count()
        
        print(f"\nDatabase Summary:")
        print(f"  • Dealers: {dealers}")
        print(f"  • Backlink Directories: {directories}")
        print(f"  • Citations Built: {citations}")
        print("=" * 60)


if __name__ == '__main__':
    main()
