from flask import Blueprint, render_template

login_bp = Blueprint(
    'login',
    __name__,
    static_folder='../templates',
    static_url_path='/assets'
)

@login_bp.route('/login')
def login():
    return render_template('login.html')

@login_bp.route('/signup')
def signup():
    return render_template('signUp.html')

@login_bp.route('/forgot-password')
def forgot_password():
    return render_template('forgotPassword.html')