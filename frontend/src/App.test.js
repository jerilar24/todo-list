import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { act } from "react";
import App from "./App";

jest.mock("axios");

beforeEach(() => {
    axios.interceptors = {
        response: { use: jest.fn(() => 1), eject: jest.fn() },
    };
    axios.post.mockResolvedValue({ data: {} });
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

test("unlocks a secret folder from the dedicated secret folders dialog", async () => {
    axios.get.mockImplementation((url) => {
        if (url === "/api/auth/me") {
            return Promise.resolve({
                data: { id: "user-1", name: "Ada", email: "ada@example.com" },
            });
        }
        if (url === "/api/folders") {
            return Promise.resolve({ data: [] });
        }
        if (url === "/api/secret-folders") {
            return Promise.resolve({
                data: [{ id: "folder-1", name: "Vault", is_secret: true, is_unlocked: false }],
            });
        }
        return Promise.resolve({ data: [] });
    });

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /secret folders/i }));
    fireEvent.click(await screen.findByRole("button", { name: /vault/i }));
    fireEvent.change(screen.getByLabelText(/password for vault/i), {
        target: { value: "correct horse" },
    });
    await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    });

    await waitFor(() =>
        expect(axios.post).toHaveBeenCalledWith(
            "/api/secret-folders/folder-1/unlock",
            { password: "correct horse" }
        )
    );
});
