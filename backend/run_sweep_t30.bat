@echo off
cd /d "%~dp0"
"C:\Users\yugpa\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m app.scraper.run_all_scrapers --window T+30 >> logs\sweep_t30.log 2>&1
