import os
import importlib.util
import subprocess
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import init_db, SessionLocal
from routes import inventory, ebay, tcgplayer, locations
from sqlalchemy import desc, asc, func
from services.scryfall_api import ScryfallAPI
from services.scryfall_api import eBayAPI


def compute_pricing_engine_results(condition=None):
    """Compute arbitrage opportunities using MTGJSON-analysis/find_arbitrage.py helpers."""
    script_dir = os.path.abspath(os.path.join(app_dir, '..', 'MTGJSON-analysis'))
    script_path = os.path.join(script_dir, 'find_arbitrage.py')

    if not os.path.exists(script_path):
        raise FileNotFoundError('find_arbitrage.py not found')

    spec = importlib.util.spec_from_file_location('find_arbitrage_module', script_path)
    if not spec or not spec.loader:
        raise RuntimeError('Unable to load find_arbitrage.py module spec')

    module = importlib.util.module_from_spec(spec)
    original_cwd = os.getcwd()
    try:
        os.chdir(script_dir)
        spec.loader.exec_module(module)
        result = module.compute_arbitrage(condition=condition or None)
    finally:
        os.chdir(original_cwd)

    opportunities = result.get('opportunities', [])[:30]
    enriched = []
    for opp in opportunities:
        image_url = ''
        try:
            search = ScryfallAPI.search_cards(opp.get('name', ''), limit=1)
            if search:
                card_obj = search[0]
                image_url = (card_obj.get('image_uris') or {}).get('small', '')
        except Exception:
            image_url = ''

        enriched.append(
            {
                'name': opp.get('name', 'Unknown'),
                'set': opp.get('set', '?'),
                'number': str(opp.get('number', '?')),
                'retail_source': opp.get('retail_source', '?'),
                'retail_price': float(opp.get('retail_price', 0.0)),
                'ck_listed': float(opp.get('ck_listed', 0.0)),
                'ck_payout': float(opp.get('ck_payout', 0.0)),
                'profit': float(opp.get('profit', 0.0)),
                'margin': float(opp.get('margin', 0.0)),
                'image_url': image_url,
            }
        )

    return {
        'condition': condition or 'DEFAULT',
        'summary': result.get('summary', {}),
        'opportunities': enriched,
        'latest_date': result.get('latest_date'),
    }

# Ensure we're working from the correct directory
app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(inventory.bp)
# app.register_blueprint(ebay.bp)
# app.register_blueprint(tcgplayer.bp)
# app.register_blueprint(locations.bp)

# ============= MAIN ROUTES =============

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/cards')
def cards():
    return render_template('cards.html')


@app.route('/boxes')
def boxes():
    return render_template('box_view.html')


@app.route('/ebay')
def ebay_console():
    return render_template('ebay.html')


@app.route('/pricing-engine')
def pricing_engine():
    return render_template('pricing_engine.html')


# ============= API ENDPOINTS =============

@app.route('/api/cards/search')
def api_search_cards():
    """Search for cards by name in database"""
    from models import Card
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if not query or len(query) < 2:
        return jsonify([])
    
    db = SessionLocal()
    try:
        cards = db.query(Card).filter(
            Card.name.ilike(f'{query}%')
        ).limit(limit).all()
        
        return jsonify([{
            'id': c.id,
            'scryfall_id': c.scryfall_id,
            'name': c.name,
            'set': c.set_code,
            'collector_number': c.collector_number,
            'condition': c.condition,
            'quantity': c.quantity,
            'purchase_price': c.purchase_price
        } for c in cards])
    finally:
        db.close()


