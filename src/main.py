from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import hashlib
import datetime
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

RIOT_API_KEY = "RGAPI-562dcb9e-3edb-45f6-b812-41a8b6698bad"

def get_db_connection():
    conn = sqlite3.connect('data/company.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_string(s):
    return hashlib.sha256(s.encode()).hexdigest()

@app.route('/', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            hashed_id = hash_string(username + password)
            return redirect(url_for('profile', hashed_id=hashed_id))
        
        hashed_id = hash_string(username + password)
        conn.execute('INSERT INTO users (username, password, hashed_id) VALUES (?, ?, ?)',
                     (username, password, hashed_id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('signup', hashed_id=hashed_id))
    
    return render_template('register.html')

@app.route('/signup/<hashed_id>', methods=['GET', 'POST'])
@app.route('/signup/<hashed_id>', methods=['GET', 'POST'])
def signup(hashed_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE hashed_id = ?', (hashed_id,)).fetchone()
    
    if not user:
        conn.close()
        return "User not found", 404 
    
    user_info = conn.execute('SELECT * FROM user_info WHERE user_id = ?', (user['id'],)).fetchone()
    
    if user_info:
        conn.close()
        return redirect(url_for('profile', hashed_id=hashed_id))
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        
        conn.execute('INSERT INTO user_info (first_name, last_name, email, user_id) VALUES (?, ?, ?, ?)',
                     (first_name, last_name, email, user['id']))
        conn.commit()
        conn.close()
        return redirect(url_for('profile', hashed_id=hashed_id))
    
    conn.close()
    return render_template('signup.html', hashed_id=hashed_id)


@app.route('/<hashed_id>/profile')
def profile(hashed_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE hashed_id = ?', (hashed_id,)).fetchone()
    user_info = conn.execute('SELECT * FROM user_info WHERE user_id = ?', (user['id'],)).fetchone()
    posts = conn.execute('SELECT * FROM posts WHERE user_id = ? ORDER BY timestamp DESC', (user['id'],)).fetchall()
    conn.close()
    
    riot_id = "qqiangi#NA1"
    match_stats = get_match_stats(riot_id)
    
    return render_template('profile.html', user_info=user_info, posts=posts, hashed_id=hashed_id, match_stats=match_stats)


@app.route('/<hashed_id>/create', methods=['GET', 'POST'])
def create_post(hashed_id):
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        post_id = hash_string(title + timestamp)
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE hashed_id = ?', (hashed_id,)).fetchone()
        
        if user:
            conn.execute('INSERT INTO posts (title, content, timestamp, user_id) VALUES (?, ?, ?, ?)',
                         (title, content, timestamp, user['id']))
            conn.commit()
        
        conn.close()
        return redirect(url_for('profile', hashed_id=hashed_id))
    
    return render_template('create_post.html', hashed_id=hashed_id)

@app.route('/posts/<post_id>')
def view_post(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (post['user_id'],)).fetchone()
    conn.close()
    return render_template('view_post.html', post=post, username=user['username'])

@app.route('/delete_post/<post_id>/<hashed_id>', methods=['POST'])
def delete_post(post_id, hashed_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('profile', hashed_id=hashed_id))

def get_match_stats(riot_id):
    base_url = "https://americas.api.riotgames.com"

    try:
        summoner_name, tagline = riot_id.split("#")
        account_url = f"{base_url}/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}"
        response = requests.get(account_url, headers={"X-Riot-Token": RIOT_API_KEY})

        if response.status_code != 200:
            return {"error": "Failed to fetch account data (Check Riot ID format)"}

        account_data = response.json()
        puuid = account_data["puuid"]

        match_url = f"{base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=100"
        response = requests.get(match_url, headers={"X-Riot-Token": RIOT_API_KEY})

        if response.status_code != 200:
            return {"error": "Failed to fetch match history"}

        match_ids = response.json()
        if not match_ids:
            return {"error": "No matches found"}

        total_wins = 0
        total_losses = 0
        total_playtime = 0
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        for match_id in match_ids:
            match_detail_url = f"{base_url}/lol/match/v5/matches/{match_id}"
            response = requests.get(match_detail_url, headers={"X-Riot-Token": RIOT_API_KEY})

            if response.status_code != 200:
                continue

            match_data = response.json()
            match_time = match_data["info"]["gameCreation"] // 1000
            match_datetime = datetime.utcfromtimestamp(match_time)

            if match_datetime < one_week_ago:
                break

            for participant in match_data["info"]["participants"]:
                if participant["puuid"] == puuid:
                    if participant["win"]:
                        total_wins += 1
                    else:
                        total_losses += 1

                    total_playtime += match_data["info"]["gameDuration"]

        hours = total_playtime // 3600
        minutes = (total_playtime % 3600) // 60

        return {
            "riot_username": summoner_name, 
            "riot_tagline": tagline,     
            "total_wins": total_wins,
            "total_losses": total_losses,
            "total_playtime": f"{hours}h {minutes}m"
        }

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


if __name__ == '__main__':
    app.run(debug=True)