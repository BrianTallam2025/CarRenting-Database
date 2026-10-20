from flask import Blueprint

bp = Blueprint('main', __name__)


@bp.route('/')
def landing():
    # TODO(B1/F1): render 'shared/landing.html' once F1 ships it.
    # Kept as a plain placeholder so the skeleton runs end to end.
    return '<h1>Car Rental System</h1><p>App skeleton is running.</p>'
