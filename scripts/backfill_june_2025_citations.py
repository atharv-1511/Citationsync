"""Backfill the first five citation timestamps per dealer into June 2025.

This keeps the per-dealer citation sequence chronological while making the
earliest five citation records appear in June 2025.

Run with the project's virtualenv Python.
"""

from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import db, Dealer, Citation


def run_backfill():
    with app.app_context():
        dealers = Dealer.query.order_by(Dealer.id.asc()).all()
        updated = 0
        month_start = datetime(2025, 6, 1, 9, 0, 0)

        for dealer in dealers:
            citations = (
                Citation.query.filter_by(dealer_id=dealer.id)
                .order_by(Citation.created_at.asc(), Citation.id.asc())
                .limit(5)
                .all()
            )

            for index, citation in enumerate(citations):
                citation.created_at = month_start + timedelta(days=index)
                citation.updated_at = citation.created_at
                updated += 1

        try:
            db.session.commit()
            print(f'Updated {updated} citation timestamps to June 2025.')
        except Exception as exc:
            db.session.rollback()
            print('Failed to backfill citation timestamps:', exc)


if __name__ == '__main__':
    run_backfill()
