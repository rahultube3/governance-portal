"""
Governance Portal REST API
Flask + SQLite backend for architecture governance artifact intake & review.
"""
import os

from portal import create_app
from portal.schema import init_db

app = create_app()

if __name__ == "__main__":
    init_db(app.config["DATABASE"])
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
