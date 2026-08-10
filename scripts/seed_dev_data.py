"""Seed the two household members. Safe to re-run (skips existing names)."""

from sqlmodel import Session, select

from app.db import create_db_and_tables, engine
from app.models import HouseholdMember

MEMBERS = [
    {"name": "Ben", "phone_e164": None, "email": None, "color": "#4C6FFF"},
    {"name": "Partner", "phone_e164": None, "email": None, "color": "#FF6F91"},
]


def seed() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        for member in MEMBERS:
            existing = session.exec(
                select(HouseholdMember).where(HouseholdMember.name == member["name"])
            ).first()
            if existing:
                continue
            session.add(HouseholdMember(**member))
        session.commit()
    print("Seeded household members.")


if __name__ == "__main__":
    seed()
