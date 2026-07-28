import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from auth import AuthDAL
from bson import ObjectId
from bson.errors import InvalidId
from dal import ToDoDAL
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from models import (
    Folder,
    ListSummary,
    ListUpdate,
    LoginRequest,
    NewFolder,
    NewItem,
    NewList,
    NewListResponse,
    PublicUser,
    RenameRequest,
    SignUpRequest,
    ToDoItemUpdate,
    ToDoList,
)
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

MONGODB_URI = os.environ["MONGODB_URI"]
DEBUG = os.environ.get("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}
APP_ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost:8000").rstrip("/")
COOKIE_NAME = "todo_session"


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client.get_default_database()
    await database.command("ping")
    app.todo_dal = ToDoDAL(
        database.get_collection("todo_lists"),
        database.get_collection("todo_folders"),
    )
    app.auth_dal = AuthDAL(
        database.get_collection("users"),
        database.get_collection("sessions"),
        database.get_collection("login_attempts"),
    )
    await app.auth_dal.ensure_indexes()
    await database.todo_lists.create_index("owner_id")
    await database.todo_folders.create_index("owner_id")
    yield
    client.close()


app = FastAPI(lifespan=lifespan, debug=DEBUG)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != APP_ORIGIN:
            return Response(status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


def valid_object_id(value: str, resource: str) -> str:
    try:
        ObjectId(value)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail=f"{resource} not found") from exc
    return value


async def current_user(request: Request) -> PublicUser:
    token = request.cookies.get(COOKIE_NAME)
    user = await app.auth_dal.get_user_for_session(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.post("/api/auth/signup", response_model=PublicUser, status_code=201)
async def signup(data: SignUpRequest):
    try:
        return await app.auth_dal.create_user(data)
    except DuplicateKeyError as exc:
        field = "Username" if "username_1" in str(exc) else "Email"
        raise HTTPException(status_code=409, detail=f"{field} is already registered") from exc


@app.post("/api/auth/login", response_model=PublicUser)
async def login(data: LoginRequest, response: Response):
    if await app.auth_dal.login_blocked(data.identifier):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    user = await app.auth_dal.authenticate(data.identifier, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email, username, or password")
    token = await app.auth_dal.create_session(user.id)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=not DEBUG,
        samesite="lax",
        path="/api",
    )
    return user


@app.get("/api/auth/me", response_model=PublicUser)
async def me(user: PublicUser = Depends(current_user)):
    return user


@app.post("/api/auth/activity", status_code=204)
async def activity(user: PublicUser = Depends(current_user)):
    return None


@app.post("/api/auth/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await app.auth_dal.logout(token)
    response.delete_cookie(COOKIE_NAME, path="/api")


@app.get("/api/folders")
async def get_all_folders(user: PublicUser = Depends(current_user)) -> list[Folder]:
    return [folder async for folder in app.todo_dal.list_folders(user.id)]


@app.post("/api/folders", response_model=Folder, status_code=201)
async def create_folder(new_folder: NewFolder, user: PublicUser = Depends(current_user)):
    return await app.todo_dal.create_folder(user.id, new_folder.name)


@app.patch("/api/folders/{folder_id}", response_model=Folder)
async def rename_folder(
    folder_id: str, rename: RenameRequest, user: PublicUser = Depends(current_user)
):
    folder = await app.todo_dal.rename_folder(
        user.id, valid_object_id(folder_id, "Folder"), rename.name
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@app.delete("/api/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    list_action: str = Query(pattern="^(unfiled|delete)$"),
    user: PublicUser = Depends(current_user),
):
    folder_id = valid_object_id(folder_id, "Folder")
    if not await app.todo_dal.folder_exists(user.id, folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")
    await app.todo_dal.delete_folder(user.id, folder_id, list_action == "delete")


@app.get("/api/lists")
async def get_all_lists(user: PublicUser = Depends(current_user)) -> list[ListSummary]:
    return [item async for item in app.todo_dal.list_todo_lists(user.id)]


@app.post("/api/lists", response_model=NewListResponse, status_code=201)
async def create_todo_list(new_list: NewList, user: PublicUser = Depends(current_user)):
    if new_list.folder_id and not await app.todo_dal.folder_exists(
        user.id, valid_object_id(new_list.folder_id, "Folder")
    ):
        raise HTTPException(status_code=404, detail="Folder not found")
    return NewListResponse(
        id=await app.todo_dal.create_todo_list(
            user.id, new_list.name, new_list.folder_id
        ),
        name=new_list.name,
        folder_id=new_list.folder_id,
    )


@app.patch("/api/lists/{list_id}", response_model=ToDoList)
async def update_list(
    list_id: str, update: ListUpdate, user: PublicUser = Depends(current_user)
):
    updates = update.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No updates supplied")
    if updates.get("folder_id") and not await app.todo_dal.folder_exists(
        user.id, valid_object_id(updates["folder_id"], "Folder")
    ):
        raise HTTPException(status_code=404, detail="Folder not found")
    result = await app.todo_dal.update_todo_list(
        user.id, valid_object_id(list_id, "List"), updates
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.get("/api/lists/{list_id}", response_model=ToDoList)
async def get_list(list_id: str, user: PublicUser = Depends(current_user)):
    result = await app.todo_dal.get_todo_list(
        user.id, valid_object_id(list_id, "List")
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str, user: PublicUser = Depends(current_user)):
    return await app.todo_dal.delete_todo_list(
        user.id, valid_object_id(list_id, "List")
    )


@app.post("/api/lists/{list_id}/items/", response_model=ToDoList, status_code=201)
async def create_item(
    list_id: str, new_item: NewItem, user: PublicUser = Depends(current_user)
):
    result = await app.todo_dal.create_item(
        user.id, valid_object_id(list_id, "List"), new_item.label
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.delete("/api/lists/{list_id}/items/{item_id}", response_model=ToDoList)
async def delete_item(
    list_id: str, item_id: str, user: PublicUser = Depends(current_user)
):
    result = await app.todo_dal.delete_item(
        user.id, valid_object_id(list_id, "List"), item_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.patch("/api/lists/{list_id}/items/{item_id}", response_model=ToDoList)
async def rename_item(
    list_id: str,
    item_id: str,
    rename: RenameRequest,
    user: PublicUser = Depends(current_user),
):
    result = await app.todo_dal.rename_item(
        user.id, valid_object_id(list_id, "List"), item_id, rename.name
    )
    if not result:
        raise HTTPException(status_code=404, detail="List item not found")
    return result


@app.patch("/api/lists/{list_id}/checked_state", response_model=ToDoList)
async def set_checked_state(
    list_id: str,
    update: ToDoItemUpdate,
    user: PublicUser = Depends(current_user),
):
    result = await app.todo_dal.set_checked_state(
        user.id,
        valid_object_id(list_id, "List"),
        update.item_id,
        update.checked_state,
    )
    if not result:
        raise HTTPException(status_code=404, detail="List item not found")
    return result


def main(argv=sys.argv[1:]):
    try:
        uvicorn.run("server:app", host="0.0.0.0", port=3001, reload=DEBUG)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
