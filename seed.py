from orm import Base, Book, Author, Genre, get_db_session, engine, User

test_user = User(username='testuser', email='test@gmail.com', password='testpassword', image_file='default.jpg')


frank_herbert = Author(name='Frank Herbert', country='USA')
chimamanda_ngozi_adichie = Author(name='Chimamanda Ngozi Adichie', country='Nigeria')
haruki_murakami = Author(name='Haruki Murakami', country='Japan')
gabriel_garcia_marquez = Author(name='Gabriel García Márquez', country='Colombia')
ursula_k_le_guin = Author(name='Ursula K. Le Guin', country='USA')
dostoevsky = Author(name='Dostoevsky', country='Russia')
toni_morrison = Author(name='Toni Morrison', country='USA')
kazuo_ishiguro = Author(name='Kazuo Ishiguro', country='UK')
nk_jemisin = Author(name='N.K. Jemisin', country='USA')
chinua_achebe = Author(name='Chinua Achebe', country='Nigeria') 



science_fiction = Genre(name='Science Fiction')
literary_fiction = Genre(name='Literary Fiction')
historical_fiction = Genre(name='Historical Fiction')
fantasy = Genre(name='Fantasy')
magical_realism = Genre(name='Magical Realism')
dystopian = Genre(name='Dystopian')
psychological_fiction = Genre(name='Psychological Fiction')
postcolonial = Genre(name='Postcolonial')
mystery = Genre(name='Mystery')
speculative_fiction = Genre(name='Speculative Fiction')





dune = Book(title='Dune', author=frank_herbert, published_year=1965, status='read', rating=5, genres=[science_fiction, fantasy], user=test_user)
half_of_a_yellow_sun = Book(title='Half of a Yellow Sun', author=chimamanda_ngozi_adichie, published_year=2006, status='read', rating=4, genres=[literary_fiction, historical_fiction], user=test_user)
norwegian_wood = Book(title='Norwegian Wood', author=haruki_murakami, published_year=1987, status='read', rating=4, genres=[literary_fiction, psychological_fiction], user=test_user)
one_hundred_years_of_solitude = Book(title='One Hundred Years of Solitude', author=gabriel_garcia_marquez, published_year=1967, status='read', rating=5, genres=[magical_realism, literary_fiction], user=test_user)
the_left_hand_of_darkness = Book(title='The Left Hand of Darkness', author=ursula_k_le_guin, published_year=1969, status='read', rating=4, genres=[science_fiction, fantasy], user=test_user)
crime_and_punishment = Book(title='Crime and Punishment', author=dostoevsky, published_year=1866, status='read', rating=5, genres=[psychological_fiction, literary_fiction], user=test_user)
beloved = Book(title='Beloved', author=toni_morrison, published_year=1987, status='read', rating=5, genres=[historical_fiction, literary_fiction], user=test_user)
never_let_me_go = Book(title='Never Let Me Go', author=kazuo_ishiguro, published_year=2005, status='read', rating=4, genres=[dystopian, literary_fiction], user=test_user)
the_fifth_season = Book(title='The Fifth Season', author=nk_jemisin, published_year=2015, status='read', rating=5, genres=[science_fiction, fantasy, speculative_fiction], user=test_user)
things_fall_apart = Book(title='Things Fall Apart', author=chinua_achebe, published_year=1958, status='read', rating=5, genres=[postcolonial, historical_fiction], user=test_user)





with get_db_session() as session:
    session.add_all([
        frank_herbert, chimamanda_ngozi_adichie, haruki_murakami, gabriel_garcia_marquez,
        ursula_k_le_guin, dostoevsky, toni_morrison, kazuo_ishiguro, nk_jemisin, chinua_achebe,
        science_fiction, literary_fiction, historical_fiction, fantasy, magical_realism,
        dystopian, psychological_fiction, postcolonial, mystery, speculative_fiction,
        dune, half_of_a_yellow_sun, norwegian_wood, one_hundred_years_of_solitude,
        the_left_hand_of_darkness, crime_and_punishment, beloved, never_let_me_go,
        the_fifth_season, things_fall_apart
    ])