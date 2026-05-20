from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_required, login_user, logout_user, current_user
from . import bp as auth  # import package blueprint and alias it to `auth`
from app import db
from .models import User
from app.auth.models import User
from werkzeug.security import generate_password_hash, check_password_hash


@auth.before_request
def _auth_ui_thai():
    """로그인·회원가입 화면 라벨 기본 태국어"""
    if request.endpoint in ('auth.login', 'auth.signup'):
        session['language'] = 'th'


# 로그인
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # SQLAlchemy로 User 객체 조회
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = getattr(user, 'role', None)  # role 필드가 있다면
            return redirect(url_for('home'))
        else:
            flash('auth_invalid_credentials')
    
    return render_template('auth/login.html')

# 로그아웃
@auth.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

# 회원가입
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        # SQLAlchemy로 중복 확인 및 생성
        if User.query.filter_by(username=username).first():
            flash('auth_username_exists')
            return redirect(url_for('auth.signup'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()
        flash('auth_registration_success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/signup.html')

# 회원관리
@auth.route('/user_manage')
@login_required
def user_manage():
    users = User.query.all()
    return render_template('auth/user_manage.html', users=users)

# 프로필 관리
@auth.route('/user_profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        user = current_user
        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect')
            return redirect(url_for('auth.user_profile'))
        if new_password != confirm_password:
            flash('New passwords do not match')
            return redirect(url_for('auth.user_profile'))
        user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password updated successfully')
        return redirect(url_for('auth.user_profile'))
    return render_template('auth/user_profile.html')
