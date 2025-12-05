import os

basedir = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = 'dev'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'movies.db')
TMDB_API_KEY = '' 
