import json
from pathlib import Path
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

USERS_FILE = Path(__file__).parent / "users.json"


class User(UserMixin):
    def __init__(self, id, username, password_hash, role, display_name):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.display_name = display_name

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_safe_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role, "display_name": self.display_name}


def _load():
    if not USERS_FILE.exists():
        return []
    return json.loads(USERS_FILE.read_text())


def _save(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def get_user_by_id(uid):
    for u in _load():
        if u["id"] == uid:
            return User(**u)
    return None


def get_user_by_username(username):
    for u in _load():
        if u["username"] == username:
            return User(**u)
    return None


def get_all_users():
    return [User(**u) for u in _load()]


def create_user(username, password, role, display_name):
    users = _load()
    if any(u["username"] == username for u in users):
        raise ValueError(f"Username '{username}' already exists")
    new_id = str(max((int(u["id"]) for u in users), default=0) + 1)
    entry = {
        "id": new_id,
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": role,
        "display_name": display_name,
    }
    users.append(entry)
    _save(users)
    return User(**entry)


def delete_user(uid):
    users = [u for u in _load() if u["id"] != uid]
    _save(users)


def change_password(uid, new_password):
    users = _load()
    for u in users:
        if u["id"] == uid:
            u["password_hash"] = generate_password_hash(new_password)
    _save(users)


def ensure_default_admin():
    if not _load():
        create_user("admin", "admin123", "admin", "Administrator")
        print("=" * 55)
        print("  Default admin created:")
        print("  Username: admin    Password: admin123")
        print("  Change this immediately in Settings!")
        print("=" * 55)
