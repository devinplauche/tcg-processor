# Database Persistence Issue - RESOLVED

## Problem Identified

The SQLite database was not persisting across app restarts due to **relative path resolution issues**. 

### Root Cause
- The `DATABASE_URL` in `.env` was set to `sqlite:///mtg_inventory.db` (relative path)
- When the app was started from different working directories, SQLite would create/use the database file in that directory
- This resulted in multiple `mtg_inventory.db` files being created:
  - `C:\...\tcg-processor\mtg_inventory.db` (empty, created when app started from root)
  - `C:\...\tcg-processor\mtg-inventory\mtg_inventory.db` (with data, created when app started from mtg-inventory dir)

### Impact
- Data was inaccessible when the app restarted from a different directory
- Confusion about which database file was being used

---

## Solution Implemented

### 1. **Modified `database.py`** to use absolute paths
The database configuration now:
- Converts relative SQLite paths to absolute paths based on the file's location
- Ensures the database is always created in `mtg-inventory/mtg_inventory.db` regardless of working directory
- Works correctly even if `.env` specifies a relative path

**Key Changes:**
```python
# Automatically converts sqlite:///mtg_inventory.db to an absolute path:
# sqlite:///C:\Users\...\tcg-processor\mtg-inventory\mtg_inventory.db

if DATABASE_URL and "sqlite:///" in DATABASE_URL:
    relative_path = DATABASE_URL.replace("sqlite:///", "")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_db_path = os.path.join(current_dir, relative_path)
    DATABASE_URL = f"sqlite:///{absolute_db_path}"
```

### 2. **Modified `app.py`** to set working directory
Ensures the app always runs from the `mtg-inventory` directory:
```python
# Ensure we're working from the correct directory
app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)
```

---

## Verification

✅ **Database persistence test passes:**
- 83 cards stored in database
- Database accessible from any working directory
- Same database file used regardless of where app is started

### To Verify Persistence:
```bash
cd C:\Users\devinsGamingPC\Coding\tcg-processor\mtg-inventory

# Run the persistence test
python test_db_persistence.py

# Expected output:
# ✓ Database file exists
# ✓ Card count: 83
# ✓ Box count: 1
# ✅ Database persistence test PASSED!
```

---

## No Action Required

The database is now **properly persisting** across app restarts. All data is safe and accessible.

### Database Location
```
C:\Users\devinsGamingPC\Coding\tcg-processor\mtg-inventory\mtg_inventory.db
```

### Current Data
- **Cards**: 83
- **Boxes**: 1
- **Cards in box**: Path to Exile, Black Lotus, Ancestral Recall, Time Walk, Timetwister, and others

---

## Cleanup (Optional)

You can remove the empty database file created in the root directory:
```powershell
Remove-Item "C:\Users\devinsGamingPC\Coding\tcg-processor\mtg_inventory.db"
```

This has no effect on the app since it now uses the absolute path to the correct file.

---

## Technical Details

### Before Fix
- Relative path: `sqlite:///mtg_inventory.db`
- Location depends on `cwd` when app starts
- Problems: Multiple DB files, data loss on wrong directory

### After Fix
- Absolute path: `sqlite:///C:\Users\...\mtg-inventory\mtg_inventory.db`
- Location fixed regardless of `cwd`
- Benefits: Consistent data access, no confusion about which DB is used

---

## Files Modified
1. `mtg-inventory/database.py` - Added absolute path conversion
2. `mtg-inventory/app.py` - Added working directory setup

## Files Added
1. `mtg-inventory/test_db_persistence.py` - Test script to verify persistence
