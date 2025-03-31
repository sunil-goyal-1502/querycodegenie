
#!/usr/bin/env python3
from src.backend.api import app

if __name__ == '__main__':
    print("Starting CodeGenie backend server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
