import os
import sys
import unittest
from pathlib import Path

from bson import ObjectId
from pydantic import ValidationError

os.environ.setdefault("MONGODB_URI", "mongodb://localhost/todo_test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import server
from dal import ToDoDAL
from models import Folder, NewFolder, PasswordRequest, PublicUser


class AsyncCursor:
    def __init__(self, docs):
        self.docs = docs

    def __aiter__(self):
        self.index = 0
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        doc = self.docs[self.index]
        self.index += 1
        return doc


class RecordingCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.queries = []

    def find(self, query, **kwargs):
        self.queries.append(query)
        return AsyncCursor(self.docs)


class SecretFolderModelTests(unittest.TestCase):
    def test_folder_derives_secret_state_from_password_hash(self):
        doc = {"_id": ObjectId(), "name": "Vault", "password_hash": "hash"}

        self.assertEqual(Folder.from_doc(doc).is_secret, True)

    def test_new_secret_folder_requires_matching_password(self):
        NewFolder(
            name="Vault",
            password="correct horse",
            confirm_password="correct horse",
        )

        with self.assertRaises(ValidationError):
            NewFolder(name="Vault", password="short", confirm_password="short")

        with self.assertRaises(ValidationError):
            NewFolder(
                name="Vault",
                password="correct horse",
                confirm_password="wrong horse",
            )


class SecretFolderDALTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_folders_excludes_locked_secret_folders(self):
        owner_id = ObjectId()
        public_id = ObjectId()
        unlocked_id = ObjectId()
        folders = RecordingCollection(
            [
                {"_id": public_id, "owner_id": owner_id, "name": "Public"},
                {
                    "_id": unlocked_id,
                    "owner_id": owner_id,
                    "name": "Unlocked",
                    "password_hash": "hash",
                },
            ]
        )
        dal = ToDoDAL(RecordingCollection(), folders)

        result = [
            folder
            async for folder in dal.list_folders(owner_id, [str(unlocked_id)])
        ]

        self.assertEqual([folder.name for folder in result], ["Public", "Unlocked"])
        self.assertEqual(
            folders.queries[0]["$or"],
            [
                {"password_hash": {"$exists": False}},
                {"_id": {"$in": [unlocked_id]}},
            ],
        )


class FakeTodoDAL:
    def __init__(self, password_digest):
        self.folder_id = str(ObjectId())
        self.doc = {
            "_id": ObjectId(self.folder_id),
            "owner_id": ObjectId(),
            "name": "Vault",
            "password_hash": password_digest,
        }

    async def get_folder(self, owner_id, folder_id):
        return self.doc if folder_id == self.folder_id else None


class FakeAuthDAL:
    def __init__(self):
        self.grants = []
        self.failures = []
        self.cleared = []

    async def folder_unlock_blocked(self, user_id, folder_id):
        return False

    async def record_folder_failure(self, user_id, folder_id):
        self.failures.append((user_id, folder_id))

    async def clear_folder_failures(self, user_id, folder_id):
        self.cleared.append((user_id, folder_id))

    async def grant_folder(self, session_id, folder_id):
        self.grants.append((session_id, folder_id))


class SecretFolderEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user = PublicUser(
            id=str(ObjectId()),
            name="Ada",
            email="ada@example.com",
            username="ada",
        )
        self.session_id = ObjectId()
        self.password_digest = server.password_hash.hash("correct horse")
        self.todo_dal = FakeTodoDAL(self.password_digest)
        self.auth_dal = FakeAuthDAL()
        server.app.todo_dal = self.todo_dal
        server.app.auth_dal = self.auth_dal
        self.auth = server.AuthContext(
            self.user,
            {"_id": self.session_id, "unlocked_folder_ids": []},
        )

    async def test_unlock_grants_folder_to_current_session(self):
        await server.unlock_secret_folder(
            self.todo_dal.folder_id,
            PasswordRequest(password="correct horse"),
            self.auth,
        )

        self.assertEqual(self.auth_dal.grants, [(self.session_id, self.todo_dal.folder_id)])
        self.assertEqual(self.auth_dal.failures, [])

    async def test_unlock_records_wrong_password_failure(self):
        with self.assertRaises(server.HTTPException) as raised:
            await server.unlock_secret_folder(
                self.todo_dal.folder_id,
                PasswordRequest(password="wrong horse"),
                self.auth,
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            self.auth_dal.failures,
            [(self.user.id, self.todo_dal.folder_id)],
        )
        self.assertEqual(self.auth_dal.grants, [])


if __name__ == "__main__":
    unittest.main()
