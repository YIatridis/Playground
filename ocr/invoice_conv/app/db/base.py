# Import all the models, so that Base has them before being imported by Alembic
from app.db.session import Base  # noqa
from app.models.user import User  # noqa
from app.models.subscription import Subscription  # noqa
from app.models.scan import Scan  # noqa
