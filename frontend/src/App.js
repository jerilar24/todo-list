import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import "./App.css";
import Auth from "./Auth";
import ListToDoLists from "./ListTodoList";
import ToDoList from "./TodoList";

const IDLE_MS = 30 * 60 * 1000;
const ACTIVITY_REFRESH_MS = 5 * 60 * 1000;

function Workspace({ user, onLogout }) {
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
                <AppHeader user={user} onLogout={onLogout} />
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
            <AppHeader user={user} onLogout={onLogout} />
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

function AppHeader({ user, onLogout }) {
    return (
        <header className="app-header">
            <span>Signed in as <strong>{user.name}</strong></span>
            <button onClick={onLogout}>Log out</button>
        </header>
    );
}

function App() {
    const [user, setUser] = useState(undefined);

    useEffect(() => {
        axios.get("/api/auth/me")
            .then((response) => setUser(response.data))
            .catch(() => setUser(null));
    }, []);

    useEffect(() => {
        const interceptor = axios.interceptors.response.use(
            (response) => response,
            (error) => {
                if (error.response?.status === 401) setUser(null);
                return Promise.reject(error);
            }
        );
        return () => axios.interceptors.response.eject(interceptor);
    }, []);

    useEffect(() => {
        if (!user) return undefined;
        let idleTimer;
        let lastRefresh = Date.now();
        const logout = () => {
            axios.post("/api/auth/logout").finally(() => setUser(null));
        };
        const activity = () => {
            clearTimeout(idleTimer);
            idleTimer = setTimeout(logout, IDLE_MS);
            if (Date.now() - lastRefresh >= ACTIVITY_REFRESH_MS) {
                lastRefresh = Date.now();
                axios.post("/api/auth/activity").catch(() => {});
            }
        };
        ["pointerdown", "keydown", "touchstart"].forEach((event) =>
            window.addEventListener(event, activity)
        );
        activity();
        return () => {
            clearTimeout(idleTimer);
            ["pointerdown", "keydown", "touchstart"].forEach((event) =>
                window.removeEventListener(event, activity)
            );
        };
    }, [user]);

    if (user === undefined) return <div className="loading">Loading ...</div>;
    if (user === null) return <Auth onAuthenticated={setUser} />;
    return (
        <Workspace
            user={user}
            onLogout={() =>
                axios.post("/api/auth/logout").finally(() => setUser(null))
            }
        />
    );
}

export default App;
