import { useState } from "react";
import axios from "axios";
import "./Auth.css";

function Auth({ onAuthenticated }) {
    const [mode, setMode] = useState("login");
    const [error, setError] = useState("");
    const [prefill, setPrefill] = useState("");

    return (
        <main className="auth-page">
            <div className="auth-card">
                <h1>{mode === "login" ? "Log in" : "Create account"}</h1>
                {error && <div className="error" role="alert">{error}</div>}
                {mode === "login" ? (
                    <LoginForm
                        prefill={prefill}
                        onSubmit={async (values) => {
                            try {
                                const response = await axios.post("/api/auth/login", values);
                                onAuthenticated(response.data);
                            } catch (requestError) {
                                setError(requestError.response?.data?.detail || "Login failed.");
                            }
                        }}
                    />
                ) : (
                    <SignupForm
                        onSubmit={async (values) => {
                            try {
                                await axios.post("/api/auth/signup", values);
                                setPrefill(values.email);
                                setMode("login");
                                setError("Account created. Log in to continue.");
                            } catch (requestError) {
                                const detail = requestError.response?.data?.detail;
                                setError(
                                    typeof detail === "string"
                                        ? detail
                                        : "Please check the signup form."
                                );
                            }
                        }}
                    />
                )}
                <button
                    className="link-button"
                    onClick={() => {
                        setError("");
                        setMode(mode === "login" ? "signup" : "login");
                    }}
                >
                    {mode === "login"
                        ? "Need an account? Sign up"
                        : "Already have an account? Log in"}
                </button>
            </div>
        </main>
    );
}

function LoginForm({ prefill, onSubmit }) {
    const [identifier, setIdentifier] = useState(prefill);
    const [password, setPassword] = useState("");
    return (
        <form onSubmit={(event) => {
            event.preventDefault();
            onSubmit({ identifier, password });
        }}>
            <label>Email or username<input required autoFocus value={identifier}
                onChange={(event) => setIdentifier(event.target.value)} /></label>
            <label>Password<input required type="password" value={password}
                onChange={(event) => setPassword(event.target.value)} /></label>
            <button>Log in</button>
        </form>
    );
}

function SignupForm({ onSubmit }) {
    const [values, setValues] = useState({
        name: "", email: "", username: "", password: "", confirm_password: "",
    });
    const update = (field) => (event) =>
        setValues({ ...values, [field]: event.target.value });
    return (
        <form onSubmit={(event) => {
            event.preventDefault();
            if (values.password !== values.confirm_password) return;
            onSubmit({ ...values, username: values.username || null });
        }}>
            <label>Name<input required autoFocus value={values.name} onChange={update("name")} /></label>
            <label>Email<input required type="email" value={values.email} onChange={update("email")} /></label>
            <label>Username <span>(optional)</span><input value={values.username} onChange={update("username")} /></label>
            <label>Password <span>(8+ characters)</span><input required minLength="8" maxLength="128"
                type="password" value={values.password} onChange={update("password")} /></label>
            <label>Confirm password<input required type="password"
                value={values.confirm_password} onChange={update("confirm_password")} /></label>
            {values.confirm_password && values.password !== values.confirm_password && (
                <p className="field-error">Passwords do not match.</p>
            )}
            <button disabled={values.password !== values.confirm_password}>Sign up</button>
        </form>
    );
}

export default Auth;
