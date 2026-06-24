from admin.auth import ensure_default_admin
from admin.api import app

ensure_default_admin()

if __name__ == "__main__":
    app.run()
