from py_spring_core import Properties
import datetime
import uuid
from pydantic import BaseModel, computed_field


class TixcraftApiSource(Properties):
    __key__: str = "tixcraft_api"
    google_login_url: str


class LoginTokenRead(BaseModel):
    id: uuid.UUID
    token: str
    email: str
    expired_at: datetime.datetime

    @computed_field
    @property
    def is_expired(self) -> bool:
        return self.expired_at < datetime.datetime.now()
