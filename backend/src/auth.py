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
                "identifier": normalize(identifier),
                "created_at": {"$gte": utc_now() - ATTEMPT_WINDOW},
            }
        ) >= MAX_ATTEMPTS

    async def record_failure(self, identifier: str):
        await self.attempts.insert_one(
            {"identifier": normalize(identifier), "created_at": utc_now()}
        )

    async def authenticate(self, identifier: str, password: str) -> PublicUser | None:
        normalized = normalize(identifier)
        doc = await self.users.find_one(
            {"$or": [{"email": normalized}, {"username": normalized}]}
        )

        if not doc or not password_hash.verify(password, doc["password_hash"]):
            await self.record_failure(identifier)
            return None
        await self.attempts.delete_many({"identifier": normalized})
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

    async def get_user_for_session(self, token: str) -> PublicUser | None:
        now = utc_now()
        session = await self.sessions.find_one_and_update(
            {"token_hash": token_digest(token), "expires_at": {"$gt": now}},
            {"$set": {"last_activity": now, "expires_at": now + IDLE_TIMEOUT}},
        )
        if not session:
            return None
        user = await self.users.find_one({"_id": session["user_id"]})
        return PublicUser.from_doc(user) if user else None

    async def logout(self, token: str):
        await self.sessions.delete_one({"token_hash": token_digest(token)})
