# MTG Inventory and Arbitrage System - Organization Plan

## Current Workspace Structure
The workspace contains many files across various directories that make navigation difficult. The files are scattered across multiple directories without clear organization.

## Proposed Directory Structure

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

4. **Cleanup**:
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