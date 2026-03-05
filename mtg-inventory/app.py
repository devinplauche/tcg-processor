from flask import Flask, render_template, request, redirect, url_for, flash
from database import init_db, SessionLocal
from routes import inventory, ebay, tcgplayer, locations

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(inventory.bp)
# app.register_blueprint(ebay.bp)
# app.register_blueprint(tcgplayer.bp)
# app.register_blueprint(locations.bp)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
