from typing import Optional

from pydantic import BaseModel


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
    id: Optional[str]
    name: str
    items: Optional[list[ToDoListItem]]

    @staticmethod
    def from_doc(doc) -> "ToDoList":
        return ToDoList(
            id=str(doc["_id"]),
            name=doc["name"],
            items=[ToDoListItem.from_doc(item) for item in doc["items"]],
        )
