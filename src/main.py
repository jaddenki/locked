from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import hashlib
import datetime
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

RIOT_API_KEY = "RGAPI-7f976dbb-6a8b-4930-87ca-ff9b21b35b09"

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
    
    riot_id = "kiwi#rii"
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
    summoner_name, tagline = riot_id.split("#")

    account_url = f"{base_url}/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}"
    response = requests.get(account_url, headers={"X-Riot-Token": RIOT_API_KEY})

    if response.status_code != 200:
        return {"error": "dev key prob expired lol"}

    account_data = response.json()
    puuid = account_data["puuid"]

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    start = 0
    count = 20
    match_ids = []

    while True:
        match_url = f"{base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
        response = requests.get(match_url, headers={"X-Riot-Token": RIOT_API_KEY})

        if response.status_code != 200:
            return {"error": "Failed to fetch match history"}

        new_match_ids = response.json()
        if not new_match_ids:
            break

        match_ids.extend(new_match_ids)
        start += count

        match_detail_url = f"{base_url}/lol/match/v5/matches/{new_match_ids[-1]}"
        response = requests.get(match_detail_url, headers={"X-Riot-Token": RIOT_API_KEY})

        if response.status_code != 200:
            continue

        match_data = response.json()
        match_time = match_data["info"]["gameCreation"] // 1000
        match_datetime = datetime.utcfromtimestamp(match_time)

        if match_datetime < one_week_ago:
            break

    total_wins = 0
    total_losses = 0
    total_playtime = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    champions_played = []

    for match_id in match_ids:
        match_detail_url = f"{base_url}/lol/match/v5/matches/{match_id}"
        response = requests.get(match_detail_url, headers={"X-Riot-Token": RIOT_API_KEY})

        if response.status_code != 200:
            continue

        match_data = response.json()
        match_time = match_data["info"]["gameCreation"] // 1000
        match_datetime = datetime.utcfromtimestamp(match_time)

        if match_datetime < one_week_ago:
            continue

        for participant in match_data["info"]["participants"]:
            if participant["puuid"] == puuid:
                if participant["win"]:
                    total_wins += 1
                else:
                    total_losses += 1

                total_kills += participant["kills"]
                total_deaths += participant["deaths"] if participant["deaths"] > 0 else 1
                total_assists += participant["assists"]

                if participant["championName"] not in champions_played:
                    champions_played.append(participant["championName"])

                total_playtime += match_data["info"]["gameDuration"]

    win_rate = calculate_win_rate(total_wins, total_losses)

    hours = total_playtime // 3600
    minutes = (total_playtime % 3600) // 60
    kda = (total_kills + total_assists) / total_deaths if total_deaths > 0 else total_kills + total_assists
    playtime_msg = get_playtime_msg(hours)
    kda_color = get_kda_color(kda)


    return {
        "riot_username": summoner_name,
        "riot_tag": tagline,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_kills": total_kills,
        "total_deaths": total_deaths,
        "total_assists": total_assists,
        "kda": round(kda, 2),
        "kda_color": kda_color,
        "champions_played": champions_played,
        "total_playtime": f"{hours}h {minutes}m",
        "playtime_msg": playtime_msg,
        "hours_played": hours,
        "win_rate": win_rate,
    }

def get_playtime_msg(hours):
    if hours == 0:
        return "so locked in. i'm proud of you"
    elif hours < 3:
        return "not bad tbh. healthy dose of league"
    elif hours < 8:
        return "erm... could be worse?"
    elif hours < 15:
        return "it's time to touch grass"
    elif hours < 25:
        return "TAKE A SHOWER NOW"
    else:
        return "get help'"

def get_kda_color(kda):
    if kda < 1.5:
        return "red"
    elif kda < 3:
        return "orange"
    elif kda < 5:
        return "green"
    else:
        return "blue"

def calculate_win_rate(wins, losses):
    total_games = wins + losses
    if total_games == 0:
        return 0
    return round((wins / total_games) * 100, 1)

if __name__ == '__main__':
    app.run(debug=True)