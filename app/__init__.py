from flask import Flask, render_template
from flask_wtf import CSRFProtect

from app import config
from app.auth import login_manager
from app.db import close_db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY

    csrf.init_app(app)
    login_manager.init_app(app)
    app.teardown_appcontext(close_db)

    from app.blueprints import main, accounts, rent, assignments, returns, fleet
    for module in (main, accounts, rent, assignments, returns, fleet):
        app.register_blueprint(module.bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('shared/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('shared/error.html', code=404), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('shared/error.html', code=500), 500

    return app
