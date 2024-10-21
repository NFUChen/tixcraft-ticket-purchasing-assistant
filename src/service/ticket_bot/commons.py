from enum import Enum

from pydantic import BaseModel

class LoginCredential(BaseModel):
    """
    Remember to disable 2FA for the account you want to use to login
    """

    email: str
    password: str

class DriverKey(str, Enum):
    GOOGLE = "google"
    TIXCRAFT = "tixcraft"
