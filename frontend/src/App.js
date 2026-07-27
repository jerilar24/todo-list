import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import "./App.css";
import ListToDoLists from "./ListTodoList";
import ToDoList from "./TodoList";

function App() {
    const [folders, setFolders] = useState(null);
    const [listSummaries, setListSummaries] = useState(null);
    const [selectedItem, setSelectedItem] = useState(null);
    const [error, setError] = useState("");

    const reloadData = useCallback(async () => {
        try {
            const [folderResponse, listResponse] = await Promise.all([
                axios.get("/api/folders"),
                axios.get("/api/lists"),
            ]);
            setFolders(folderResponse.data);
            setListSummaries(listResponse.data);
            setError("");
        } catch (requestError) {
            console.error(requestError);
            setError("Unable to load your folders and to-do lists.");
        }
    }, []);

    useEffect(() => {
        reloadData();
    }, [reloadData]);

    async function mutate(request) {
        try {
            await request();
            await reloadData();
            return true;
        } catch (requestError) {
            console.error(requestError);
            setError(requestError.response?.data?.detail || "The change could not be saved.");
            return false;
        }
    }

    const actions = {
        createFolder: (name) => mutate(() => axios.post("/api/folders", { name })),
        renameFolder: (id, name) =>
            mutate(() => axios.patch(`/api/folders/${id}`, { name })),
        deleteFolder: (id, listAction) =>
            mutate(() =>
                axios.delete(`/api/folders/${id}`, {
                    params: { list_action: listAction },
                })
            ),
        createList: (name, folderId) =>
            mutate(() =>
                axios.post("/api/lists", {
                    name,
                    folder_id: folderId || null,
                })
            ),
        updateList: (id, updates) =>
            mutate(() => axios.patch(`/api/lists/${id}`, updates)),
        deleteList: (id) => mutate(() => axios.delete(`/api/lists/${id}`)),
    };

    if (selectedItem === null) {
        return (
            <div className="App">
                {error && <div className="error" role="alert">{error}</div>}
                <ListToDoLists
                    folders={folders}
                    listSummaries={listSummaries}
                    actions={actions}
                    handleSelectList={setSelectedItem}
                />
            </div>
        );
    }

    return (
        <div className="App">
            {error && <div className="error" role="alert">{error}</div>}
            <ToDoList
                listId={selectedItem}
                folders={folders || []}
                handleBackButton={async () => {
                    setSelectedItem(null);
                    await reloadData();
                }}
                handleListChanged={reloadData}
            />
        </div>
    );
}

export default App;
