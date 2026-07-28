from uuid import uuid4

from bson import ObjectId
from models import Folder, ListSummary, ToDoList
from pymongo import ReturnDocument


class ToDoDAL:
    def __init__(self, todo_collection, folder_collection):
        self._todo_collection = todo_collection
        self._folder_collection = folder_collection

    def owned(self, owner_id, extra=None):
        return {"owner_id": ObjectId(owner_id), **(extra or {})}

    async def list_folders(self, owner_id, session=None):
        async for doc in self._folder_collection.find(
            self.owned(owner_id), sort={"name": 1}, session=session
        ):
            yield Folder.from_doc(doc)

    async def create_folder(self, owner_id, name, session=None):
        response = await self._folder_collection.insert_one(
            self.owned(owner_id, {"name": name}), session=session
        )
        return Folder(id=str(response.inserted_id), name=name)

    async def folder_exists(self, owner_id, folder_id, session=None):
        return await self._folder_collection.count_documents(
            self.owned(owner_id, {"_id": ObjectId(folder_id)}), limit=1, session=session
        ) == 1

    async def rename_folder(self, owner_id, folder_id, name, session=None):
        doc = await self._folder_collection.find_one_and_update(
            self.owned(owner_id, {"_id": ObjectId(folder_id)}),
            {"$set": {"name": name}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return Folder.from_doc(doc) if doc else None

    async def delete_folder(self, owner_id, folder_id, delete_lists, session=None):
        folder_id = ObjectId(folder_id)
        lists = self.owned(owner_id, {"folder_id": folder_id})
        if delete_lists:
            await self._todo_collection.delete_many(lists, session=session)
        else:
            await self._todo_collection.update_many(
                lists, {"$unset": {"folder_id": ""}}, session=session
            )
        result = await self._folder_collection.delete_one(
            self.owned(owner_id, {"_id": folder_id}), session=session
        )
        return result.deleted_count == 1

    async def list_todo_lists(self, owner_id, session=None):
        async for doc in self._todo_collection.find(
            self.owned(owner_id),
            projection={
                "name": 1,
                "folder_id": 1,
                "item_count": {"$size": "$items"},
            },
            sort={"name": 1},
            session=session,
        ):
            yield ListSummary.from_doc(doc)

    async def create_todo_list(self, owner_id, name, folder_id=None, session=None):
        doc = self.owned(owner_id, {"name": name, "items": []})
        if folder_id:
            doc["folder_id"] = ObjectId(folder_id)
        response = await self._todo_collection.insert_one(doc, session=session)
        return str(response.inserted_id)

    async def update_todo_list(self, owner_id, list_id, updates, session=None):
        mongo_update = {}
        if "name" in updates:
            mongo_update.setdefault("$set", {})["name"] = updates["name"]
        if "folder_id" in updates:
            if updates["folder_id"] is None:
                mongo_update.setdefault("$unset", {})["folder_id"] = ""
            else:
                mongo_update.setdefault("$set", {})["folder_id"] = ObjectId(updates["folder_id"])
        result = await self._todo_collection.find_one_and_update(
            self.owned(owner_id, {"_id": ObjectId(list_id)}),
            mongo_update,
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return ToDoList.from_doc(result) if result else None

    async def get_todo_list(self, owner_id, list_id, session=None):
        doc = await self._todo_collection.find_one(
            self.owned(owner_id, {"_id": ObjectId(list_id)}), session=session
        )
        return ToDoList.from_doc(doc) if doc else None

    async def delete_todo_list(self, owner_id, list_id, session=None):
        response = await self._todo_collection.delete_one(
            self.owned(owner_id, {"_id": ObjectId(list_id)}), session=session
        )
        return response.deleted_count == 1

    async def create_item(self, owner_id, list_id, label, session=None):
        return await self._item_update(
            owner_id,
            list_id,
            {"$push": {"items": {"id": uuid4().hex, "label": label, "checked": False}}},
            session=session,
        )

    async def set_checked_state(
        self, owner_id, list_id, item_id, checked_state, session=None
    ):
        return await self._item_update(
            owner_id,
            list_id,
            {"$set": {"items.$.checked": checked_state}},
            item_id,
            session,
        )

    async def delete_item(self, owner_id, list_id, item_id, session=None):
        return await self._item_update(
            owner_id,
            list_id,
            {"$pull": {"items": {"id": item_id}}},
            session=session,
        )

    async def rename_item(self, owner_id, list_id, item_id, label, session=None):
        return await self._item_update(
            owner_id,
            list_id,
            {"$set": {"items.$.label": label}},
            item_id,
            session,
        )

    async def _item_update(
        self, owner_id, list_id, update, item_id=None, session=None
    ):
        extra = {"_id": ObjectId(list_id)}
        if item_id:
            extra["items.id"] = item_id
        result = await self._todo_collection.find_one_and_update(
            self.owned(owner_id, extra),
            update,
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        return ToDoList.from_doc(result) if result else None
