import { useEffect, useState } from "react";
import axios from "axios";
import { BiEdit, BiSolidTrash } from "react-icons/bi";
import "./TodoList.css";
import Modal from "./Modal";

function ToDoList({ listId, folders, handleBackButton, handleListChanged }) {
    const [listData, setListData] = useState(null);
    const [newItem, setNewItem] = useState("");
    const [editing, setEditing] = useState(null);
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        axios
            .get(`/api/lists/${listId}`)
            .then((response) => setListData(response.data))
            .catch((requestError) => {
                console.error(requestError);
                setError("Unable to load this to-do list.");
            });
    }, [listId]);

    async function update(request) {
        setSaving(true);
        try {
            const response = await request();
            if (response?.data) setListData(response.data);
            setError("");
            await handleListChanged();
            return true;
        } catch (requestError) {
            console.error(requestError);
            setError(requestError.response?.data?.detail || "The change could not be saved.");
            return false;
        } finally {
            setSaving(false);
        }
    }

    if (listData === null) {
        return (
            <div className="ToDoList loading">
                <button className="back" onClick={handleBackButton}>Back</button>
                {error || "Loading to-do list ..."}
            </div>
        );
    }

    return (
        <main className="ToDoList">
            <button className="back" onClick={handleBackButton}>Back</button>
            {error && <div className="error" role="alert">{error}</div>}
            <header className="list-heading">
                <h1>{listData.name}</h1>
                <button
                    aria-label="Edit list"
                    onClick={() =>
                        setEditing({
                            type: "list",
                            name: listData.name,
                            folder_id: listData.folder_id || "",
                        })
                    }
                >
                    <BiEdit />
                </button>
            </header>

            <form
                className="box new-item"
                onSubmit={async (event) => {
                    event.preventDefault();
                    if (!newItem.trim()) return;
                    const saved = await update(() =>
                        axios.post(`/api/lists/${listData.id}/items/`, {
                            label: newItem.trim(),
                        })
                    );
                    if (saved) setNewItem("");
                }}
            >
                <label>
                    New item
                    <input
                        value={newItem}
                        onChange={(event) => setNewItem(event.target.value)}
                    />
                </label>
                <button disabled={saving}>Add item</button>
            </form>

            {listData.items.length > 0 ? (
                listData.items.map((item) => (
                    <div
                        key={item.id}
                        className={item.checked ? "item checked" : "item"}
                        onClick={() =>
                            update(() =>
                                axios.patch(
                                    `/api/lists/${listData.id}/checked_state`,
                                    {
                                        item_id: item.id,
                                        checked_state: !item.checked,
                                    }
                                )
                            )
                        }
                    >
                        <span aria-hidden="true">{item.checked ? "✓" : "☐"}</span>
                        <span className="label">{item.label}</span>
                        <span className="flex" />
                        <span className="row-actions">
                            <button
                                aria-label={`Rename item ${item.label}`}
                                onClick={(event) => {
                                    event.stopPropagation();
                                    setEditing({ type: "item", ...item });
                                }}
                            >
                                <BiEdit />
                            </button>
                            <button
                                aria-label={`Delete item ${item.label}`}
                                onClick={(event) => {
                                    event.stopPropagation();
                                    update(() =>
                                        axios.delete(
                                            `/api/lists/${listData.id}/items/${item.id}`
                                        )
                                    );
                                }}
                            >
                                <BiSolidTrash />
                            </button>
                        </span>
                    </div>
                ))
            ) : (
                <div className="box">There are currently no items.</div>
            )}

            {editing && (
                <RenameModal
                    target={editing}
                    folders={folders}
                    saving={saving}
                    onClose={() => setEditing(null)}
                    onSave={async (name, folderId) => {
                        const saved =
                            editing.type === "list"
                                ? await update(() =>
                                      axios.patch(`/api/lists/${listData.id}`, {
                                          name,
                                          folder_id: folderId || null,
                                      })
                                  )
                                : await update(() =>
                                      axios.patch(
                                          `/api/lists/${listData.id}/items/${editing.id}`,
                                          { name }
                                      )
                                  );
                        if (saved) setEditing(null);
                    }}
                />
            )}
        </main>
    );
}

function RenameModal({ target, folders, saving, onClose, onSave }) {
    const [name, setName] = useState(target.name || target.label);
    const [folderId, setFolderId] = useState(target.folder_id || "");
    return (
        <Modal title={`Edit ${target.type}`} onClose={onClose}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    if (name.trim()) onSave(name, folderId);
                }}
            >
                <label>
                    Name
                    <input
                        autoFocus
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                    />
                </label>
                {target.type === "list" && (
                    <label>
                        Folder
                        <select
                            value={folderId}
                            onChange={(event) => setFolderId(event.target.value)}
                        >
                            <option value="">Unfiled</option>
                            {folders.map((folder) => (
                                <option key={folder.id} value={folder.id}>
                                    {folder.name}
                                </option>
                            ))}
                        </select>
                    </label>
                )}
                <div className="modal-actions">
                    <button type="button" onClick={onClose}>Cancel</button>
                    <button disabled={saving || !name.trim()}>Save</button>
                </div>
            </form>
        </Modal>
    );
}

export default ToDoList;
