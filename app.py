from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import tmdb_service
import os

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    entries = db.relationship('WatchEntry', backref='user', lazy=True)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    poster_path = db.Column(db.String(255))
    release_date = db.Column(db.String(20))
    runtime = db.Column(db.Integer) # in minutes
    # Relationship to watch entries
    entries = db.relationship('WatchEntry', backref='movie', lazy=True)

class WatchEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    rating = db.Column(db.Float)
    comment = db.Column(db.Text)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
@login_required
def index():
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    user_entries = WatchEntry.query.filter_by(user_id=current_user.id)
    
    total_movies = user_entries.count()
    monthly_count = user_entries.filter(WatchEntry.watched_at >= month_ago).count()
    
    avg_rating_result = db.session.query(func.avg(WatchEntry.rating)).filter(WatchEntry.user_id == current_user.id).scalar()
    avg_rating = round(avg_rating_result, 1) if avg_rating_result else 0.0

    total_minutes_result = db.session.query(func.sum(Movie.runtime)).join(WatchEntry).filter(WatchEntry.user_id == current_user.id).scalar()
    total_hours = round((total_minutes_result or 0) / 60)
    
    entries = user_entries.order_by(WatchEntry.watched_at.desc()).all()
    
    stats = {
        'total_movies': total_movies,
        'monthly_count': monthly_count,
        'avg_rating': avg_rating,
        'total_hours': total_hours
    }
    
    return render_template('index.html', entries=entries, stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Giriş bilgilerinizi kontrol edip tekrar deneyin.')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Bu e-posta adresi zaten kullanılıyor.')
            return redirect(url_for('signup'))
        
        new_user = User(email=email, name=name, password_hash=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/search')
@login_required
def search():
    query = request.args.get('q')
    if query:
        results = tmdb_service.search_movies(query)
        return render_template('add_movie.html', results=results, search_query=query)
    return render_template('add_movie.html', results=[], search_query='')

@app.route('/add/<int:tmdb_id>', methods=['GET', 'POST'])
@login_required
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
                release_date=details.get('release_date'),
                runtime=details.get('runtime')
            )
            db.session.add(movie)
            db.session.commit()
    
    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        watched_at_str = request.form.get('watched_at')
        
        watched_at = datetime.strptime(watched_at_str, '%Y-%m-%d') if watched_at_str else datetime.utcnow()

        entry = WatchEntry(
            user_id=current_user.id,
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
