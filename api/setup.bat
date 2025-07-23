@echo off
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo To run ngrok, you have two options:
echo 1. Install ngrok directly from https://ngrok.com/download
echo 2. Use the pyngrok library (already installed)
echo.
echo For option 1: ngrok http 8000
echo For option 2: Use pyngrok in your Python code
pause