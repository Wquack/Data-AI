from sqlalchemy import Column, Integer, String
from utils.db import Base

class User(Base):
    __tablename__ = "users"

<<<<<<< HEAD
    id = Column(Integer, primary_key=True, index=True)  # type: ignore
    email = Column(String, unique=True, index=True, nullable=False)  # type: ignore
    password_hash = Column(String, nullable=False)  # type: ignore
=======
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    def __repr__(self):
        return f"<User(email={self.email})>"
>>>>>>> 8d73dd69d899bcdfd05e62c74345dc04d083c366
