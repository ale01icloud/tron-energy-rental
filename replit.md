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

## User Preferences
- Manual control over code execution and library installation
- Simple, straightforward Python environment
