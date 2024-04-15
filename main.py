import decimal
from flask import Flask, render_template, url_for, redirect, flash, request
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from flask_wtf import FlaskForm
from wtforms import (StringField, EmailField, PasswordField, SubmitField, URLField, BooleanField,
                     SelectField, DecimalField)
from wtforms.validators import DataRequired, Length, NumberRange
from flask_bootstrap import Bootstrap5
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from urllib.parse import quote
from flask_wtf.csrf import CSRFProtect

load_dotenv()
MAPS_API_KEY = os.getenv("MAPS_API_KEY")


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
login_manager.login_view = 'login'

# create the app
app = Flask(__name__)

SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY

# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cafes.db"
app.config['BOOTSTRAP_BTN_STYLE'] = 'dark'

# initialize the app with the extension
db.init_app(app)
login_manager.init_app(app)
bootstrap = Bootstrap5(app)
csrf = CSRFProtect(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one()


class Cafe(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250), unique=True)
    map_url: Mapped[str] = mapped_column(String(500))
    img_url: Mapped[str] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(250))
    has_sockets: Mapped[bool]
    has_toilet: Mapped[bool]
    has_wifi: Mapped[bool]
    can_take_calls: Mapped[bool]
    seats: Mapped[str] = mapped_column(String(250), nullable=True)
    coffee_price: Mapped[str] = mapped_column(String(250), nullable=True)


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    name: Mapped[str]


class SignupForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Signup")


class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Login")


class AddCafeForm(FlaskForm):
    seat_choices = [('0-10', '0-10'), ('10-20', '10-20'), ('20-30', '20-30'), ('30-40', '30-40'),
                    ('40-50', '40-50'), ('50+', '50+')]
    name = StringField('Name', validators=[DataRequired()])
    map_url = URLField('Map URL', validators=[DataRequired()])
    img_url = URLField('Image URL', validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired()])
    has_sockets = BooleanField('Has power sockets')
    has_wifi = BooleanField('Has WiFi')
    can_take_calls = BooleanField('Can take calls')
    has_toilet = BooleanField('Has toilet')
    seats = SelectField("How many seats", choices=seat_choices)
    coffee_price = DecimalField("Coffee price (£)", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Add cafe')

    def populate_obj(self, obj: Cafe):
        obj.name = self.name.data
        obj.map_url = self.map_url.data
        obj.img_url = self.img_url.data
        obj.location = self.location.data
        obj.has_sockets = self.has_sockets.data
        obj.has_toilet = self.has_toilet.data
        obj.has_wifi = self.has_wifi.data
        obj.can_take_calls = self.can_take_calls.data
        obj.seats = self.seats.data
        obj.coffee_price = "£{:.2f}".format(self.coffee_price.data)

    def prefill_form(self, cafe: Cafe):
        self.name.data = cafe.name
        self.map_url.data = cafe.map_url
        self.img_url.data = cafe.img_url
        self.location.data = cafe.location
        self.has_sockets.data = cafe.has_sockets
        self.has_toilet.data = cafe.has_toilet
        self.has_wifi.data = cafe.has_wifi
        self.can_take_calls.data = cafe.can_take_calls
        self.seats.data = cafe.seats
        self.coffee_price.data = decimal.Decimal(str(cafe.coffee_price).replace('£', ''))


class DeleteCafeForm(FlaskForm):
    submit_delete = SubmitField("Delete")
    submit_cancel = SubmitField("Cancel")


class EditProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField("Apply changes")


@app.route("/")
def index():
    cafes = db.session.execute(db.select(Cafe)).scalars()
    return render_template('index.html', cafes=cafes)


@app.route('/cafe/<int:cafe_id>')
def show_cafe(cafe_id):
    cafe = db.get_or_404(Cafe, cafe_id)
    search_query = quote(','.join((cafe.name, cafe.location)))
    return render_template('cafe.html', cafe=cafe, MAPS_API_KEY=MAPS_API_KEY,
                           search_query=search_query)


@app.route('/cafe/add', methods=['GET', 'POST'])
@login_required
def add_cafe():
    form = AddCafeForm()
    if form.validate_on_submit():
        cafe = Cafe()
        form.populate_obj(cafe)
        db.session.add(cafe)
        db.session.commit()
        return redirect(url_for('show_cafe', cafe_id=cafe.id))

    return render_template('form.html', heading="Add cafe", form=form,
                           action=url_for('add_cafe'))


@app.route('/cafe/<int:cafe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cafe(cafe_id):
    cafe = db.get_or_404(Cafe, cafe_id)
    form = AddCafeForm()
    form.submit.label.text = "Apply changes"

    if request.method == "GET":
        form.prefill_form(cafe)

    if form.validate_on_submit():
        form.populate_obj(cafe)
        db.session.commit()
        return redirect(url_for('show_cafe', cafe_id=cafe.id))

    return render_template('form.html', heading="Edit cafe", form=form,
                           action=url_for('edit_cafe', cafe_id=cafe_id))


@app.route('/cafe/<int:cafe_id>/delete', methods=['GET', 'POST'])
@login_required
def delete_cafe(cafe_id):
    cafe = db.get_or_404(Cafe, cafe_id)
    form = DeleteCafeForm()
    if form.validate_on_submit():
        if form.submit_delete.data:
            db.session.delete(cafe)
            db.session.commit()
            return redirect(url_for('index'))
        elif form.submit_cancel.data:
            return redirect(url_for('show_cafe', cafe_id=cafe_id))
    heading = f'Delete cafe "{cafe.name}"?'
    return render_template('form.html', heading="Delete cafe", form=form,
                           action=url_for('delete_cafe', cafe_id=cafe_id))


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user: User = current_user
    form = EditProfileForm()
    if form.validate_on_submit():
        user.name = form.name.data
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('form.html', heading="Edit name", form=form,
                           action=url_for('edit_profile'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # check if user with same email exists
        same_user = db.session.execute(db.select(User).filter_by(email=form.email.data)).scalar()
        if same_user:
            flash("User with this email already exists", category='danger')
            return redirect(url_for('signup'))

        # if user with this email does not exist we add one
        user = User()
        user.email = form.email.data
        user.name = form.name.data
        user.password_hash = generate_password_hash(form.password.data)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('form.html', heading="Signup", form=form, action=url_for('signup'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')
    form = LoginForm()
    if form.validate_on_submit():
        user: User = db.session.execute(db.select(User).filter_by(email=form.email.data)).scalar()
        if not user:
            flash("User with this email does not exist", category="danger")
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            if next_page is not None:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash("Password is incorrect", category='danger')


    return render_template('form.html', heading="Login", form=form,
                           action=url_for('login', next=next_page))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(request.referrer)


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()

