from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import queries
from orm import Author, Base, Book, Genre


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    yield TestingSession

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch, session_factory):
    @contextmanager
    def test_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(queries, "get_session", test_session)


@pytest.fixture
def sample_library(session_factory):
    session = session_factory()

    octavia_butler = Author(name="Octavia E. Butler", country="USA")
    nk_jemisin = Author(name="N.K. Jemisin", country="USA")

    science_fiction = Genre(name="Science Fiction")
    fantasy = Genre(name="Fantasy")

    session.add_all(
        [
            Book(
                title="Parable of the Sower",
                author=octavia_butler,
                published_year=1993,
                status="unread",
                rating=5,
                genres=[science_fiction],
            ),
            Book(
                title="Kindred",
                author=octavia_butler,
                published_year=1979,
                status="read",
                rating=4,
                genres=[science_fiction],
            ),
            Book(
                title="The Fifth Season",
                author=nk_jemisin,
                published_year=2015,
                status="read",
                rating=5,
                genres=[science_fiction, fantasy],
            ),
            Book(
                title="The Hundred Thousand Kingdoms",
                author=nk_jemisin,
                published_year=2010,
                status="unread",
                rating=3,
                genres=[fantasy],
            ),
        ]
    )
    session.commit()
    session.close()
