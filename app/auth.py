from functools import wraps

from flask import abort
from flask_login import LoginManager, UserMixin, current_user, login_required

from app.db import query

login_manager = LoginManager()
login_manager.login_view = 'accounts.login'


class User(UserMixin):
    def __init__(self, row):
        self.id = row['User_ID']
        self.email = row['Email']
        self.role = row['Role']
        self.customer_id = row['Customer_ID']
        self.driver_id = row['Driver_ID']


@login_manager.user_loader
def load_user(user_id):
    row = query('SELECT * FROM USER_ACCOUNT WHERE User_ID = %s', (user_id,), one=True)
    return User(row) if row else None


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
