import datetime
import uuid
from py_spring_model import PySpringModel
from sqlmodel import Field

from src.repository.common import LoginTokenRead


class LoginToken(PySpringModel, table=True):
    __tablename__: str = "login_token"
    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    token: str
    email: str
    expired_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now() + datetime.timedelta(hours=6)
    )

    def as_read(self) -> LoginTokenRead:
        return LoginTokenRead(
            id=self.id, token=self.token, email=self.email, expired_at=self.expired_at
        )
