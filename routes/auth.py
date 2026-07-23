from core import app, get_db, nlog, request, redirect, url_for, flash, render_template
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from security_bootstrap import User

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('accueil'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pwd   = request.form.get('password','')
        conn  = get_db()
        row   = conn.execute("SELECT id,email,password_hash FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if row and check_password_hash(row['password_hash'], pwd):
            login_user(User(row['id'], row['email']))
            nlog('info', f'Admin login {email}')
            return redirect(url_for('accueil'))
        flash('Identifiants invalides.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/users', methods=['GET','POST'])
@login_required
def admin_users():
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            em = request.form.get('email','').strip().lower()
            pw = request.form.get('password','')
            if em and pw and len(pw)>=8:
                h = generate_password_hash(pw, method='pbkdf2:sha256')
                try:
                    conn.execute("INSERT INTO users (email,password_hash) VALUES (?,?)",(em,h))
                    conn.commit(); flash('Utilisateur créé.','success')
                except Exception: flash('Email déjà utilisé.','warning')
            else: flash('Email requis + mdp 8 caractères.','warning')
        elif action == 'delete' and request.form.get('user_id'):
            conn.execute("DELETE FROM users WHERE id=?", (request.form['user_id'],))
            conn.commit(); flash('Utilisateur supprimé.','info')
    users = conn.execute("SELECT id,email,created_at FROM users").fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)
