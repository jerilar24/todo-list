from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel
from pymongo import ReturnDocument


class ListSummary(BaseModel):
    id: str
    name: str
    item_count: int

    @staticmethod
    def from_doc(doc) -> "ListSummary":
        return ListSummary(
            id=str(doc["_id"]), name=doc["name"], item_count=doc["item_count"]
        )


class ToDoListItem(BaseModel):
    id: str
    label: str
    checked: bool

    @staticmethod
    def from_doc(item) -> "ToDoListItem":
        return ToDoListItem(id=item["id"], label=item["label"], checked=item["checked"])
    

class ToDoList(BaseModel):
    id: str
    name:str
    items: list[ToDoListItem]

    @staticmethod
    def from_doc(doc) -> "ToDoList":
        return ToDoList(id=str(doc["_id"]), name=doc["name"], items=[ToDoListItem.from_doc(item) for item in doc["items"]])
    
    