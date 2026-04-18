from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import logging
from services import manabox
from database import SessionLocal
from models import SyncLog, ImportCardLink

bp = Blueprint('inventory', __name__, url_prefix='/inventory')
logger = logging.getLogger(__name__)


def _is_ajax_request(req):
    return req.headers.get('X-Requested-With') == 'XMLHttpRequest'

@bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            if _is_ajax_request(request):
                return jsonify({'success': False, 'error': 'No file part'}), 400
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            if _is_ajax_request(request):
                return jsonify({'success': False, 'error': 'No selected file'}), 400
            flash('No selected file')
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            db = SessionLocal()
            try:
                result = manabox.import_csv(db, file)
                import_cards = result.pop('import_cards', [])
                cards_processed = int(result.get('added', 0)) + int(result.get('updated', 0)) + int(result.get('skipped', 0))
                sync_log = SyncLog(
                    sync_type='manabox_csv_import',
                    status='complete',
                    cards_processed=cards_processed,
                    errors=0,
                )
                db.add(sync_log)
                db.flush()

                for item in import_cards:
                    card_id = item.get('card_id')
                    if card_id is None:
                        continue
                    db.add(
                        ImportCardLink(
                            sync_log_id=sync_log.id,
                            card_id=card_id,
                            status=item.get('status', 'updated'),
                        )
                    )

                db.commit()
                if _is_ajax_request(request):
                    return jsonify({'success': True, 'result': result}), 200
                flash(f"Import successful: {result['added']} added, {result['updated']} updated, {result['skipped']} skipped.", 'success')
            except Exception as e:
                db.rollback()
                logger.exception("CSV import failed")
                try:
                    db.add(
                        SyncLog(
                            sync_type='manabox_csv_import',
                            status='failed',
                            cards_processed=0,
                            errors=1,
                        )
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                if _is_ajax_request(request):
                    return jsonify({'success': False, 'error': 'Internal server error'}), 500
                flash("An internal server error occurred during import.", 'danger')
            finally:
                db.close()
            return redirect(url_for('inventory.import_csv'))

        if _is_ajax_request(request):
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload a CSV file.'}), 400
        flash('Invalid file type. Please upload a CSV file.', 'error')
        return redirect(url_for('inventory.import_csv'))

    return render_template('import.html')
