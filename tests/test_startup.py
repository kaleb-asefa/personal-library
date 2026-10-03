import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

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

    def test_public_pages_include_ui_dependencies(self):
        client = TestClient(main.app)
        for path in ("/", "/login", "/users/new"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('id="page-content" class="page-shell"', response.text)
                self.assertIn('class="app-nav"', response.text)
                self.assertIn('id="route-loader"', response.text)
                self.assertIn("/static/js/forms.js", response.text)
                self.assertNotIn('class="nav-login"', response.text)
        self.assertEqual(client.get("/static/profile/default.png").status_code, 200)
        self.assertIn('href="/users/new">Sign up', client.get("/login").text)

    def test_password_recovery_pages_and_api_flow(self):
        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        test_sessions = async_sessionmaker(test_engine, expire_on_commit=False)
        with (
            patch.object(main, "engine", test_engine),
            patch.object(db, "AsyncSessionLocal", test_sessions),
            patch.object(user, "send_password_reset_email", new_callable=AsyncMock) as send_email,
            TestClient(main.app) as client,
        ):
            forgot_page = client.get("/forgot-password")
            self.assertEqual(forgot_page.status_code, 200)
            self.assertIn('data-api-form="forgot-password"', forgot_page.text)
            self.assertIn("/static/js/forms.js", forgot_page.text)

            reset_page = client.get("/reset-password?token=preview-token")
            self.assertEqual(reset_page.status_code, 200)
            self.assertIn('name="token" value="preview-token"', reset_page.text)

            register_response = client.post(
                "/api/users",
                json={
                    "username": "reset-reader",
                    "email": "reset-reader@example.com",
                    "password": "old-password-123",
                },
            )
            self.assertEqual(register_response.status_code, 201)

            forgot_response = client.post(
                "/api/users/forgot-password",
                json={"email": "reset-reader@example.com"},
            )
            self.assertEqual(forgot_response.status_code, 204)
            send_email.assert_awaited_once()
            raw_token = send_email.await_args.args[2]

            reset_response = client.post(
                "/api/users/reset-password",
                json={"token": raw_token, "new_password": "new-password-456"},
            )
            self.assertEqual(reset_response.status_code, 200)

            old_password_login = client.post(
                "/api/users/token",
                data={"username": "reset-reader@example.com", "password": "old-password-123"},
            )
            new_password_login = client.post(
                "/api/users/token",
                data={"username": "reset-reader@example.com", "password": "new-password-456"},
            )
            self.assertEqual(old_password_login.status_code, 401)
            self.assertEqual(new_password_login.status_code, 200)

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
            self.assertEqual(client.get("/users/me", follow_redirects=False).status_code, 303)
            self.assertEqual(client.get("/users/me/edit", follow_redirects=False).status_code, 303)
            self.assertEqual(client.post("/users/me/edit").status_code, 401)
            self.assertEqual(client.post("/users/me/delete").status_code, 401)

            profile_routes = [
                route for route in main.app.routes
                if getattr(route, "path", "").startswith("/users/me")
            ]
            self.assertTrue(profile_routes)
            self.assertTrue(all(route.endpoint.__module__ == "app.main" for route in profile_routes))

    def test_user_api_with_existing_database_schema(self):
        password = "legacy-test-password"
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "CREATE TABLE users (user_id INTEGER PRIMARY KEY, "
                    "username VARCHAR NOT NULL UNIQUE, email VARCHAR NOT NULL UNIQUE, "
                    "password_hash VARCHAR(200) NOT NULL, image_file VARCHAR)"
                )
                connection.execute(
                    "CREATE TABLE books (book_id INTEGER PRIMARY KEY, title VARCHAR, "
                    "author_id INTEGER, published_year INTEGER, status VARCHAR(6), "
                    "rating INTEGER, user_id INTEGER)"
                )
                connection.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                    (1, "legacy-reader", "legacy@example.com", auth.hash_password(password), "existing.png"),
                )

            test_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
            test_sessions = async_sessionmaker(test_engine, expire_on_commit=False)
            with (
                patch.object(main, "engine", test_engine),
                patch.object(db, "AsyncSessionLocal", test_sessions),
                TestClient(main.app) as client,
            ):
                with sqlite3.connect(database_path) as connection:
                    connection.execute("INSERT INTO authors (author_id, name, country) VALUES (1, 'Test Author', 'Test Country')")
                    connection.execute(
                        "INSERT INTO books VALUES (1, 'Visible Shelf Book', 1, 2020, 'unread', 0, 1)"
                    )
                login_response = client.post(
                    "/api/users/token",
                    data={"username": "legacy@example.com", "password": password},
                )
                self.assertEqual(login_response.status_code, 200)
                self.assertIn("access_token", login_response.json())

                profile_response = client.get("/api/users/me")
                self.assertEqual(profile_response.status_code, 200)
                self.assertEqual(profile_response.json()["user_id"], 1)
                self.assertEqual(profile_response.json()["image_file"], "existing.png")
                self.assertEqual(profile_response.json()["image_path"], "/media/profile/existing.png")

                books_response = client.get("/api/users/1/books")
                self.assertEqual(books_response.status_code, 200)
                self.assertEqual(books_response.json()["total"], 1)

                page_markers = {
                    "/users/1/books": "Visible Shelf Book",
                    "/books/new": 'name="genre_names"',
                    "/books/1": 'aria-label="Book actions"',
                    "/books/1/edit": "Visible Shelf Book",
                    "/users/1/edit": 'data-api-form="update-user-picture"',
                }
                for path, marker in page_markers.items():
                    with self.subTest(path=path):
                        page_response = client.get(path)
                        self.assertEqual(page_response.status_code, 200)
                        self.assertIn(marker, page_response.text)
                        self.assertIn("/static/js/forms.js", page_response.text)

                create_response = client.post(
                    "/api/users",
                    json={"username": "new-reader", "email": "new@example.com", "password": password},
                )
                self.assertEqual(create_response.status_code, 201)
                self.assertIsNone(create_response.json()["image_file"])

            with sqlite3.connect(database_path) as connection:
                self.assertIn(
                    "password_reset_tokens",
                    {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                )
                self.assertEqual(connection.execute("SELECT count(*) FROM users").fetchone()[0], 2)
                columns = {column[1] for column in connection.execute("PRAGMA table_info(users)")}
                self.assertNotIn("created_at", columns)


if __name__ == "__main__":
    unittest.main()