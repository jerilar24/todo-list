from uuid import uuid4

from bson import ObjectId
from models import Folder, ListSummary, ToDoList
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument


class ToDoDAL:
    def __init__(
        self,
        todo_collection: AsyncIOMotorCollection,
        folder_collection: AsyncIOMotorCollection,
    ):
        self._todo_collection = todo_collection
        self._folder_collection = folder_collection

    async def list_folders(self, session=None):
        async for doc in self._folder_collection.find(
            {}, sort={"name": 1}, session=session
        ):
            yield Folder.from_doc(doc)

    async def create_folder(self, name: str, session=None) -> Folder:
        response = await self._folder_collection.insert_one(
            {"name": name}, session=session
        )
        return Folder(id=str(response.inserted_id), name=name)

    async def folder_exists(self, id: str | ObjectId, session=None) -> bool:
        return (
            await self._folder_collection.count_documents(
                {"_id": ObjectId(id)}, limit=1, session=session
            )
            == 1
        )

    async def rename_folder(
        self, id: str | ObjectId, name: str, session=None
    ) -> Folder | None:
        doc = await self._folder_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": {"name": name}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return Folder.from_doc(doc) if doc else None

    async def folder_list_count(self, id: str | ObjectId, session=None) -> int:
        return await self._todo_collection.count_documents(
            {"folder_id": ObjectId(id)}, session=session
        )

    async def delete_folder(
        self, id: str | ObjectId, delete_lists: bool, session=None
    ) -> bool:
        folder_id = ObjectId(id)
        if delete_lists:
            await self._todo_collection.delete_many(
                {"folder_id": folder_id}, session=session
            )
        else:
            await self._todo_collection.update_many(
                {"folder_id": folder_id},
                {"$unset": {"folder_id": ""}},
                session=session,
            )
        result = await self._folder_collection.delete_one(
            {"_id": folder_id}, session=session
        )
        return result.deleted_count == 1

    async def list_todo_lists(self, session=None):
        async for doc in self._todo_collection.find(
            {},
            projection={
                "name": 1,
                "folder_id": 1,
                "item_count": {"$size": "$items"},
            },
            sort={"name": 1},
            session=session,
        ):
            yield ListSummary.from_doc(doc)

    async def create_todo_list(
        self, name: str, folder_id: str | ObjectId | None = None, session=None
    ) -> str:
        doc = {"name": name, "items": []}
        if folder_id:
            doc["folder_id"] = ObjectId(folder_id)
        response = await self._todo_collection.insert_one(
            doc,
            session=session,
        )
        return str(response.inserted_id)

    async def update_todo_list(
        self,
        id: str | ObjectId,
        updates: dict,
        session=None,
    ) -> ToDoList | None:
        mongo_update = {}
        if "name" in updates:
            mongo_update.setdefault("$set", {})["name"] = updates["name"]
        if "folder_id" in updates:
            if updates["folder_id"] is None:
                mongo_update.setdefault("$unset", {})["folder_id"] = ""
            else:
                mongo_update.setdefault("$set", {})["folder_id"] = ObjectId(
                    updates["folder_id"]
                )
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            mongo_update,
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return ToDoList.from_doc(result) if result else None

    async def get_todo_list(self, id: str | ObjectId, session=None) -> ToDoList:
        doc = await self._todo_collection.find_one(
            {"_id": ObjectId(id)},
            session=session,
        )
        return ToDoList.from_doc(doc) if doc else None

    async def delete_todo_list(self, id: str | ObjectId, session=None) -> bool:
        response = await self._todo_collection.delete_one(
            {"_id": ObjectId(id)},
            session=session,
        )
        return response.deleted_count == 1

    async def create_item(
        self,
        id: str | ObjectId,
        label: str,
        session=None,
    ) -> ToDoList | None:
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {
                "$push": {
                    "items": {
                        "id": uuid4().hex,
                        "label": label,
                        "checked": False,
                    }
                }
            },
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if result:
            return ToDoList.from_doc(result)

    async def set_checked_state(
        self,
        doc_id: str | ObjectId,
        item_id: str,
        checked_state: bool,
        session=None,
    ) -> ToDoList | None:
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(doc_id), "items.id": item_id},
            {"$set": {"items.$.checked": checked_state}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if result:
            return ToDoList.from_doc(result)

    async def delete_item(
        self,
        doc_id: str | ObjectId,
        item_id: str,
        session=None,
    ) -> ToDoList | None:
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(doc_id)},
            {"$pull": {"items": {"id": item_id}}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if result:
            return ToDoList.from_doc(result)

    async def rename_item(
        self,
        doc_id: str | ObjectId,
        item_id: str,
        label: str,
        session=None,
    ) -> ToDoList | None:
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(doc_id), "items.id": item_id},
            {"$set": {"items.$.label": label}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return ToDoList.from_doc(result) if result else None
