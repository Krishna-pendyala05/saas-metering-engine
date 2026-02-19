from .user import User, UserBase, UserCreate, Token, TokenPayload
from pydantic import BaseModel


class Widget(BaseModel):
    name: str
