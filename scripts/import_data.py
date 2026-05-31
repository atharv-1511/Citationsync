"""
Data import script to load the updated dealer and backlink Excel workbooks into PostgreSQL.
"""
import sys
import pandas as pd
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import Dealer, BacklinkDirectory, Citation, ActivityLog
from sqlalchemy import text

DATA_DIR = PROJECT_ROOT / 'Acutal Data'
DIRECTORY_FILE = 'Backlink_Directory_UPDATED.xlsx'
DEALER_FILE = 'Atharv_s_Clients-_Backlink_Records_FINAL.xlsx'


def clear_existing_data():
    """Remove existing dealer, citation, and activity rows before a full dealer refresh."""
    print("Clearing existing dealer/citation/activity rows...")
    db.session.query(Citation).delete(synchronize_session=False)
    db.session.query(ActivityLog).delete(synchronize_session=False)
    db.session.query(Dealer).delete(synchronize_session=False)
    db.session.query(BacklinkDirectory).delete(synchronize_session=False)
    db.session.commit()
    print("✓ Existing data cleared")


def read_local_excel(file_name, sheet_name=None, **read_kwargs):
    """Read an Excel file from the local Data directory."""
    file_path = DATA_DIR / file_name
    if not file_path.exists():
        print(f"✗ Error: {file_name} not found in {DATA_DIR}")
        return None

    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, **read_kwargs)
        print(f"✓ Read {file_path}")
        return df
    except Exception as exc:
        print(f"✗ Error reading {file_path}: {exc}")
        return None


def build_placeholder_directory_url(name):
    """Create a stable placeholder URL for directories that only exist in the dealer workbook."""
    slug = re.sub(r'[^a-z0-9]+', '-', str(name).strip().lower()).strip('-')
    if not slug:
        slug = 'directory'
    return f'https://{slug}.example'


def guess_website_in_column(df, col_idx):
    """Heuristically find a website/URL for a dealer in the first few rows of the column."""
    max_search_rows = min(10, len(df))
    for row_idx in range(2, max_search_rows):
        try:
            val = df.iloc[row_idx, col_idx]
        except Exception:
            continue
        if pd.isna(val):
            continue
        s = str(val).strip()
        if not s:
            continue
        # crude URL detection: contains protocol or a host-like token (contains a dot, no spaces)
        if re.search(r'https?://', s, flags=re.I) or ('.' in s and ' ' not in s):
            if not re.search(r'https?://', s, flags=re.I):
                s = 'https://' + s.lstrip('/')
            return s
    return None


def sync_backlink_directories():
    """Sync backlink directories from the updated workbook and mark missing rows as removed."""
    print("Syncing backlink directories from the updated workbook...")

    df = read_local_excel(DIRECTORY_FILE, sheet_name='Sheet1', header=None)
    
    if df is None:
        print(f"Error: Could not read {DIRECTORY_FILE} from {DATA_DIR}!")
        return False
    
    try:
        existing_directories = {
            directory.name: directory
            for directory in BacklinkDirectory.query.all()
        }
        imported_names = set()

        for idx, row in df.iterrows():
            if idx == 0:
                continue
            directory_name = row.iloc[0]
            directory_url = row.iloc[1] if len(row) > 1 else None

            if pd.isna(directory_name) or pd.isna(directory_url):
                continue

            directory_name = str(directory_name).strip()
            directory_url = str(directory_url).strip()
            imported_names.add(directory_name)

            existing_directory = existing_directories.get(directory_name)
            if existing_directory:
                existing_directory.url = directory_url
                existing_directory.active = True
                continue

            directory = BacklinkDirectory(
                name=directory_name,
                url=directory_url,
                active=True
            )
            db.session.add(directory)

        for directory_name, directory in existing_directories.items():
            if directory_name not in imported_names:
                directory.active = False
        
        db.session.commit()
        active_count = BacklinkDirectory.query.filter_by(active=True).count()
        removed_count = BacklinkDirectory.query.filter_by(active=False).count()
        print(f"✓ Synced backlink directories from the updated workbook")
        print(f"  • Active directories: {active_count}")
        print(f"  • Removed directories: {removed_count}")
        return True
        
        
    except Exception as e:
        print(f"✗ Error importing directories: {str(e)}")
        db.session.rollback()
        return False


