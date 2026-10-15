import os
import uvicorn
from server import app
from fastapi.staticfiles import StaticFiles

# During cloud deployment, mount the ui directory to root
# (assuming run_cloud.py is run from the backend directory and ui_ux_design is its sibling)
base_dir = os.path.dirname(os.path.abspath(__file__))
ui_dir = os.path.join(os.path.dirname(base_dir), "ui_ux_design")

if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
else:
    print(f"Warning: UI directory not found at {ui_dir}")

if __name__ == "__main__":
    # In a cloud context like Railway or Heroku, the platform assigns a port via the PORT env var.
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 to accept external connections
    uvicorn.run(app, host="0.0.0.0", port=port)
