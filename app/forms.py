from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')


class RegisterForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last name', validators=[DataRequired(), Length(max=50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    national_id = StringField('National ID', validators=[DataRequired(), Length(max=20)])
    license_number = StringField('License number', validators=[DataRequired(), Length(max=30)])
    license_expiry = DateField('License expiry', validators=[DataRequired()])
    submit = SubmitField('Register')


class RentForm(FlaskForm):
    start_date = DateField('Start date', validators=[DataRequired()])
    end_date = DateField('End date', validators=[DataRequired()])
    is_chauffeur = BooleanField('With a chauffeur')
    submit = SubmitField('Rent')
