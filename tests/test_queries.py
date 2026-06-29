import queries


def book_titles(books):
    return {book.title for book in books}


def test_get_all_books_returns_every_book(sample_library):
    books = queries.get_all_books()

    assert book_titles(books) == {
        "Parable of the Sower",
        "Kindred",
        "The Fifth Season",
        "The Hundred Thousand Kingdoms",
    }


def test_mark_book_as_read_updates_existing_book(sample_library):
    updated = queries.mark_book_as_read("Parable of the Sower")

    assert updated is True
    books_by_title = {book.title: book for book in queries.get_all_books()}
    assert books_by_title["Parable of the Sower"].status == "read"


def test_mark_book_as_read_returns_false_for_missing_book(sample_library):
    updated = queries.mark_book_as_read("Missing Book")

    assert updated is False


def test_get_books_by_genre_returns_matching_books(sample_library):
    books = queries.get_books_by_genre("Fantasy")

    assert book_titles(books) == {
        "The Fifth Season",
        "The Hundred Thousand Kingdoms",
    }


def test_get_books_by_genre_returns_empty_list_for_unknown_genre(sample_library):
    assert queries.get_books_by_genre("Mystery") == []


def test_get_books_by_author_returns_matching_books(sample_library):
    books = queries.get_books_by_author("Octavia E. Butler")

    assert book_titles(books) == {
        "Parable of the Sower",
        "Kindred",
    }


def test_get_books_by_author_returns_empty_list_for_unknown_author(sample_library):
    assert queries.get_books_by_author("Unknown Author") == []


def test_top_rated_books_uses_default_minimum_rating(sample_library):
    books = queries.top_rated_books()

    assert book_titles(books) == {
        "Parable of the Sower",
        "Kindred",
        "The Fifth Season",
    }


def test_top_rated_books_accepts_custom_minimum_rating(sample_library):
    books = queries.top_rated_books(min_rating=5)

    assert book_titles(books) == {
        "Parable of the Sower",
        "The Fifth Season",
    }
