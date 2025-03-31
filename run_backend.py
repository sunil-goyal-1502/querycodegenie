
#!/usr/bin/env python3
from src.backend.api import app
import os

if __name__ == '__main__':
    # Allow connections from any host to make development easier
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting CodeGenie backend server on http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
