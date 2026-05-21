"""
Data import script to load Excel data from AWS S3 into PostgreSQL database
"""
import sys
import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
from io import BytesIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import Dealer, BacklinkDirectory, Citation
from aws_storage import S3Storage


def import_backlink_directories():
    """Import backlink directories from S3"""
    print("Importing backlink directories from S3...")
    
    storage = S3Storage()
    
    # Read directly from S3
    df = storage.read_excel('data/Backlink_Directories.xlsx', sheet_name='Backlink Directories')
    
    if df is None:
        print("Error: Could not read Backlink_Directories.xlsx from S3!")
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
        print(f"✓ Imported {count} backlink directories from S3")
        return True
        
        
    except Exception as e:
        print(f"✗ Error importing directories: {str(e)}")
        db.session.rollback()
        return False


def import_dealers_and_citations():
    """Import dealers and their citation history from S3 Excel file"""
    print("Importing dealers and citations from S3...")
    
    storage = S3Storage()
    
    # Read directly from S3
    df = storage.read_excel('data/Cafe_Clients_Backlinks.xlsx', sheet_name='Cafe Backlinks')
    
    if df is None:
        print("Error: Could not read Cafe_Clients_Backlinks.xlsx from S3!")
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
            
            # Check if dealer exists
            existing_dealer = Dealer.query.filter_by(id=dealer_id).first()
            if not existing_dealer:
                dealer = Dealer(
                    id=dealer_id,
                    name=str(dealer_name),
                    contact_info=None
                )
                db.session.add(dealer)
                dealers_imported += 1
            else:
                dealer = existing_dealer
            
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
                    created_date = datetime.utcnow() - timedelta(days=int((row_idx - 2) * 10))
                    
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
        
        print(f"✓ Imported {dealers_imported} new dealers from S3 (Total: {total_dealers})")
        print(f"✓ Imported {citations_imported} new citations from S3 (Total: {total_citations})")
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
