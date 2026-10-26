from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


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


class ReturnForm(FlaskForm):
    return_date = DateField('Return date', validators=[DataRequired()])
    submit = SubmitField('Process return')


class VehicleForm(FlaskForm):
    vin = StringField('VIN', validators=[DataRequired(), Length(min=1, max=17)])
    plate_number = StringField(
        'Plate number', validators=[DataRequired(), Length(max=15)]
    )
    make = StringField('Make', validators=[DataRequired(), Length(max=50)])
    model = StringField('Model', validators=[DataRequired(), Length(max=50)])
    year = IntegerField(
        'Year', validators=[DataRequired(), NumberRange(min=1886, max=2100)]
    )
    daily_rate = DecimalField(
        'Daily rate',
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    submit = SubmitField('Save vehicle')


class InsuranceForm(FlaskForm):
    vehicle_id = SelectField('Vehicle', coerce=int, validators=[DataRequired()])
    provider = StringField('Provider', validators=[DataRequired(), Length(max=100)])
    expiry_date = DateField('Expiry date', validators=[DataRequired()])
    submit = SubmitField('Save insurance')


class MaintenanceForm(FlaskForm):
    vehicle_id = SelectField('Vehicle', coerce=int, validators=[DataRequired()])
    start_date = DateField('Start date', validators=[DataRequired()])
    end_date = DateField('Expected end date', validators=[Optional()])
    description = StringField(
        'Description', validators=[DataRequired(), Length(max=255)]
    )
    submit = SubmitField('Schedule maintenance')


class DriverForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last name', validators=[DataRequired(), Length(max=50)])
    license_number = StringField(
        'License number', validators=[DataRequired(), Length(max=30)]
    )
    submit = SubmitField('Save driver')
