import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import App from "./App";

jest.mock("axios");

test("groups lists into folders and keeps legacy lists unfiled", async () => {
    axios.get.mockImplementation((url) => {
        if (url === "/api/folders") {
            return Promise.resolve({
                data: [{ id: "folder-1", name: "Work" }],
            });
        }
        return Promise.resolve({
            data: [
                { id: "list-1", name: "Inbox", item_count: 1, folder_id: null },
                {
                    id: "list-2",
                    name: "Project",
                    item_count: 2,
                    folder_id: "folder-1",
                },
            ],
        });
    });

    render(<App />);

    expect(screen.getByText(/loading to-do lists/i)).toBeInTheDocument();
    await waitFor(() =>
        expect(
            screen.getByRole("heading", { name: /unfiled/i })
        ).toBeInTheDocument()
    );
    expect(screen.getByRole("heading", { name: /work/i })).toBeInTheDocument();
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getByText("Project")).toBeInTheDocument();
});

test("shows an error when initial data cannot be loaded", async () => {
    axios.get.mockRejectedValue(new Error("offline"));
    render(<App />);

    expect(
        await screen.findByText("Unable to load your folders and to-do lists.")
    ).toBeInTheDocument();
});
