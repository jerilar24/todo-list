import { useState } from "react";
import { BiEdit, BiFolder, BiKey, BiLock, BiSolidTrash } from "react-icons/bi";
import "./ListTodoList.css";
import Modal from "./Modal";

function ListToDoLists({ folders, listSummaries, actions, handleSelectList }) {
    const [newFolderName, setNewFolderName] = useState("");
    const [newFolderSecret, setNewFolderSecret] = useState(false);
    const [newFolderPassword, setNewFolderPassword] = useState("");
    const [newFolderConfirmation, setNewFolderConfirmation] = useState("");
    const [newListName, setNewListName] = useState("");
    const [newListFolder, setNewListFolder] = useState("");
    const [editing, setEditing] = useState(null);
    const [deletingFolder, setDeletingFolder] = useState(null);
    const [deletePassword, setDeletePassword] = useState("");
    const [protectingFolder, setProtectingFolder] = useState(null);
    const [showSecrets, setShowSecrets] = useState(false);
    const [secretFolders, setSecretFolders] = useState(null);
    const [secretError, setSecretError] = useState("");
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
        if (listsIn(folder.id).length === 0 && !folder.is_secret) {
            actions.deleteFolder(folder.id, "unfiled");
        } else {
            setDeletePassword("");
            setDeletingFolder(folder);
        }
    }

    async function openSecrets() {
        setShowSecrets(true);
        setSecretFolders(null);
        setSecretError("");
        try {
            const response = await actions.listSecretFolders();
            setSecretFolders(response.data);
        } catch (requestError) {
            setSecretError(
                requestError.response?.data?.detail || "Unable to load secret folders."
            );
        }
    }

    return (
        <main className="ListToDoLists">
            <div className="title-row">
                <h1>To-Do Lists</h1>
                <button onClick={openSecrets}><BiKey /> Secret folders</button>
            </div>

            <section className="create-panel">
                <form
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (!newFolderName.trim()) return;
                        submit(
                            () =>
                                actions.createFolder({
                                    name: newFolderName,
                                    ...(newFolderSecret
                                        ? {
                                              password: newFolderPassword,
                                              confirm_password: newFolderConfirmation,
                                          }
                                        : {}),
                                }),
                            () => {
                                setNewFolderName("");
                                setNewFolderPassword("");
                                setNewFolderConfirmation("");
                                setNewFolderSecret(false);
                            }
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
                    <label className="secret-toggle">
                        <input
                            type="checkbox"
                            checked={newFolderSecret}
                            onChange={(event) => setNewFolderSecret(event.target.checked)}
                        />
                        Make secret
                    </label>
                    {newFolderSecret && (
                        <>
                            <label>
                                Password
                                <input
                                    required
                                    minLength="8"
                                    maxLength="128"
                                    type="password"
                                    value={newFolderPassword}
                                    onChange={(event) =>
                                        setNewFolderPassword(event.target.value)
                                    }
                                />
                            </label>
                            <label>
                                Confirm password
                                <input
                                    required
                                    type="password"
                                    value={newFolderConfirmation}
                                    onChange={(event) =>
                                        setNewFolderConfirmation(event.target.value)
                                    }
                                />
                            </label>
                        </>
                    )}
                    <button
                        disabled={
                            saving ||
                            (newFolderSecret &&
                                newFolderPassword !== newFolderConfirmation)
                        }
                    >
                        Add folder
                    </button>
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
                        <h2>
                            <BiFolder /> {folder.name}
                            {folder.is_secret && (
                                <BiLock aria-label="Secret folder" title="Secret folder" />
                            )}
                        </h2>
                        {folder.id && (
                            <div className="row-actions">
                                <button
                                    aria-label={`Rename folder ${folder.name}`}
                                    onClick={() => setEditing({ type: "folder", ...folder })}
                                >
                                    <BiEdit />
                                </button>
                                <button
                                    aria-label={`Manage protection for ${folder.name}`}
                                    onClick={() => setProtectingFolder(folder)}
                                >
                                    <BiKey />
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
                    title={`Delete "${deletingFolder.name}"?`}
                    onClose={() => setDeletingFolder(null)}
                >
                    <p>This folder contains {listsIn(deletingFolder.id).length} list(s).</p>
                    {deletingFolder.is_secret && (
                        <label>
                            Current folder password
                            <input
                                autoFocus
                                type="password"
                                value={deletePassword}
                                onChange={(event) => setDeletePassword(event.target.value)}
                            />
                        </label>
                    )}
                    <div className="modal-actions">
                        <button onClick={() => setDeletingFolder(null)}>Cancel</button>
                        <button
                            disabled={saving || (deletingFolder.is_secret && !deletePassword)}
                            onClick={() =>
                                submit(
                                    () => actions.deleteFolder(
                                        deletingFolder.id,
                                        "unfiled",
                                        deletePassword
                                    ),
                                    () => setDeletingFolder(null)
                                )
                            }
                        >
                            Move lists to Unfiled
                        </button>
                        <button
                            className="danger"
                            disabled={saving || (deletingFolder.is_secret && !deletePassword)}
                            onClick={() =>
                                submit(
                                    () => actions.deleteFolder(
                                        deletingFolder.id,
                                        "delete",
                                        deletePassword
                                    ),
                                    () => setDeletingFolder(null)
                                )
                            }
                        >
                            Delete lists too
                        </button>
                    </div>
                </Modal>
            )}

            {protectingFolder && (
                <ProtectionModal
                    folder={protectingFolder}
                    saving={saving}
                    onClose={() => setProtectingFolder(null)}
                    onProtect={(data) =>
                        submit(
                            () => actions.protectFolder(protectingFolder.id, data),
                            () => setProtectingFolder(null)
                        )
                    }
                    onChange={(data) =>
                        submit(
                            () => actions.changeFolderPassword(protectingFolder.id, data),
                            () => setProtectingFolder(null)
                        )
                    }
                    onRemove={(password) =>
                        submit(
                            () => actions.removeFolderProtection(
                                protectingFolder.id,
                                password
                            ),
                            () => setProtectingFolder(null)
                        )
                    }
                />
            )}

            {showSecrets && (
                <SecretFoldersModal
                    folders={secretFolders}
                    error={secretError}
                    onClose={() => setShowSecrets(false)}
                    onUnlock={async (folder, password) => {
                        try {
                            await actions.unlockFolder(folder.id, password);
                            setSecretFolders((current) =>
                                current.map((item) =>
                                    item.id === folder.id
                                        ? { ...item, is_unlocked: true }
                                        : item
                                )
                            );
                            setSecretError("");
                            return true;
                        } catch (requestError) {
                            setSecretError(
                                requestError.response?.data?.detail ||
                                    "Unable to unlock this folder."
                            );
                            return false;
                        }
                    }}
                />
            )}
        </main>
    );
}

