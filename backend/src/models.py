from pydantic import BaseModel, field_validator


class NamedModel(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value


class Folder(NamedModel):
    id: str

    @staticmethod
    def from_doc(doc) -> "Folder":
        return Folder(id=str(doc["_id"]), name=doc["name"])


class NewFolder(NamedModel):
    pass


class RenameRequest(NamedModel):
    pass


class ListSummary(BaseModel):
    id: str
    name: str
    item_count: int
    folder_id: str | None = None

    @staticmethod
    def from_doc(doc) -> "ListSummary":
        return ListSummary(
            id=str(doc["_id"]),
            name=doc["name"],
            item_count=doc["item_count"],
            folder_id=str(doc["folder_id"]) if doc.get("folder_id") else None,
        )


class ToDoListItem(BaseModel):
    id: str
    label: str
    checked: bool

    @staticmethod
    def from_doc(item) -> "ToDoListItem":
        return ToDoListItem(id=item["id"], label=item["label"], checked=item["checked"])


class NewItem(BaseModel):
    label: str


class NewItemResponse(BaseModel):
    id: str
    label: str


class ToDoItemUpdate(BaseModel):
    item_id: str
    checked_state: bool


class ToDoList(BaseModel):
    id: str
    name: str
    folder_id: str | None = None
    items: list[ToDoListItem]

    @staticmethod
    def from_doc(doc) -> "ToDoList":
        return ToDoList(
            id=str(doc["_id"]),
            name=doc["name"],
            folder_id=str(doc["folder_id"]) if doc.get("folder_id") else None,
            items=[ToDoListItem.from_doc(item) for item in doc["items"]],
        )


class NewList(NamedModel):
    folder_id: str | None = None


class NewListResponse(NamedModel):
    id: str
    folder_id: str | None = None


class ListUpdate(BaseModel):
    name: str | None = None
    folder_id: str | None = None

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value
