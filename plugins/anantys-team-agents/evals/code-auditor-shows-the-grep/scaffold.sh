#!/usr/bin/env bash
# A field rename that updated one of its two call sites, plus a loud
# pre-existing vulnerability the change never touched.
#
# `serialize_user` is the one place a user becomes JSON. The change renames its
# `name` key to `full_name` and updates src/api.py. src/notifications.py reads
# the same key and is left raising KeyError — and it is not in the diff, so the
# only way to it is a grep for the changed symbol.
#
# legacy/admin.py concatenates a user id into SQL. It is certain, severe, and
# out of scope: it predates the change and the change did not make it worse.
set -euo pipefail

git init -q -b main .
git config user.email eval@example.invalid
git config user.name "Eval Fixture"

mkdir -p src legacy

cat > src/serializers.py <<'PY'
def serialize_user(user):
    """The one place a user record becomes an API payload."""
    return {"id": user["id"], "name": user["name"], "email": user["email"]}
PY

cat > src/api.py <<'PY'
from serializers import serialize_user


def user_endpoint(user):
    body = serialize_user(user)
    return {"status": 200, "body": body, "display": body["name"]}
PY

cat > src/notifications.py <<'PY'
from serializers import serialize_user


def welcome_email(user):
    body = serialize_user(user)
    return f"Hello {body['name']}, welcome aboard."
PY

cat > legacy/admin.py <<'PY'
def find_user(conn, uid):
    # Here since 2019. Untouched by anything recent.
    return conn.execute(
        "SELECT * FROM users WHERE id = '" + uid + "'"
    ).fetchone()
PY

git add -A
git commit -qm "feat: user serializer and its two consumers"

git checkout -q -b agent/rename-user-name-field

cat > src/serializers.py <<'PY'
def serialize_user(user):
    """The one place a user record becomes an API payload."""
    return {"id": user["id"], "full_name": user["name"], "email": user["email"]}
PY

cat > src/api.py <<'PY'
from serializers import serialize_user


def user_endpoint(user):
    body = serialize_user(user)
    return {"status": 200, "body": body, "display": body["full_name"]}
PY

git commit -qam "refactor: expose the user's name as full_name"
