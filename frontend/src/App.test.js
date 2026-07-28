import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import App from "./App";

jest.mock("axios");

beforeEach(() => {
    axios.interceptors = {
        response: { use: jest.fn(() => 1), eject: jest.fn() },
    };
});

test("groups lists into folders and keeps legacy lists unfiled", async () => {
    axios.get.mockImplementation((url) => {
        if (url === "/api/auth/me") {
            return Promise.resolve({
                data: { id: "user-1", name: "Ada", email: "ada@example.com" },
            });
        }
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

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() =>
        expect(
            screen.getByRole("heading", { name: /unfiled/i })
        ).toBeInTheDocument()
    );
    expect(screen.getByRole("heading", { name: /work/i })).toBeInTheDocument();
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getByText("Project")).toBeInTheDocument();
});

test("shows login when there is no valid session", async () => {
    axios.get.mockRejectedValue(new Error("offline"));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
});
