from typing import Optional
from uuid import UUID
from py_spring_model import CrudRepository

from src.repository.common import LoginTokenRead
from src.repository.models import LoginToken


class LoginTokenRepository(CrudRepository[UUID, LoginToken]):
    def get_token_by_email(self, email: str) -> Optional[LoginTokenRead]:
        _, optional_token = self._find_by_query({"email": email})
        if optional_token is None:
            return
        return optional_token.as_read()

    def save_token(self, token: LoginToken) -> LoginTokenRead:
        return self.upsert(token, {"email": token.email}).as_read()
