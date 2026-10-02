import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi_cli.discover import get_import_data
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import auth, db, main, models
from app.routers import books, user


class StartupTests(unittest.TestCase):
    def test_fastapi_cli_discovers_application(self):
        app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        import_data = get_import_data(path=app_path)
        self.assertEqual(import_data.import_string, "app.main:app")

    def test_startup_with_shared_database_models(self):
        self.assertIs(auth.User, models.User)
        self.assertIs(auth.get_db, db.get_db)
        self.assertIs(books.Book, models.Book)
        self.assertIs(user.User, models.User)

        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        test_sessions = async_sessionmaker(test_engine, expire_on_commit=False)
        with (
            patch.object(main, "engine", test_engine),
            patch.object(db, "AsyncSessionLocal", test_sessions),
            TestClient(main.app) as client,
        ):
            schema_response = client.get("/openapi.json")
            self.assertEqual(schema_response.status_code, 200)
            self.assertIn("/api/books", schema_response.json()["paths"])
            self.assertIn("/api/users", schema_response.json()["paths"])
            self.assertIn("/api/users/me", schema_response.json()["paths"])
            self.assertIn("/api/users/token", schema_response.json()["paths"])
            self.assertEqual(client.get("/api/books").status_code, 401)
            self.assertEqual(client.get("/api/users/me").status_code, 401)
            self.assertEqual(client.post("/api/users/token").status_code, 422)


if __name__ == "__main__":
    unittest.main()