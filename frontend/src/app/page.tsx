"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

const AUTH_STORAGE_KEY = "pm-authenticated";
const AUTH_USERNAME = "user";
const AUTH_PASSWORD = "password";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (saved === "true") {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (username === AUTH_USERNAME && password === AUTH_PASSWORD) {
      setIsAuthenticated(true);
      setError("");
      setPassword("");
      window.localStorage.setItem(AUTH_STORAGE_KEY, "true");
      return;
    }

    setError("Invalid credentials.");
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUsername("");
    setPassword("");
    setError("");
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  };

  if (isAuthenticated) {
    return <KanbanBoard onLogout={handleLogout} />;
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg items-center justify-center px-6">
      <div className="w-full rounded-[28px] border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
          Project Management MVP
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]">
          Sign in
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Use the MVP credentials to continue to your board.
        </p>
        <form className="mt-6 space-y-4" onSubmit={handleLogin}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-[var(--navy-dark)]">
              Username
            </span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              placeholder="user"
              required
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-[var(--navy-dark)]">
              Password
            </span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              placeholder="password"
              required
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm font-medium text-red-600">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  );
}
