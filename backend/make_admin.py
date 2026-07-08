"""
Promote an existing user to admin from the command line.

The signup flow never creates admins — that's deliberate, so a stranger
can't sign up and grant themselves dashboard access. Run this script
locally (you need direct access to the database file/server) to make
yourself, or someone else, an admin.

Usage:
    python make_admin.py you@example.com
"""

import sys

from database import SessionLocal
import models


def make_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"No account found for {email}. They need to sign up first.")
            return
        if user.is_admin:
            print(f"{email} is already an admin.")
            return
        user.is_admin = True
        db.commit()
        print(f"{email} is now an admin. Log out and back in for it to take effect in the UI.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py you@example.com")
        sys.exit(1)
    make_admin(sys.argv[1])
