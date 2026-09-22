"""Mark a user as admin (Sprint 03 task 8). An admin is a user with a flag, not a separate login.

Usage (from the project root):
    python -m scripts.make_admin "+993 61 234567"
    python -m scripts.make_admin "+993 61 234567" --revoke

The number goes through the same normalisation as the login form. The user must already
exist, i.e. have logged in once, so a typo cannot create an admin account nobody owns.
"""
from __future__ import annotations

import argparse
import sys

from app.db import connect
from app.phone import InvalidPhone, normalize_phone


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phone")
    parser.add_argument("--revoke", action="store_true", help="remove the admin flag instead")
    args = parser.parse_args()

    try:
        phone = normalize_phone(args.phone)
    except InvalidPhone as exc:
        print(exc.message, file=sys.stderr)
        return 1

    conn = connect()
    try:
        updated = conn.execute(
            "UPDATE users SET is_admin = ? WHERE phone = ?", (0 if args.revoke else 1, phone)
        ).rowcount
        conn.commit()
    finally:
        conn.close()

    if not updated:
        print(f"No user with phone {phone}. Log in with it once first.", file=sys.stderr)
        return 1
    print(f"{phone} is {'no longer' if args.revoke else 'now'} an admin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
