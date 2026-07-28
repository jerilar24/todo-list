import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass

import uvicorn
from auth import AuthDAL, password_hash
from bson import ObjectId
from bson.errors import InvalidId
from dal import ToDoDAL
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from models import (
    ChangeFolderPassword,
    Folder,
    FolderDeleteRequest,
    ListSummary,
    ListUpdate,
    LoginRequest,
    NewFolder,
    NewItem,
    NewList,
    NewListResponse,
    PasswordRequest,
    PublicUser,
    RenameRequest,
    SecretFolderSummary,
    SetFolderPassword,
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


@dataclass
class AuthContext:
    user: PublicUser
    session: dict

    @property
    def unlocked_folder_ids(self):
        return self.session.get("unlocked_folder_ids", [])


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


async def current_auth(request: Request) -> AuthContext:
    token = request.cookies.get(COOKIE_NAME)
    result = await app.auth_dal.get_user_for_session(token) if token else None
    if not result:
        raise HTTPException(status_code=401, detail="Authentication required")
    user, session = result
    return AuthContext(user, session)


async def current_user(auth: AuthContext = Depends(current_auth)) -> PublicUser:
    return auth.user


async def require_folder_access(auth: AuthContext, folder_id: str):
    if not await app.todo_dal.folder_accessible(
        auth.user.id, folder_id, auth.unlocked_folder_ids
    ):
        raise HTTPException(status_code=404, detail="Folder not found")


async def require_list_access(auth: AuthContext, list_id: str):
    if not await app.todo_dal.list_accessible(
        auth.user.id, list_id, auth.unlocked_folder_ids
    ):
        raise HTTPException(status_code=404, detail="List not found")


async def secret_folder(folder_id: str, auth: AuthContext):
    doc = await app.todo_dal.get_folder(auth.user.id, folder_id)
    if not doc or not doc.get("password_hash"):
        raise HTTPException(status_code=404, detail="Secret folder not found")
    return doc


def password_matches(password: str, password_digest: str) -> bool:
    try:
        return password_hash.verify(password, password_digest)
    except Exception:
        return False


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
async def get_all_folders(auth: AuthContext = Depends(current_auth)) -> list[Folder]:
    return [
        folder
        async for folder in app.todo_dal.list_folders(
            auth.user.id, auth.unlocked_folder_ids
        )
    ]


@app.post("/api/folders", response_model=Folder, status_code=201)
async def create_folder(
    new_folder: NewFolder, auth: AuthContext = Depends(current_auth)
):
    digest = password_hash.hash(new_folder.password) if new_folder.password else None
    folder = await app.todo_dal.create_folder(auth.user.id, new_folder.name, digest)
    if folder.is_secret:
        await app.auth_dal.grant_folder(auth.session["_id"], folder.id)
    return folder


@app.get("/api/secret-folders", response_model=list[SecretFolderSummary])
async def get_secret_folders(auth: AuthContext = Depends(current_auth)):
    return [
        folder
        async for folder in app.todo_dal.list_secret_folders(
            auth.user.id, auth.unlocked_folder_ids
        )
    ]


@app.post("/api/secret-folders/{folder_id}/unlock", status_code=204)
async def unlock_secret_folder(
    folder_id: str,
    request_data: PasswordRequest,
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Secret folder")
    doc = await secret_folder(folder_id, auth)
    if await app.auth_dal.folder_unlock_blocked(auth.user.id, folder_id):
        raise HTTPException(
            status_code=429, detail="Too many attempts. Try again later."
        )
    if not password_matches(request_data.password, doc["password_hash"]):
        await app.auth_dal.record_folder_failure(auth.user.id, folder_id)
        raise HTTPException(status_code=403, detail="Incorrect folder password")
    await app.auth_dal.clear_folder_failures(auth.user.id, folder_id)
    await app.auth_dal.grant_folder(auth.session["_id"], folder_id)


@app.post("/api/folders/{folder_id}/protection", response_model=Folder)
async def protect_folder(
    folder_id: str,
    request_data: SetFolderPassword,
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Folder")
    doc = await app.todo_dal.get_folder(auth.user.id, folder_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Folder not found")
    if doc.get("password_hash"):
        raise HTTPException(status_code=409, detail="Folder is already secret")
    folder = await app.todo_dal.set_folder_password(
        auth.user.id, folder_id, password_hash.hash(request_data.password)
    )
    await app.auth_dal.revoke_folder_from_other_sessions(auth.user.id, folder_id)
    await app.auth_dal.grant_folder(auth.session["_id"], folder_id)
    return folder


@app.patch("/api/folders/{folder_id}/protection", response_model=Folder)
async def change_folder_password(
    folder_id: str,
    request_data: ChangeFolderPassword,
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Folder")
    doc = await secret_folder(folder_id, auth)
    await require_folder_access(auth, folder_id)
    if not password_matches(request_data.current_password, doc["password_hash"]):
        raise HTTPException(status_code=403, detail="Incorrect folder password")
    folder = await app.todo_dal.set_folder_password(
        auth.user.id, folder_id, password_hash.hash(request_data.password)
    )
    await app.auth_dal.revoke_folder_from_other_sessions(
        auth.user.id, folder_id, auth.session["_id"]
    )
    return folder


@app.delete("/api/folders/{folder_id}/protection", response_model=Folder)
async def remove_folder_protection(
    folder_id: str,
    request_data: PasswordRequest = Body(...),
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Folder")
    doc = await secret_folder(folder_id, auth)
    await require_folder_access(auth, folder_id)
    if not password_matches(request_data.password, doc["password_hash"]):
        raise HTTPException(status_code=403, detail="Incorrect folder password")
    folder = await app.todo_dal.remove_folder_password(auth.user.id, folder_id)
    await app.auth_dal.revoke_folder_from_other_sessions(auth.user.id, folder_id)
    return folder


@app.patch("/api/folders/{folder_id}", response_model=Folder)
async def rename_folder(
    folder_id: str,
    rename: RenameRequest,
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Folder")
    await require_folder_access(auth, folder_id)
    folder = await app.todo_dal.rename_folder(
        auth.user.id, folder_id, rename.name
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@app.delete("/api/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    list_action: str = Query(pattern="^(unfiled|delete)$"),
    request_data: FolderDeleteRequest | None = Body(None),
    auth: AuthContext = Depends(current_auth),
):
    folder_id = valid_object_id(folder_id, "Folder")
    doc = await app.todo_dal.get_folder(auth.user.id, folder_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Folder not found")
    if doc.get("password_hash"):
        await require_folder_access(auth, folder_id)
        supplied = request_data.password if request_data else ""
        if not password_matches(supplied, doc["password_hash"]):
            raise HTTPException(status_code=403, detail="Incorrect folder password")
    await app.todo_dal.delete_folder(
        auth.user.id, folder_id, list_action == "delete"
    )
    await app.auth_dal.revoke_folder_from_other_sessions(auth.user.id, folder_id)


@app.get("/api/lists")
async def get_all_lists(
    auth: AuthContext = Depends(current_auth),
) -> list[ListSummary]:
    return [
        item
        async for item in app.todo_dal.list_todo_lists(
            auth.user.id, auth.unlocked_folder_ids
        )
    ]


@app.post("/api/lists", response_model=NewListResponse, status_code=201)
async def create_todo_list(
    new_list: NewList, auth: AuthContext = Depends(current_auth)
):
    if new_list.folder_id:
        new_list.folder_id = valid_object_id(new_list.folder_id, "Folder")
        await require_folder_access(auth, new_list.folder_id)
    return NewListResponse(
        id=await app.todo_dal.create_todo_list(
            auth.user.id, new_list.name, new_list.folder_id
        ),
        name=new_list.name,
        folder_id=new_list.folder_id,
    )


@app.patch("/api/lists/{list_id}", response_model=ToDoList)
async def update_list(
    list_id: str,
    update: ListUpdate,
    auth: AuthContext = Depends(current_auth),
):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    updates = update.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No updates supplied")
    if updates.get("folder_id"):
        updates["folder_id"] = valid_object_id(updates["folder_id"], "Folder")
        await require_folder_access(auth, updates["folder_id"])
    result = await app.todo_dal.update_todo_list(
        auth.user.id, list_id, updates
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.get("/api/lists/{list_id}", response_model=ToDoList)
async def get_list(list_id: str, auth: AuthContext = Depends(current_auth)):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    result = await app.todo_dal.get_todo_list(
        auth.user.id, list_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str, auth: AuthContext = Depends(current_auth)):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    return await app.todo_dal.delete_todo_list(
        auth.user.id, list_id
    )


@app.post("/api/lists/{list_id}/items/", response_model=ToDoList, status_code=201)
async def create_item(
    list_id: str,
    new_item: NewItem,
    auth: AuthContext = Depends(current_auth),
):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    result = await app.todo_dal.create_item(
        auth.user.id, list_id, new_item.label
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.delete("/api/lists/{list_id}/items/{item_id}", response_model=ToDoList)
async def delete_item(
    list_id: str,
    item_id: str,
    auth: AuthContext = Depends(current_auth),
):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    result = await app.todo_dal.delete_item(
        auth.user.id, list_id, item_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.patch("/api/lists/{list_id}/items/{item_id}", response_model=ToDoList)
async def rename_item(
    list_id: str,
    item_id: str,
    rename: RenameRequest,
    auth: AuthContext = Depends(current_auth),
):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    result = await app.todo_dal.rename_item(
        auth.user.id, list_id, item_id, rename.name
    )
    if not result:
        raise HTTPException(status_code=404, detail="List item not found")
    return result


@app.patch("/api/lists/{list_id}/checked_state", response_model=ToDoList)
async def set_checked_state(
    list_id: str,
    update: ToDoItemUpdate,
    auth: AuthContext = Depends(current_auth),
):
    list_id = valid_object_id(list_id, "List")
    await require_list_access(auth, list_id)
    result = await app.todo_dal.set_checked_state(
        auth.user.id,
        list_id,
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
