# Python Development Environment

## Overview
A simple Python environment for manual code execution and library management. This setup gives you full control to write code, run scripts, and manage packages yourself.

## Project Structure
- `main.py` - Main entry point with example code
- `requirements.txt` - Python package dependencies
- `.gitignore` - Git ignore rules for Python projects

## How to Use

### Running Python Code
1. Edit `main.py` or create new `.py` files
2. Click the "Run" button or the workflow will auto-run
3. View output in the console

### Installing Packages
You have several options:

**Option 1: Using requirements.txt**
1. Add package names to `requirements.txt`
2. Run: `pip install -r requirements.txt`

**Option 2: Direct pip install**
Run in the shell:
```bash
pip install package-name
```

**Option 3: Using the Replit packager**
The packager tool can also install Python packages automatically.

### Running Different Scripts
To run a different Python file:
```bash
python filename.py
```

Or update the workflow configuration to run your preferred script.

## Recent Changes
- 2025-10-14: Initial project setup with Python 3.11
- Created basic structure with main.py and requirements.txt
- Replaced with advanced finance bot using python-telegram-bot library
- Installed Flask, python-dotenv dependencies
- Configured workflow to run bot.py on port 5000
- Created comprehensive README.md for finance bot
- 2025-10-15: 
  - Implemented multi-group support - each group has independent accounting data
  - Refactored data structure to use per-group state management
  - Added group-specific log directories (data/logs/group_<chat_id>/)
  - Removed OKX exchange rate query feature
  - Added dual-mode support: Polling (Replit) + Webhook (Render Web Service)
  - Code now supports both local development and production deployment
  - Successfully uploaded project to GitHub: lea499579-stack/telegram-finance-bot
- 2025-10-16:
  - Fixed webhook async event loop handling using run_coroutine_threadsafe
  - Fixed Python version compatibility (3.11.9) in render.yaml and .python-version
  - Enhanced webhook setup with validation, error handling, and verification
  - Added webhook URL validation to prevent empty webhook registration
  - Fixed keep-alive mechanism: correct URL variable and 5-minute interval
  - **Production server upgrade**: Replaced Flask dev server with Gunicorn
  - Refactored bot.py to support Gunicorn WSGI deployment
  - Added Gunicorn with 2 workers, 4 threads per worker for production stability

## User Preferences
- Manual control over code execution and library installation
- Chinese language interface for documentation
- Financial tracking bot for Telegram
- **Important**: Each Telegram group has completely independent accounting data

## Bot Features
- Finance tracking with in/out transactions
- USDT conversion with custom rates and exchange rates
- Admin system with permission management
- **Multi-group support**: Each group maintains independent:
  - Transaction records (入金/出金)
  - USDT summary (应下发/已下发)
  - Rate and exchange settings
  - Daily reset schedule
  - Transaction logs
- Data persistence with per-group JSON files (data/groups/group_<chat_id>.json)
- HTTP keepalive server on port 5000
