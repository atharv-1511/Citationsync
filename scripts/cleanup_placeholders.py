"""One-off cleanup: remove BacklinkDirectory rows with URLs ending in '.example'.

Run with the project's virtualenv Python:

    .\venv\Scripts\python.exe scripts\cleanup_placeholders.py

This will print how many rows were found and deleted.
"""
import sys
import os

# Ensure project root is on sys.path so `from app import app` works when
# executing this script from the `scripts/` folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import db, BacklinkDirectory

def run_cleanup():
    with app.app_context():
        qry = BacklinkDirectory.query.filter(BacklinkDirectory.url.ilike('%.example'))
        count = qry.count()
        if count == 0:
            print('No .example placeholder directories found.')
            return

        print(f'Found {count} placeholder directories. Deleting...')
        try:
            qry.delete(synchronize_session=False)
            db.session.commit()
            print(f'Deleted {count} placeholder directories.')
        except Exception as exc:
            db.session.rollback()
            print('Error deleting placeholder directories:', exc)

if __name__ == '__main__':
    run_cleanup()
