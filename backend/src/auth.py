import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from models import PublicUser, SignUpRequest
from motor.motor_asyncio import AsyncIOMotorCollection
from pwdlib import PasswordHash

IDLE_TIMEOUT = timedelta(minutes=30)
ATTEMPT_WINDOW = timedelta(minutes=15)
MAX_ATTEMPTS = 5
password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("not-a-real-user-password")


def utc_now():
    return datetime.now(timezone.utc)


def normalize(value: str) -> str:
    return value.strip().casefold()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthDAL:
    def __init__(self, users, sessions, attempts):
        self.users: AsyncIOMotorCollection = users
        self.sessions: AsyncIOMotorCollection = sessions
        self.attempts: AsyncIOMotorCollection = attempts

    async def ensure_indexes(self):
        await self.users.create_index("email", unique=True)
        await self.users.create_index(
            "username",
            unique=True,
            partialFilterExpression={"username": {"$type": "string"}},
        )
        await self.sessions.create_index("token_hash", unique=True)
        await self.sessions.create_index("expires_at", expireAfterSeconds=0)
        await self.sessions.create_index("user_id")
        await self.attempts.create_index("created_at", expireAfterSeconds=900)

    async def create_user(self, signup: SignUpRequest) -> PublicUser:
        document = {
            "name": signup.name,
            "email": normalize(str(signup.email)),
            "password_hash": password_hash.hash(signup.password),
            "created_at": utc_now(),
        }
        if signup.username:
            document["username"] = normalize(signup.username)
        result = await self.users.insert_one(document)
        document["_id"] = result.inserted_id
        return PublicUser.from_doc(document)

    async def login_blocked(self, identifier: str) -> bool:
        return await self.attempts.count_documents(
            {
                "kind": "login",
                "identifier": normalize(identifier),
                "created_at": {"$gte": utc_now() - ATTEMPT_WINDOW},
            }
        ) >= MAX_ATTEMPTS

    async def record_failure(self, identifier: str):
        await self.attempts.insert_one(
            {
                "kind": "login",
                "identifier": normalize(identifier),
                "created_at": utc_now(),
            }
        )

    async def authenticate(self, identifier: str, password: str) -> PublicUser | None:
        normalized = normalize(identifier)
        doc = await self.users.find_one(
            {"$or": [{"email": normalized}, {"username": normalized}]}
        )

        if not doc or not password_hash.verify(password, doc["password_hash"]):
            await self.record_failure(identifier)
            return None
        await self.attempts.delete_many({"kind": "login", "identifier": normalized})
        return PublicUser.from_doc(doc)

    async def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        await self.sessions.insert_one(
            {
                "token_hash": token_digest(token),
                "user_id": ObjectId(user_id),
                "created_at": now,
                "last_activity": now,
                "expires_at": now + IDLE_TIMEOUT,
            }
        )
        return token

    async def get_user_for_session(self, token: str):
        now = utc_now()
        session = await self.sessions.find_one_and_update(
            {"token_hash": token_digest(token), "expires_at": {"$gt": now}},
            {"$set": {"last_activity": now, "expires_at": now + IDLE_TIMEOUT}},
        )
        if not session:
            return None
        user = await self.users.find_one({"_id": session["user_id"]})
        if not user:
            return None
        return PublicUser.from_doc(user), session

    async def logout(self, token: str):
        await self.sessions.delete_one({"token_hash": token_digest(token)})

    async def grant_folder(self, session_id, folder_id: str):
        await self.sessions.update_one(
            {"_id": session_id},
            {"$addToSet": {"unlocked_folder_ids": ObjectId(folder_id)}},
        )

    async def revoke_folder_from_other_sessions(
        self, user_id: str, folder_id: str, keep_session_id=None
    ):
        query = {"user_id": ObjectId(user_id)}
        if keep_session_id is not None:
            query["_id"] = {"$ne": keep_session_id}
        await self.sessions.update_many(
            query, {"$pull": {"unlocked_folder_ids": ObjectId(folder_id)}}
        )

    async def folder_unlock_blocked(self, user_id: str, folder_id: str) -> bool:
        return await self.attempts.count_documents(
            {
                "kind": "folder",
                "user_id": ObjectId(user_id),
                "folder_id": ObjectId(folder_id),
                "created_at": {"$gte": utc_now() - ATTEMPT_WINDOW},
            }
        ) >= MAX_ATTEMPTS

    async def record_folder_failure(self, user_id: str, folder_id: str):
        await self.attempts.insert_one(
            {
                "kind": "folder",
                "user_id": ObjectId(user_id),
                "folder_id": ObjectId(folder_id),
                "created_at": utc_now(),
            }
        )

    async def clear_folder_failures(self, user_id: str, folder_id: str):
        await self.attempts.delete_many(
            {
                "kind": "folder",
                "user_id": ObjectId(user_id),
                "folder_id": ObjectId(folder_id),
            }
        )