function ProtectionModal({ folder, saving, onClose, onProtect, onChange, onRemove }) {
    const [currentPassword, setCurrentPassword] = useState("");
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");
    const validNewPassword =
        password.length >= 8 && password.length <= 128 && password === confirmation;

    return (
        <Modal title={`${folder.is_secret ? "Manage" : "Add"} protection`} onClose={onClose}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    if (!validNewPassword) return;
                    const data = {
                        ...(folder.is_secret
                            ? { current_password: currentPassword }
                            : {}),
                        password,
                        confirm_password: confirmation,
                    };
                    folder.is_secret ? onChange(data) : onProtect(data);
                }}
            >
                {folder.is_secret && (
                    <label>
                        Current password
                        <input
                            autoFocus
                            required
                            type="password"
                            value={currentPassword}
                            onChange={(event) => setCurrentPassword(event.target.value)}
                        />
                    </label>
                )}
                <label>
                    {folder.is_secret ? "New password" : "Password"}
                    <input
                        autoFocus={!folder.is_secret}
                        required
                        minLength="8"
                        maxLength="128"
                        type="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                    />
                </label>
                <label>
                    Confirm password
                    <input
                        required
                        type="password"
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                    />
                </label>
                <div className="modal-actions">
                    <button type="button" onClick={onClose}>Cancel</button>
                    {folder.is_secret && (
                        <button
                            type="button"
                            className="danger"
                            disabled={saving || !currentPassword}
                            onClick={() => onRemove(currentPassword)}
                        >
                            Remove protection
                        </button>
                    )}
                    <button
                        disabled={
                            saving ||
                            !validNewPassword ||
                            (folder.is_secret && !currentPassword)
                        }
                    >
                        {folder.is_secret ? "Change password" : "Make secret"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}

function SecretFoldersModal({ folders, error, onClose, onUnlock }) {
    const [selected, setSelected] = useState(null);
    const [password, setPassword] = useState("");
    const [unlocking, setUnlocking] = useState(false);

    async function unlock(event) {
        event.preventDefault();
        setUnlocking(true);
        const unlocked = await onUnlock(selected, password);
        setUnlocking(false);
        if (unlocked) {
            setSelected(null);
            setPassword("");
        }
    }

    return (
        <Modal title="Secret folders" onClose={onClose}>
            {error && <div className="error" role="alert">{error}</div>}
            {folders === null ? (
                <p>Loading secret folders ...</p>
            ) : folders.length === 0 ? (
                <p>There are no secret folders.</p>
            ) : (
                <div className="secret-folder-list">
                    {folders.map((folder) => (
                        <button
                            key={folder.id}
                            disabled={folder.is_unlocked}
                            onClick={() => {
                                setSelected(folder);
                                setPassword("");
                            }}
                        >
                            <BiLock /> {folder.name}
                            {folder.is_unlocked ? " - Unlocked" : ""}
                        </button>
                    ))}
                </div>
            )}
            {selected && (
                <form onSubmit={unlock}>
                    <label>
                        Password for {selected.name}
                        <input
                            autoFocus
                            required
                            type="password"
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                        />
                    </label>
                    <div className="modal-actions">
                        <button type="button" onClick={() => setSelected(null)}>
                            Cancel
                        </button>
                        <button disabled={unlocking || !password}>Unlock</button>
                    </div>
                </form>
            )}
        </Modal>
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
