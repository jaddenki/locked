# ######################################################
# Author : Jadden Picardal
# email : jpicarda@purdue.edu
# ID : ee364b17
# Date : 03/04/2025
# ######################################################

from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import hashlib
import datetime

# ######################################################
# No Module - Level Variables or Statements !
# ONLY FUNCTIONS BEYOND THIS POINT !
# ######################################################


app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('data/company.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_string(s):
    return hashlib.sha256(s.encode()).hexdigest()

# https://unogeeks.com/python-sha256/

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
    return render_template('profile.html', user_info=user_info, posts=posts, hashed_id=hashed_id)

@app.route('/<hashed_id>/create', methods=['GET', 'POST'])
def create_post(hashed_id):
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

if __name__ == '__main__':
    app.run(debug=True)