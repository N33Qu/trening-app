from flask_babel import gettext
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase

from .i18n import N_


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = N_("Zaloguj się, aby zobaczyć tę stronę.")
login_manager.localize_callback = gettext
login_manager.login_message_category = "info"
login_manager.session_protection = "basic"