@app.route('/api/cards/list')
def api_list_cards():
    """Get paginated list of cards with filtering"""
    from models import Card
    
    db = SessionLocal()
    try:
        # Get query parameters
        search_query = request.args.get('q', '').strip()
        condition = request.args.get('condition', '').strip()
        foil = request.args.get('foil', '').strip()
        box = request.args.get('box', '', type=str)
        sort_by = request.args.get('sort', 'name')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Build query
        query = db.query(Card)
        
        # Apply filters
        if search_query:
            query = query.filter(Card.name.ilike(f'%{search_query}%'))
        
        if condition:
            query = query.filter(Card.condition == condition)
        
        if foil:
            query = query.filter(Card.foil == (foil.lower() == 'foil'))

        if box:
            try:
                query = query.filter(Card.box_number == int(box))
            except ValueError:
                return jsonify({'error': 'Invalid box filter'}), 400
        
        # Apply sorting
        if sort_by == 'value':
            sort_expr = (Card.purchase_price * Card.quantity)
            query = query.order_by(desc(sort_expr))
        elif sort_by == 'quantity':
            query = query.order_by(desc(Card.quantity))
        elif sort_by == 'date':
            query = query.order_by(desc(Card.created_at))
        else:  # name
            query = query.order_by(asc(Card.name))
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * limit
        cards = query.offset(offset).limit(limit).all()
        
        total_pages = (total + limit - 1) // limit
        
        return jsonify({
            'cards': [{
                'id': c.id,
                'name': c.name,
                'set_code': c.set_code,
                'collector_number': c.collector_number,
                'condition': c.condition,
                'foil': c.foil,
                'quantity': c.quantity,
                'purchase_price': c.purchase_price,
                'location_code': c.location_code
            } for c in cards],
            'total': total,
            'page': page,
            'pages': total_pages,
            'limit': limit
        })
    finally:
        db.close()








@app.route('/api/boxes')
def api_get_boxes():
    """Get all storage boxes"""
    from models import Box, Card
    db = SessionLocal()
    try:
        boxes = db.query(Box).order_by(asc(Box.box_number)).all()
        return jsonify([
            {
                'box_number': b.box_number,
                'capacity': b.capacity or 0,
                'current_count': b.current_count or 0,
                'card_rows': db.query(Card).filter(Card.box_number == b.box_number).count(),
            }
            for b in boxes
        ])
    finally:
        db.close()


@app.route('/api/boxes/<int:box_id>')
def api_get_box(box_id):
    """Get details for a specific box"""
    from models import Box, Card
    db = SessionLocal()
    try:
        box = db.query(Box).filter(Box.box_number == box_id).first()
        if not box:
            return jsonify({'error': 'Box not found'}), 404

        cards = (
            db.query(Card)
            .filter(Card.box_number == box_id)
            .order_by(asc(Card.slot_number), asc(Card.name))
            .limit(50)
            .all()
        )

        return jsonify({
            'id': box_id,
            'number': box_id,
            'capacity': box.capacity or 0,
            'current_count': box.current_count or 0,
            'cards': [
                {
                    'id': c.id,
                    'name': c.name,
                    'set_code': c.set_code,
                    'slot_number': c.slot_number,
                    'location_code': c.location_code,
                    'quantity': c.quantity,
                }
                for c in cards
            ]
        })
    finally:
        db.close()


@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'database': 'connected',
        'version': '0.1.0'
    })


