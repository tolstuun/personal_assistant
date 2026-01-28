"""
Tests for PostgreSQL storage.

Requires docker-compose postgres service to be running.
Run: docker-compose up -d postgres
"""

import pytest
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.future import select

from src.core.storage.postgres import Base, Database


class TestUser(Base):
    """Test model for database tests."""

    __tablename__ = "test_users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)


@pytest.mark.asyncio
async def test_database_connection(database: Database) -> None:
    """Test that database connects successfully."""
    assert await database.health_check() is True


@pytest.mark.asyncio
async def test_database_session_query(database: Database) -> None:
    """Test executing a simple query."""
    async with database.session() as session:
        result = await session.execute(text("SELECT 1 as num"))
        row = result.scalar()
        assert row == 1


@pytest.mark.asyncio
async def test_database_create_tables(database: Database) -> None:
    """Test creating and dropping tables."""
    # Create tables
    await database.create_tables()

    # Verify table exists by querying it
    async with database.session() as session:
        result = await session.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'test_users')")
        )
        exists = result.scalar()
        assert exists is True

    # Clean up
    await database.drop_tables()


@pytest.mark.asyncio
async def test_database_crud_operations(database: Database) -> None:
    """Test basic CRUD operations with ORM."""
    # Create tables
    await database.create_tables()

    try:
        # Create
        async with database.session() as session:
            user = TestUser(name="John Doe", email="john@example.com")
            session.add(user)
            await session.flush()
            user_id = user.id

        # Read
        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.id == user_id)
            )
            user = result.scalar_one()
            assert user.name == "John Doe"
            assert user.email == "john@example.com"

        # Update
        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.id == user_id)
            )
            user = result.scalar_one()
            user.name = "Jane Doe"

        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.id == user_id)
            )
            user = result.scalar_one()
            assert user.name == "Jane Doe"

        # Delete
        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.id == user_id)
            )
            user = result.scalar_one()
            await session.delete(user)

        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.id == user_id)
            )
            user = result.scalar_one_or_none()
            assert user is None

    finally:
        # Clean up
        await database.drop_tables()


@pytest.mark.asyncio
async def test_database_transaction_rollback(database: Database) -> None:
    """Test that failed transactions are rolled back."""
    await database.create_tables()

    try:
        # Try to create duplicate email (should fail)
        async with database.session() as session:
            user1 = TestUser(name="User 1", email="same@example.com")
            session.add(user1)

        with pytest.raises(Exception):
            async with database.session() as session:
                user2 = TestUser(name="User 2", email="same@example.com")
                session.add(user2)

        # Verify only first user exists
        async with database.session() as session:
            result = await session.execute(
                select(TestUser).where(TestUser.email == "same@example.com")
            )
            users = result.scalars().all()
            assert len(users) == 1
            assert users[0].name == "User 1"

    finally:
        await database.drop_tables()
