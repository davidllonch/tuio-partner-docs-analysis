#!/usr/bin/env python
"""
Create an analyst account.

Usage:
    python create_analyst.py email@example.com "Full Name" password123

This script is run once (or as needed) to create the initial analyst login.
Think of it as adding the first user to the system — you need at least one
analyst account before anyone can log in to review submissions.

Requirements:
    - The DATABASE_URL environment variable must be set (or a .env file must exist)
    - The database must already exist and have the tables created (run alembic first)
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

# Ensure the app package is importable when running from the backend/ directory
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.analyst import Analyst
from app.auth.jwt import hash_password


async def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python create_analyst.py <email> <full_name> <password>")
        print('Example: python create_analyst.py admin@tuio.com "Ana García" MySecurePass123')
        sys.exit(1)

    email = sys.argv[1]
    full_name = sys.argv[2]
    password = sys.argv[3]

    # Basic validation
    if "@" not in email:
        print(f"Error: '{email}' does not look like a valid email address")
        sys.exit(1)

    if len(password) < 8:
        print("Error: password must be at least 8 characters long")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        # Check if an analyst with this email already exists
        result = await session.execute(select(Analyst).where(Analyst.email == email))
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"Error: an analyst with email '{email}' already exists")
            sys.exit(1)

        analyst = Analyst(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(analyst)
        await session.commit()

        print(f"Analyst created successfully:")
        print(f"  Email:     {email}")
        print(f"  Full name: {full_name}")
        print(f"  ID:        {analyst.id}")
        print(f"  Active:    {analyst.is_active}")


if __name__ == "__main__":
    asyncio.run(main())
