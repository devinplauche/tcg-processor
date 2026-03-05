from flask import Blueprint, render_template, request, redirect, url_for, flash
from services import manabox
from database import SessionLocal

bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            db = SessionLocal()
            try:
                result = manabox.import_csv(db, file)
                flash(f"Import successful: {result['added']} added, {result['updated']} updated, {result['skipped']} skipped.", 'success')
            except Exception as e:
                flash(f"An error occurred: {e}", 'danger')
            finally:
                db.close()
            return redirect(url_for('inventory.import_csv'))

    return render_template('import.html')
