from py_spring import Component, BeanCollection
from typing import cast
from ddddocr import DdddOcr

class VerificationCodeDecipherBeanCollection(BeanCollection):
    @classmethod
    def create_engine(cls) -> DdddOcr:
        return DdddOcr()

class VerificationCodeDecipher(Component):
    engine: DdddOcr
    def detect_verification_code(self, img_bytes: bytes) -> str:
        return cast(str, self.engine.classification(img_bytes))
