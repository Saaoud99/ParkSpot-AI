from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str


class ErrorOut(BaseModel):
    detail: str
    code: str


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
