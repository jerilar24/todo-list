import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from bson import ObjectId
from bson.errors import InvalidId
from dal import ToDoDAL
from fastapi import FastAPI, HTTPException, Query, status
from models import (
    Folder,
    ListUpdate,
    ListSummary,
    NewFolder,
    NewItem,
    NewList,
    NewListResponse,
    RenameRequest,
    ToDoItemUpdate,
    ToDoList,
)
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

COLLECTION_NAME = "todo_lists"
FOLDER_COLLECTION_NAME = "todo_folders"
MONGODB_URI = os.environ["MONGODB_URI"]
DEBUG = os.environ.get("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client.get_default_database()

    # Ensure the database is available:
    pong = await database.command("ping")
    if int(pong["ok"]) != 1:
        raise Exception("Cluster connection is not okay!")

    todo_lists = database.get_collection(COLLECTION_NAME)
    folders = database.get_collection(FOLDER_COLLECTION_NAME)
    app.todo_dal = ToDoDAL(todo_lists, folders)

    # Yield back to FastAPI Application:
    yield

    # Shutdown:
    client.close()


app = FastAPI(lifespan=lifespan, debug=DEBUG)


def valid_object_id(value: str, resource: str) -> str:
    try:
        ObjectId(value)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail=f"{resource} not found") from exc
    return value


@app.get("/api/folders")
async def get_all_folders() -> list[Folder]:
    return [folder async for folder in app.todo_dal.list_folders()]


@app.post("/api/folders", response_model=Folder, status_code=status.HTTP_201_CREATED)
async def create_folder(new_folder: NewFolder) -> Folder:
    return await app.todo_dal.create_folder(new_folder.name)


@app.patch("/api/folders/{folder_id}", response_model=Folder)
async def rename_folder(folder_id: str, rename: RenameRequest) -> Folder:
    folder = await app.todo_dal.rename_folder(
        valid_object_id(folder_id, "Folder"), rename.name
    )
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@app.delete("/api/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    list_action: str = Query(pattern="^(unfiled|delete)$"),
) -> None:
    folder_id = valid_object_id(folder_id, "Folder")
    if not await app.todo_dal.folder_exists(folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")
    await app.todo_dal.delete_folder(
        folder_id, delete_lists=list_action == "delete"
    )


@app.get("/api/lists")
async def get_all_lists() -> list[ListSummary]:
    return [i async for i in app.todo_dal.list_todo_lists()]


@app.post("/api/lists", status_code=status.HTTP_201_CREATED)
async def create_todo_list(new_list: NewList) -> NewListResponse:
    if new_list.folder_id:
        valid_object_id(new_list.folder_id, "Folder")
        if not await app.todo_dal.folder_exists(new_list.folder_id):
            raise HTTPException(status_code=404, detail="Folder not found")
    return NewListResponse(
        id=await app.todo_dal.create_todo_list(new_list.name, new_list.folder_id),
        name=new_list.name,
        folder_id=new_list.folder_id,
    )


@app.patch("/api/lists/{list_id}", response_model=ToDoList)
async def update_list(list_id: str, update: ListUpdate) -> ToDoList:
    list_id = valid_object_id(list_id, "List")
    updates = update.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No updates supplied")
    if updates.get("folder_id"):
        valid_object_id(updates["folder_id"], "Folder")
        if not await app.todo_dal.folder_exists(updates["folder_id"]):
            raise HTTPException(status_code=404, detail="Folder not found")
    result = await app.todo_dal.update_todo_list(list_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.get("/api/lists/{list_id}")
async def get_list(list_id: str) -> ToDoList:
    """Get a single to-do list"""
    result = await app.todo_dal.get_todo_list(valid_object_id(list_id, "List"))
    if result is None:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str) -> bool:
    return await app.todo_dal.delete_todo_list(list_id)


@app.post(
    "/api/lists/{list_id}/items/",
    status_code=status.HTTP_201_CREATED,
)
async def create_item(list_id: str, new_item: NewItem) -> ToDoList:
    return await app.todo_dal.create_item(list_id, new_item.label)


@app.delete("/api/lists/{list_id}/items/{item_id}")
async def delete_item(list_id: str, item_id: str) -> ToDoList:
    return await app.todo_dal.delete_item(list_id, item_id)


@app.patch("/api/lists/{list_id}/items/{item_id}", response_model=ToDoList)
async def rename_item(
    list_id: str, item_id: str, rename: RenameRequest
) -> ToDoList:
    result = await app.todo_dal.rename_item(
        valid_object_id(list_id, "List"), item_id, rename.name
    )
    if result is None:
        raise HTTPException(status_code=404, detail="List item not found")
    return result


@app.patch("/api/lists/{list_id}/checked_state")
async def set_checked_state(list_id: str, update: ToDoItemUpdate) -> ToDoList:
    return await app.todo_dal.set_checked_state(
        list_id, update.item_id, update.checked_state
    )


class DummyResponse(BaseModel):
    id: str
    when: datetime


@app.get("/api/dummy")
async def get_dummy() -> DummyResponse:
    return DummyResponse(
        id=str(ObjectId()),
        when=datetime.now(),
    )


def main(argv=sys.argv[1:]):
    try:
        uvicorn.run("server:app", host="0.0.0.0", port=3001, reload=DEBUG)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
