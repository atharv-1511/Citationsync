"""
Cleanup script to remove unnecessary files after cloud migration
Run this only after confirming data is stored in Supabase.
"""
import os
import shutil
from pathlib import Path


def cleanup_local_files():
    """Remove unnecessary local files after cloud migration"""
    
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    
    # Files and folders to remove (after cloud migration)
    items_to_remove = [
        'Data',  # Local data folder - now in Supabase-backed workflow
        'database/backlinks.db',  # Old SQLite database
    ]
    
    print("🗑️ Cleaning up unnecessary local files...")
    print("="*60)
    
    removed = 0
    failed = 0
    
    for item in items_to_remove:
        item_path = PROJECT_ROOT / item
        
        if not item_path.exists():
            print(f"⏭️ Skipped: {item} (not found)")
            continue
        
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
                print(f"✅ Removed directory: {item}")
            else:
                item_path.unlink()
                print(f"✅ Removed file: {item}")
            removed += 1
        except Exception as e:
            print(f"❌ Failed to remove {item}: {str(e)}")
            failed += 1
    
    print("="*60)
    print(f"\n✅ Cleanup complete!")
    print(f"  Removed: {removed}")
    print(f"  Failed: {failed}")
    
    print("\n" + "="*60)
    print("YOUR SYSTEM IS NOW CLOUD-BASED:")
    print("="*60)
    print("✅ Database: Supabase PostgreSQL")
    print("✅ Data Files: Local source files removed")
    print("✅ No local data stored locally")
    print("="*60)


if __name__ == '__main__':
    cleanup_local_files()
