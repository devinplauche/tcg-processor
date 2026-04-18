# MTG Inventory and Arbitrage System - Organization Plan

## Current Workspace Structure
The workspace contains many files across various directories that make navigation difficult. The files are scattered across multiple directories without clear organization.

## Proposed Directory Structure

### 0. Root-Level Files and Shared Infrastructure
Keep these at the repository root and treat them as shared project controls:
- requirements.txt
- pyproject.toml
- setup.py
- .env (local only; never commit secrets)
- .gitignore
- README.md

Add a shared package for cross-project code:
- shared/ (or common/) for utilities/models reused by mtg-inventory and arbitrage-engine

Packaging guidance:
- Each major Python code directory should be a package with __init__.py
- This includes mtg-inventory, arbitrage-engine, MTGJSON-analysis, buylist-updater, and shared

Deployment/CI artifacts should be discoverable at root (or a documented infra directory):
- Dockerfile
- docker-compose.yml
- Kubernetes manifests (for example, k8s/)
- .github/workflows/ (or .gitlab-ci.yml)

### 1. mtg-inventory/ - Main Inventory Management System
This directory should contain:
- Core application files (app.py, config.py, database.py, models.py)
- Route handlers (routes/inventory.py, routes/ebay.py, routes/locations.py, routes/tcgplayer.py)
- Service integrations (services/scryfall_api.py, services/tcgplayer_api.py, services/ebay_api.py, services/chaos_sort.py, etc.)
- Templates and static assets (templates/*.html, static/*.css, static/*.js)
- Testing framework files (tests/*, test_* files, conftest.py)
- Documentation files (README.md, API_SETUP_GUIDE.md, HOW_TO_USE_DOCUMENTATION.md, etc.)

### 2. arbitrage-engine/ - Arbitrage Opportunity Detection
This directory should contain:
- Arbitrage detection algorithms (arbitrage_engine.py, find_arbitrage.py, check_arbitrage.py)
- Price comparison logic
- Data processing scripts for arbitrage analysis

### 3. MTGJSON-analysis/ - Data Analysis and Processing
This directory should contain:
- Data analysis scripts (card_value_report.py, inspect_data.py, verify_prices.py)
- Card value processing tools
- Data verification utilities
- Data analysis and reporting scripts

### 4. buylist-updater/ - Buylist Scraping and Updating
This directory should contain:
- Scraper scripts (atomic_empire_scraper.py, cardkingdom_scraper_selenium.py)
- Buylist processing and updating tools
- Data extraction and transformation scripts

### 5. docs/ - Documentation
This directory should contain:
- Project documentation and guides
- API documentation
- Implementation details
- User manuals and setup guides

### 6. contract/ - API Contracts and Specifications
This directory should contain:
- API contract specifications
- Documentation index
- API contract files

### 7. architecture/ - Architecture Diagrams and Documentation
This directory should contain:
- Architecture diagrams (mtg_demo.html, mtg_friendly_diagram.html, mtg_uml.html)
- Design documents
- System architecture documentation

### 8. test_data/ - Test Data Files
This directory should contain:
- Sample data for testing
- Test verification data
- Test files and datasets

## Implementation Steps

- Before starting: create a full backup and/or ensure the workspace is committed to version control.

1. **Create new directory structure**:
   - Create the 8 main directories listed above
   - Move relevant files to appropriate directories

2. **File organization**:
   - Move core application files to mtg-inventory/
   - Move arbitrage-related files to arbitrage-engine/
   - Move analysis scripts to MTGJSON-analysis/
   - Move scraper scripts to buylist-updater/
   - Move documentation to docs/
   - Move architecture diagrams to architecture/
   - Keep test data in test_data/

3. **Update references**:
   - Update import statements in code to reflect new paths
   - Update configuration files with new paths
   - Update any hardcoded paths
   - During migration: make incremental commits per directory move and verify imports at each step

4. **After moving files (step 3)**:
   - Run the full test suite and linting
   - Start the application and verify major endpoints still work

5. **Validation**:
   - Verify key features with smoke tests (import, search, sync, listing flows)
   - Confirm package imports resolve cleanly from the new layout

6. **Rollback plan**:
   - If critical issues are found, restore from backup or reset to the last known-good commit
   - Re-apply migration in smaller chunks with validation gates

7. **Cleanup**:
   - Remove duplicate files
   - Remove unnecessary temporary files
   - Clean up the root directory

## Benefits of This Organization

- Clear separation of concerns
- Easier navigation and understanding of project structure
- Better maintainability
- Improved collaboration
- Cleaner workspace for development

This organization will make the project much more manageable and easier to navigate.