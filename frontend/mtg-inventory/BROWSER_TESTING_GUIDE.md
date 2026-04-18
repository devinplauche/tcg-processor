# Browser Testing Quick Start Guide

## Prerequisites
- Python 3.8+
- Virtual environment activated (`.venv`)
- All dependencies installed (`requirements.txt`)

## Quick Setup

### 1. Activate Virtual Environment
```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# macOS/Linux
source .venv/bin/activate
```

### 2. Install Dependencies (if not already done)
```bash
cd mtg-inventory
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
python -c "from database import init_db; init_db()"
```

### 4. Start the Flask Development Server
```bash
python app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### 5. Open in Browser
Navigate to: **http://localhost:5000**

---

## What You Can Test

### Dashboard (`/`)
- ✅ Overview cards showing statistics
- ✅ Quick action buttons
- ✅ Recent imports table
- ✅ System status indicators

### CSV Import (`/inventory/import`)
- ✅ Drag-and-drop file upload
- ✅ File selection browser
- ✅ Progress bar with animation
- ✅ Upload simulation

### Features Coming Soon
- 📦 Box/Location View
- 🛒 eBay Listing Creation
- 🔍 Card Search
- 💰 Pricing Management

---

## Testing CSV Import

### Option 1: Use Provided Test File
```bash
# Copy test.csv to the mtg-inventory folder
# Then upload it via the browser
```

### Option 2: Create Sample CSV
Create a file named `sample.csv` with this content:
```csv
name,set,number,condition,foil
Ragavan, Nimble Pilferer,MH2,138,NM,normal
Wrenn and Six,MH1,217,LP,foil
Force of Will,ALL,28,NM,normal
```

Then upload via the browser import page.

---

## Troubleshooting

### Port 5000 Already in Use
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

### Database Issues
```bash
# Reset the database
python -c "from pathlib import Path; Path('mtg_inventory.db').unlink(missing_ok=True); from database import init_db; init_db()"
```

### Module Not Found Errors
```bash
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### CORS or Static File Issues
```bash
# Clear browser cache (Ctrl+Shift+Delete or Cmd+Shift+Delete)
# Or restart Flask with: flask run -p 8000
# Alternative for app.py runs: set FLASK_RUN_PORT=8000 before `python app.py`
```

---

## Browser DevTools Tips

1. **Open DevTools**: F12 or Ctrl+Shift+I (Windows/Linux), Cmd+Option+I (macOS)
2. **Console Tab**: See any JavaScript errors
3. **Network Tab**: Check API requests and their status
4. **Application Tab**: View localStorage and cookies
5. **Elements Tab**: Inspect HTML/CSS

---

## Next Steps After Basic Testing

1. **Test Database**: Upload a CSV and verify it's stored in the database
2. **Check Logs**: Look in `logs/` folder for any errors
3. **API Testing**: Use the `send_request.py` script:
   ```bash
   python send_request.py
   ```
4. **Run Full Test Suite**:
   ```bash
   pytest test_import.py test_services.py test_e2e.py -v
   ```

---

## File Structure Reference

```
mtg-inventory/
├── app.py                 # Flask application entry point
├── database.py            # Database setup
├── models.py              # SQLAlchemy models
├── requirements.txt       # Python dependencies
├── routes/
│   ├── inventory.py       # CSV import and card management
│   ├── ebay.py           # eBay listing (stub)
│   ├── tcgplayer.py      # Pricing (stub)
│   └── locations.py      # Box management (stub)
├── services/
│   ├── manabox.py        # CSV import logic
│   ├── location_engine.py # Box assignment logic
│   ├── scryfall_api.py   # Card data API
│   └── ...
├── static/
│   ├── app.js            # Client-side JavaScript
│   └── style.css         # Styling (dark theme)
└── templates/
    ├── base.html         # Base template
    ├── dashboard.html    # Home page
    ├── import.html       # CSV import page
    ├── box_view.html     # Box viewer (future)
    └── card_detail.html  # Card details (future)
```

---

## Environment Variables

The following are already configured in `.env`:
- `DATABASE_URL=sqlite:///mtg_inventory.db` - Local database
- `BOX_CAPACITY=500` - Cards per box
- `EBAY_SANDBOX_MODE=True` - Use sandbox (safe for testing)

To add API keys later (optional for testing):
```env
SCRYFALL_API=https://api.scryfall.com
TCGPLAYER_API_KEY=<your-key>
TCGPLAYER_API_SECRET=<your-secret>
EBAY_CLIENT_ID=<your-id>
EBAY_CLIENT_SECRET=<your-secret>
```

---

## Performance Notes

- **First Load**: May take a few seconds to initialize the database
- **CSV Upload**: Small files (<1MB) process instantly
- **API Calls**: Mock data used for testing (no actual API calls)

---

## Support & Debugging

If something doesn't work:
1. Check the console (F12) for JavaScript errors
2. Check the terminal for Flask errors
3. Review `logs/` folder for application logs
4. Verify `.env` file is in the mtg-inventory directory
5. Ensure all files were created/modified correctly

---

**Ready to test? Run `python app.py` and open http://localhost:5000** 🚀