@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Get dashboard statistics"""
    from models import Card, Box, SyncLog
    db = SessionLocal()
    try:
        total_cards = db.query(Card).count()
        total_boxes = db.query(Box).count()
        total_value = db.query(
            func.sum(Card.purchase_price * Card.quantity)
        ).scalar() or 0
        
        active_listings = db.query(Card).filter(Card.ebay_listing_id.isnot(None)).count()

        return jsonify({
            'total_cards': total_cards,
            'total_boxes': total_boxes,
            'estimated_value': round(float(total_value), 2),
            'active_listings': active_listings,
        })
    finally:
        db.close()


@app.route('/api/ebay/health')
def api_ebay_health():
    """Return eBay integration readiness and token validation status."""
    from config import Config

    configured = bool(Config.EBAY_APP_ID and Config.EBAY_DEV_ID)
    token_configured = bool(Config.EBAY_USER_TOKEN)

    result = {
        'configured': configured,
        'app_id_configured': bool(Config.EBAY_APP_ID),
        'dev_id_configured': bool(Config.EBAY_DEV_ID),
        'user_token_configured': token_configured,
        'refresh_token_configured': token_configured,
        'sandbox_mode': Config.EBAY_SANDBOX_MODE,
        'token_ok': False,
        'auth_status_code': None,
    }

    if configured and token_configured:
        api = eBayAPI()
        result['token_ok'] = api.validate_rest_access()
        result['auth_mode'] = getattr(api, '_auth_mode', None)
        result['auth_status_code'] = getattr(api, '_last_auth_status', None)

    return jsonify(result)


@app.route('/api/ebay/cards')
def api_ebay_cards():
    """List cards that are candidates for eBay listing creation."""
    from models import Card

    limit = request.args.get('limit', 100, type=int)
    db = SessionLocal()
    try:
        cards = (
            db.query(Card)
            .order_by(desc(Card.updated_at), desc(Card.id))
            .limit(limit)
            .all()
        )

        return jsonify([
            {
                'id': c.id,
                'name': c.name,
                'set_code': c.set_code,
                'condition': c.condition,
                'quantity': c.quantity,
                'purchase_price': c.purchase_price,
                'ebay_listing_id': c.ebay_listing_id,
                'sku': f'mtg-card-{c.id}',
            }
            for c in cards
        ])
    finally:
        db.close()


@app.route('/api/ebay/listings', methods=['POST'])
def api_create_ebay_listing():
    """Create an eBay listing for an inventory card."""
    from models import Card

    payload = request.get_json(silent=True) or {}
    card_id = payload.get('card_id')
    if not card_id:
        return jsonify({'success': False, 'error': 'card_id is required'}), 400

    db = SessionLocal()
    try:
        card = db.query(Card).filter(Card.id == int(card_id)).first()
        if not card:
            return jsonify({'success': False, 'error': 'Card not found'}), 404

        ebay_api = eBayAPI()
        if not ebay_api.get_access_token():
            return jsonify({'success': False, 'error': 'eBay auth failed. Verify EBAY_APP_ID, EBAY_DEV_ID, and EBAY_USER_TOKEN.'}), 502

        quantity = int(payload.get('quantity') or card.quantity or 1)
        price = float(payload.get('price') or card.purchase_price or 1.0)
        condition = payload.get('condition') or card.condition or 'NM'

        listing_data = {
            'sku': f'mtg-card-{card.id}',
            'product': {
                'title': f"{card.name} [{card.set_code}] {condition}",
                'description': payload.get('description') or f"{card.name} from set {card.set_code}. Condition: {condition}.",
            },
            'availability': {
                'shipToLocationAvailability': {
                    'quantity': quantity,
                }
            },
            'condition': condition,
            'price': {
                'value': f"{price:.2f}",
                'currency': 'USD',
            },
        }

        listing_id = ebay_api.create_listing(listing_data)
        if not listing_id:
            return jsonify({'success': False, 'error': 'eBay listing creation failed'}), 502

        card.ebay_listing_id = listing_id
        card.list_on_ebay = True
        db.commit()

        return jsonify({'success': True, 'listing_id': listing_id, 'card_id': card.id})
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid numeric value in request payload'}), 400
    except Exception as exc:
        db.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 500
    finally:
        db.close()


@app.route('/api/ebay/listings/<listing_id>', methods=['PATCH'])
def api_update_ebay_listing(listing_id):
    """Update an existing eBay listing with new pricing/quantity data."""
    payload = request.get_json(silent=True) or {}
    ebay_api = eBayAPI()
    if not ebay_api.get_access_token():
        return jsonify({'success': False, 'error': 'eBay auth failed. Verify EBAY_APP_ID, EBAY_DEV_ID, and EBAY_USER_TOKEN.'}), 502

    update_payload = {
        'price': {
            'value': f"{float(payload.get('price', 0.0)):.2f}",
            'currency': 'USD',
        },
        'availability': {
            'shipToLocationAvailability': {
                'quantity': int(payload.get('quantity', 1)),
            }
        },
    }

    result = ebay_api.update_listing(listing_id, update_payload)
    if not result:
        return jsonify({'success': False, 'error': 'eBay update failed'}), 502

    return jsonify({'success': True, 'listing_id': listing_id, 'result': result})


@app.route('/api/ebay/listings/<listing_id>/publish', methods=['POST'])
def api_publish_ebay_listing(listing_id):
    """Publish a listing to eBay marketplace."""
    ebay_api = eBayAPI()
    if not ebay_api.get_access_token():
        return jsonify({'success': False, 'error': 'eBay auth failed. Verify EBAY_APP_ID, EBAY_DEV_ID, and EBAY_USER_TOKEN.'}), 502

    published = ebay_api.publish_listing(listing_id)
    if not published:
        return jsonify({'success': False, 'error': 'Failed to publish listing'}), 502

    return jsonify({'success': True, 'listing_id': listing_id})


@app.route('/api/ebay/listings/bulk-publish', methods=['POST'])
def api_bulk_publish_ebay_listings():
    """Publish a set of listings in one operation."""
    payload = request.get_json(silent=True) or {}
    listing_ids = payload.get('listing_ids') or []
    if not isinstance(listing_ids, list) or not listing_ids:
        return jsonify({'success': False, 'error': 'listing_ids array is required'}), 400

    ebay_api = eBayAPI()
    if not ebay_api.get_access_token():
        return jsonify({'success': False, 'error': 'eBay auth failed. Verify EBAY_APP_ID, EBAY_DEV_ID, and EBAY_USER_TOKEN.'}), 502

    results = []
    for listing_id in listing_ids:
        ok = ebay_api.publish_listing(str(listing_id))
        results.append({'listing_id': listing_id, 'published': bool(ok)})

    published_count = sum(1 for item in results if item['published'])
    return jsonify(
        {
            'success': published_count == len(results),
            'published_count': published_count,
            'requested_count': len(results),
            'results': results,
        }
    )


@app.route('/api/pricing-engine/data')
def api_pricing_engine_data():
    """Return structured arbitrage opportunities for UI table rendering."""
    condition = (request.args.get('condition') or '').strip().upper()
    try:
        data = compute_pricing_engine_results(condition=condition or None)
        return jsonify({'success': True, **data})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/pricing-engine/run')
def api_pricing_engine_run():
    """Execute MTGJSON find_arbitrage.py and return stdout for UI rendering."""
    condition = (request.args.get('condition') or '').strip().upper()
    script_dir = os.path.abspath(os.path.join(app_dir, '..', 'MTGJSON-analysis'))
    script_path = os.path.join(script_dir, 'find_arbitrage.py')

    if not os.path.exists(script_path):
        return jsonify({'success': False, 'error': 'find_arbitrage.py not found'}), 404

    cmd = [sys.executable, script_path]
    if condition:
        cmd.append(condition)

    try:
        proc = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return jsonify(
            {
                'success': proc.returncode == 0,
                'condition': condition or 'DEFAULT',
                'stdout': proc.stdout,
                'stderr': proc.stderr,
                'returncode': proc.returncode,
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Pricing engine timed out'}), 504


@app.route('/api/dashboard/recent-imports')
def api_recent_imports():
    """Get recent import history"""
    from models import SyncLog
    db = SessionLocal()
    try:
        imports = db.query(SyncLog).order_by(
            SyncLog.run_at.desc()
        ).limit(10).all()
        
        return jsonify([{
            'id': imp.id,
            'date': imp.run_at.isoformat() if imp.run_at else None,
            'type': imp.sync_type or 'import',
            'cards_processed': imp.cards_processed or 0,
            'errors': imp.errors or 0,
            'status': imp.status or 'unknown'
        } for imp in imports])
    finally:
        db.close()


@app.route('/api/dashboard/recent-imports/<int:import_id>/cards')
def api_recent_import_cards(import_id):
    """Get card rows included in a specific import."""
    from models import Card, SyncLog, ImportCardLink

    db = SessionLocal()
    try:
        import_log = db.query(SyncLog).filter(SyncLog.id == import_id).first()
        if not import_log:
            return jsonify({'error': 'Import not found'}), 404

        link_rows = (
            db.query(ImportCardLink)
            .filter(ImportCardLink.sync_log_id == import_id)
            .order_by(desc(ImportCardLink.id))
            .all()
        )

        cards_payload = []
        if link_rows:
            card_ids = [row.card_id for row in link_rows]
            cards_by_id = {
                card.id: card
                for card in db.query(Card).filter(Card.id.in_(card_ids)).all()
            }

            for row in link_rows:
                card = cards_by_id.get(row.card_id)
                if not card:
                    continue
                cards_payload.append(
                    {
                        'id': card.id,
                        'name': card.name,
                        'set_code': card.set_code,
                        'condition': card.condition,
                        'quantity': card.quantity,
                        'location_code': card.location_code,
                        'updated_at': card.updated_at.isoformat() if card.updated_at else None,
                        'status': row.status,
                    }
                )
        else:
            # Backward compatibility for imports created before explicit link tracking.
            later_import = (
                db.query(SyncLog)
                .filter(SyncLog.run_at > import_log.run_at)
                .order_by(asc(SyncLog.run_at))
                .first()
            )

            query = db.query(Card).filter(Card.updated_at >= import_log.run_at)
            if later_import:
                query = query.filter(Card.updated_at < later_import.run_at)

            cards = query.order_by(desc(Card.updated_at)).limit(200).all()
            cards_payload = [
                {
                    'id': c.id,
                    'name': c.name,
                    'set_code': c.set_code,
                    'condition': c.condition,
                    'quantity': c.quantity,
                    'location_code': c.location_code,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                    'status': 'unknown',
                }
                for c in cards
            ]

        return jsonify(
            {
                'import': {
                    'id': import_log.id,
                    'date': import_log.run_at.isoformat() if import_log.run_at else None,
                    'type': import_log.sync_type or 'import',
                    'status': import_log.status or 'unknown',
                    'cards_processed': import_log.cards_processed or 0,
                },
                'cards': cards_payload,
            }
        )
    finally:
        db.close()


@app.route('/api/dashboard/system-status')
def api_system_status():
    """Get system status with real configuration checks"""
    from models import Card, SyncLog
    from config import Config
    
    db = SessionLocal()
    try:
        # Database check
        db_connected = True
        try:
            db.query(Card).count()
        except:
            db_connected = False
        
        # eBay check
        ebay_configured = bool(Config.EBAY_APP_ID and Config.EBAY_DEV_ID and Config.EBAY_USER_TOKEN)
        ebay_status = 'ready' if ebay_configured else 'not_configured'
        ebay_mode = 'sandbox' if Config.EBAY_SANDBOX_MODE else 'production'
        
        return jsonify({
            'database': {
                'status': 'connected' if db_connected else 'disconnected',
                'icon': '✓' if db_connected else '✗'
            },
            'scryfall_api': {
                'status': 'ready',
                'icon': '✓',
                'note': 'Offline card data'
            },
            'ebay_sandbox': {
                'status': ebay_status,
                'icon': '✓' if ebay_configured else '—',
                'note': f'{"Ready (" + ebay_mode + " mode)" if ebay_configured else "Setup required - see docs"}'
            }
        })
    finally:
        db.close()


# ============= ERROR HANDLERS =============

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# ============= DEBUGGING & DEVELOPMENT =============

@app.before_request
def log_request():
    """Log incoming requests (development only)"""
    if app.debug:
        print(f"{request.method} {request.path}")


if __name__ == '__main__':
    app.run(debug=True)
