from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import tmdb_service

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)

# Models
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    poster_path = db.Column(db.String(255))
    release_date = db.Column(db.String(20))
    # Relationship to watch entries
    entries = db.relationship('WatchEntry', backref='movie', lazy=True)

class WatchEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    rating = db.Column(db.Float)
    comment = db.Column(db.Text)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'movie_title': self.movie.title,
            'rating': self.rating,
            'comment': self.comment,
            'watched_at': self.watched_at.strftime('%Y-%m-%d')
        }

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    weekly_count = WatchEntry.query.filter(WatchEntry.watched_at >= week_ago).count()
    monthly_count = WatchEntry.query.filter(WatchEntry.watched_at >= month_ago).count()
    yearly_count = WatchEntry.query.filter(WatchEntry.watched_at >= year_ago).count()
    
    entries = WatchEntry.query.order_by(WatchEntry.watched_at.desc()).all()
    
    trends = {
        'weekly': weekly_count,
        'monthly': monthly_count,
        'yearly': yearly_count
    }
    
    return render_template('index.html', entries=entries, trends=trends)

@app.route('/search')
def search():
    query = request.args.get('q')
    if query:
        results = tmdb_service.search_movies(query)
        return render_template('add_movie.html', results=results, search_query=query)
    return render_template('add_movie.html', results=[], search_query='')

@app.route('/add/<int:tmdb_id>', methods=['GET', 'POST'])
def add_movie_entry(tmdb_id):
    # Check if movie exists in our DB, if not fetch from TMDB and save
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
    
    if not movie:
        details = tmdb_service.get_movie_details(tmdb_id)
        if details:
            movie = Movie(
                tmdb_id=details['id'],
                title=details['title'],
                poster_path=details.get('poster_path'),
                release_date=details.get('release_date')
            )
            db.session.add(movie)
            db.session.commit()
    
    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        watched_at_str = request.form.get('watched_at')
        
        watched_at = datetime.strptime(watched_at_str, '%Y-%m-%d') if watched_at_str else datetime.utcnow()

        entry = WatchEntry(
            movie_id=movie.id,
            rating=float(rating) if rating else None,
            comment=comment,
            watched_at=watched_at
        )
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('movie_detail.html', movie=movie)

if __name__ == '__main__':
    app.run(debug=True)