def import_dealers_and_citations():
    """Import dealers and their citation history from the local Excel file."""
    print("Importing dealers and citations from the updated workbook...")

    df = read_local_excel(DEALER_FILE, sheet_name='Sheet1', header=None)
    
    if df is None:
        print(f"Error: Could not read {DEALER_FILE} from {DATA_DIR}!")
        return False
    
    try:
        # First row contains dealer IDs. Some workbooks have websites in row 1 and names in row 2.
        dealer_ids = df.iloc[0].values

        # Heuristic: check if row 1 looks like websites (many values containing 'http' or a dot)
        def row_looks_like_urls(row):
            tokens = 0
            total = 0
            for v in row:
                total += 1
                try:
                    s = str(v).strip()
                except Exception:
                    continue
                if not s or s.lower() == 'nan':
                    continue
                if re.search(r'https?://', s, flags=re.I) or ('.' in s and ' ' not in s):
                    tokens += 1
            return tokens >= max(3, int(total * 0.5))

        website_row_idx = None
        names_row_idx = 1
        if len(df) > 1 and row_looks_like_urls(df.iloc[1].values):
            website_row_idx = 1
            names_row_idx = 2 if len(df) > 2 else 1

        citation_start_row = 3 if website_row_idx is not None else 2

        dealer_names = df.iloc[names_row_idx].values

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

            # Do not replace dealer name with the ID or website — keep the provided name.
            
            # Check if dealer exists
            existing_dealer = Dealer.query.filter_by(id=dealer_id).first()
            if not existing_dealer:
                existing_dealer = Dealer.query.filter_by(name=dealer_name).first()

            if existing_dealer:
                dealer = existing_dealer
            else:
                # Try to detect a website/url for this dealer from the workbook rows
                detected_website = None
                # Prefer explicit website row if present
                if website_row_idx is not None:
                    try:
                        raw = df.iloc[website_row_idx, col_idx]
                        if not pd.isna(raw) and str(raw).strip():
                            s = str(raw).strip()
                            if not re.search(r'https?://', s, flags=re.I):
                                s = 'https://' + s.lstrip('/')
                            detected_website = s
                    except Exception:
                        detected_website = None

                if not detected_website:
                    detected_website = guess_website_in_column(df, col_idx)

                dealer = db.session.merge(Dealer(
                    id=dealer_id,
                    name=dealer_name,
                    contact_info=detected_website
                ))
                dealers_imported += 1
            # If dealer exists already, prefer to populate contact_info if missing
            if existing_dealer and not existing_dealer.contact_info:
                # Populate missing contact_info from explicit website row or heuristic
                detected_website = None
                if website_row_idx is not None:
                    try:
                        raw = df.iloc[website_row_idx, col_idx]
                        if not pd.isna(raw) and str(raw).strip():
                            s = str(raw).strip()
                            if not re.search(r'https?://', s, flags=re.I):
                                s = 'https://' + s.lstrip('/')
                            detected_website = s
                    except Exception:
                        detected_website = None
                if not detected_website:
                    detected_website = guess_website_in_column(df, col_idx)
                if detected_website:
                    existing_dealer.contact_info = detected_website
                    db.session.add(existing_dealer)

            if dealers_imported % 10 == 0 or col_idx % 10 == 0:
                print(f"  Processing dealer column {col_idx + 1}/{len(dealer_ids)}: {dealer_id}")

            try:
                db.session.flush()  # Flush to get the dealer in the session

                # Import citations for this dealer (skip the website/name rows)
                for row_idx in range(citation_start_row, len(df)):
                    citation_name = df.iloc[row_idx, col_idx]
                    if pd.isna(citation_name) or citation_name == '':
                        continue
                    citation_name = str(citation_name).strip()

                    # Find the directory
                    directory = BacklinkDirectory.query.filter_by(name=citation_name).first()
                    if not directory:
                        # Auto-create missing directories so dealer records are preserved.
                        directory = BacklinkDirectory(
                            name=citation_name,
                            url=build_placeholder_directory_url(citation_name),
                            active=True,
                        )
                        db.session.add(directory)
                        db.session.flush()
                        print(f"  Created missing directory '{citation_name}' for dealer {dealer_id}")
                    elif not directory.active:
                        directory.active = True

                    # Check if citation already exists
                    existing_citation = Citation.query.filter_by(
                        dealer_id=dealer_id,
                        directory_id=directory.id
                    ).first()

                    if not existing_citation:
                        # Create citation with a date offset (to simulate past citations)
                        created_date = datetime.now(timezone.utc) - timedelta(days=int((row_idx - citation_start_row) * 10))
                        citation = Citation(
                            dealer_id=dealer_id,
                            directory_id=directory.id,
                            created_at=created_date
                        )
                        db.session.add(citation)
                        citations_imported += 1

                # Commit per-dealer to persist progress and avoid large transactions
                db.session.commit()
            except Exception as de:
                print(f"  ✗ Error processing dealer {dealer_id}: {de}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                continue

            if dealers_imported % 10 == 0 or citations_imported % 100 == 0:
                print(f"    Progress: {dealers_imported} dealers, {citations_imported} citations queued")
        
        db.session.commit()
        
        total_dealers = Dealer.query.count()
        total_citations = Citation.query.count()
        
        print(f"✓ Imported {dealers_imported} dealers from the updated workbook (Total: {total_dealers})")
        print(f"✓ Imported {citations_imported} citations from the updated workbook (Total: {total_citations})")
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
    print("Citation Building Management System - Updated Dealer Data Import")
    print("=" * 60)

    replace_existing = '--replace' in sys.argv
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Create tables
        print("\nInitializing database...")
        db.create_all()
        print("✓ Database tables created")

        # Disable statement timeout for this session to allow large imports
        try:
            db.session.execute(text('SET statement_timeout = 0'))
            db.session.commit()
            print('✓ Disabled statement_timeout for this import session')
        except Exception:
            db.session.rollback()
            print('⚠️ Could not disable statement_timeout; imports may time out')

        if replace_existing:
            clear_existing_data()
        
        # Import data
        print("\n" + "-" * 60)
        if sync_backlink_directories():
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
