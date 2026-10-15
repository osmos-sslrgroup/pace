import os
import sys
import socket
import webbrowser
from threading import Timer
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Setup PyInstaller PhreeqPython DB environment variable before importing server
if getattr(sys, 'frozen', False):
    # PyInstaller extract directory
    base_dir = sys._MEIPASS
    os.environ['PHREEQPYTHON_DB'] = os.path.join(base_dir, 'phreeqpython', 'database')
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Import the existing app from server.py
from server import app

# Path to the frontend UI folder
if getattr(sys, 'frozen', False):
    # When bundled, ui_ux_design is packaged in the root of _MEIPASS
    ui_dir = os.path.join(base_dir, "ui_ux_design")
else:
    # During dev, run_app.py is in backend/, ui_ux_design is one level up
    ui_dir = os.path.join(os.path.dirname(base_dir), "ui_ux_design")

# Mount the static files to serve the frontend on the root URL
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
else:
    print(f"Warning: UI directory not found at {ui_dir}")

def find_free_port():
    """Finds a free network port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def open_browser(port):
    """Opens the default web browser to the local app URL"""
    url = f"http://127.0.0.1:{port}"
    print(f"Opening browser at {url}")
    webbrowser.open_new(url)

if __name__ == "__main__":
    print("Starting PACE Application...")
    
    # Find a dynamic port to avoid 8000 conflicts
    app_port = find_free_port()
    print(f"Dynamically assigned port: {app_port}")
    
    # Delay browser opening slightly to let server start
    Timer(1.5, open_browser, args=(app_port,)).start()
    
    # Run the server (localhost only)
    uvicorn.run(app, host="127.0.0.1", port=app_port, log_level="warning")
