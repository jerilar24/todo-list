import { useState } from "react";
import { BiEdit, BiFolder, BiSolidTrash } from "react-icons/bi";
import "./ListTodoList.css";
import Modal from "./Modal";

function ListToDoLists({ folders, listSummaries, actions, handleSelectList }) {
    const [newFolderName, setNewFolderName] = useState("");
    const [newListName, setNewListName] = useState("");
    const [newListFolder, setNewListFolder] = useState("");
    const [editing, setEditing] = useState(null);
    const [deletingFolder, setDeletingFolder] = useState(null);
    const [saving, setSaving] = useState(false);

    if (folders === null || listSummaries === null) {
        return <div className="ListToDoLists loading">Loading to-do lists ...</div>;
    }

    const sortedFolders = [...folders].sort((a, b) => a.name.localeCompare(b.name));
    const sections = [
        { id: null, name: "Unfiled" },
        ...sortedFolders,
    ];

    async function submit(action, clear) {
        setSaving(true);
        try {
            const saved = await action();
            if (saved !== false) clear();
        } finally {
            setSaving(false);
        }
    }

    function listsIn(folderId) {
        return listSummaries.filter(
            (list) => (list.folder_id || null) === folderId
        );
    }

    function requestFolderDelete(folder) {
        if (listsIn(folder.id).length === 0) {
            actions.deleteFolder(folder.id, "unfiled");
        } else {
            setDeletingFolder(folder);
        }
    }

    return (
        <main className="ListToDoLists">
            <h1>To-Do Lists</h1>

            <section className="create-panel">
                <form
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (!newFolderName.trim()) return;
                        submit(
                            () => actions.createFolder(newFolderName),
                            () => setNewFolderName("")
                        );
                    }}
                >
                    <label>
                        New folder
                        <input
                            value={newFolderName}
                            onChange={(event) => setNewFolderName(event.target.value)}
                        />
                    </label>
                    <button disabled={saving}>Add folder</button>
                </form>

                <form
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (!newListName.trim()) return;
                        submit(
                            () => actions.createList(newListName, newListFolder),
                            () => setNewListName("")
                        );
                    }}
                >
                    <label>
                        New list
                        <input
                            value={newListName}
                            onChange={(event) => setNewListName(event.target.value)}
                        />
                    </label>
                    <label>
                        Folder
                        <select
                            value={newListFolder}
                            onChange={(event) => setNewListFolder(event.target.value)}
                        >
                            <option value="">Unfiled</option>
                            {sortedFolders.map((folder) => (
                                <option key={folder.id} value={folder.id}>
                                    {folder.name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <button disabled={saving}>Add list</button>
                </form>
            </section>

            {sections.map((folder) => (
                <section className="folder" key={folder.id || "unfiled"}>
                    <header>
                        <h2><BiFolder /> {folder.name}</h2>
                        {folder.id && (
                            <div className="row-actions">
                                <button
                                    aria-label={`Rename folder ${folder.name}`}
                                    onClick={() => setEditing({ type: "folder", ...folder })}
                                >
                                    <BiEdit />
                                </button>
                                <button
                                    aria-label={`Delete folder ${folder.name}`}
                                    onClick={() => requestFolderDelete(folder)}
                                >
                                    <BiSolidTrash />
                                </button>
                            </div>
                        )}
                    </header>
                    {listsIn(folder.id).length === 0 ? (
                        <p className="empty">No lists in this folder.</p>
                    ) : (
                        listsIn(folder.id).map((summary) => (
                            <div
                                key={summary.id}
                                className="summary"
                                onClick={() => handleSelectList(summary.id)}
                            >
                                <span className="name">{summary.name}</span>
                                <span className="count">({summary.item_count} items)</span>
                                <span className="flex" />
                                <span className="row-actions">
                                    <button
                                        aria-label={`Edit list ${summary.name}`}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            setEditing({ type: "list", ...summary });
                                        }}
                                    >
                                        <BiEdit />
                                    </button>
                                    <button
                                        aria-label={`Delete list ${summary.name}`}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            actions.deleteList(summary.id);
                                        }}
                                    >
                                        <BiSolidTrash />
                                    </button>
                                </span>
                            </div>
                        ))
                    )}
                </section>
            ))}

            {editing && (
                <EditModal
                    target={editing}
                    folders={sortedFolders}
                    saving={saving}
                    onClose={() => setEditing(null)}
                    onSave={(name, folderId) =>
                        submit(
                            () =>
                                editing.type === "folder"
                                    ? actions.renameFolder(editing.id, name)
                                    : actions.updateList(editing.id, {
                                          name,
                                          folder_id: folderId || null,
                                      }),
                            () => setEditing(null)
                        )
                    }
                />
            )}

            {deletingFolder && (
                <Modal
                    title={`Delete “${deletingFolder.name}”?`}
                    onClose={() => setDeletingFolder(null)}
                >
                    <p>This folder contains {listsIn(deletingFolder.id).length} list(s).</p>
                    <div className="modal-actions">
                        <button onClick={() => setDeletingFolder(null)}>Cancel</button>
                        <button
                            disabled={saving}
                            onClick={() =>
                                submit(
                                    () => actions.deleteFolder(deletingFolder.id, "unfiled"),
                                    () => setDeletingFolder(null)
                                )
                            }
                        >
                            Move lists to Unfiled
                        </button>
                        <button
                            className="danger"
                            disabled={saving}
                            onClick={() =>
                                submit(
                                    () => actions.deleteFolder(deletingFolder.id, "delete"),
                                    () => setDeletingFolder(null)
                                )
                            }
                        >
                            Delete lists too
                        </button>
                    </div>
                </Modal>
            )}
        </main>
    );
}

function EditModal({ target, folders, saving, onClose, onSave }) {
    const [name, setName] = useState(target.name);
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

export default ListToDoLists;
