from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegistrationForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tickets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'נא להתחבר כדי לגשת לדף זה'
login_manager.login_message_category = 'info'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_staff = db.Column(db.Boolean, default=False)
    tickets = db.relationship('Ticket', backref='creator', lazy=True)

    def set_password(self, password):
        self.password = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(10), unique=True, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='פתוח')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        print(f"Login attempt for email: {form.email.data}")
        
        if user:
            print("User found")
            if user.check_password(form.password.data):
                print("Password correct")
                login_user(user, remember=form.remember.data)
                flash('התחברת בהצלחה!', 'success')
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('home'))
            else:
                print("Password incorrect")
        else:
            print("User not found")
        
        flash('אימייל או סיסמה שגויים', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('כתובת האימייל כבר קיימת במערכת', 'danger')
            return render_template('register.html', form=form)
        
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('ההרשמה הושלמה בהצלחה! כעת תוכל להתחבר', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            flash('אירעה שגיאה בתהליך ההרשמה', 'danger')
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('התנתקת בהצלחה', 'info')
    return redirect(url_for('home'))

# Routes
@app.route('/')
def home():
    print(f"User authenticated: {current_user.is_authenticated}")
    if current_user.is_authenticated:
        print(f"Current user email: {current_user.email}")
        # Get user's tickets grouped by status
        open_tickets = Ticket.query.filter_by(
            user_id=current_user.id, 
            status='פתוח'
        ).order_by(Ticket.created_at.desc()).all()
        
        in_progress_tickets = Ticket.query.filter_by(
            user_id=current_user.id, 
            status='בטיפול'
        ).order_by(Ticket.created_at.desc()).all()
        
        closed_tickets = Ticket.query.filter_by(
            user_id=current_user.id, 
            status='סגור'
        ).order_by(Ticket.created_at.desc()).limit(5).all()
        
        return render_template('home.html',
                             open_tickets=open_tickets,
                             in_progress_tickets=in_progress_tickets,
                             closed_tickets=closed_tickets)
    return render_template('home.html')

@app.route('/tickets/new', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        ticket = Ticket(
            ticket_number=f"TK{datetime.now().strftime('%Y%m%d%H%M%S')}",
            subject=request.form['subject'],
            description=request.form['description'],
            user_id=current_user.id
        )
        db.session.add(ticket)
        db.session.commit()
        flash('הקריאה נפתחה בהצלחה!', 'success')
        return redirect(url_for('my_tickets'))
    return render_template('new_ticket.html')

@app.route('/tickets/my')
@login_required
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.created_at.desc()).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/tickets/all')
@login_required
def all_tickets():
    if not current_user.is_staff:
        flash('אין לך הרשאה לצפות בכל הקריאות', 'error')
        return redirect(url_for('home'))
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return render_template('all_tickets.html', tickets=tickets)

@app.route('/tickets/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id and not current_user.is_staff:
        flash('אין לך הרשאה לצפות בקריאה זו', 'danger')
        return redirect(url_for('home'))
    return render_template('view_ticket.html', ticket=ticket)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5005)
