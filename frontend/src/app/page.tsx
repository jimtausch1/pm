'use client';

import { KanbanBoard } from '@/components/KanbanBoard';
import { SubmitEvent, useState, useSyncExternalStore } from 'react';

const AUTH_STORAGE_KEY = 'pm-authenticated';
const AUTH_USERNAME = 'user';
const AUTH_PASSWORD = 'password';

const subscribeToAuth = (callback: () => void) => {
  window.addEventListener('storage', callback);
  return () => window.removeEventListener('storage', callback);
};
const getAuthSnapshot = () =>
  window.localStorage.getItem(AUTH_STORAGE_KEY) === 'true';
const getServerAuthSnapshot = () => false;

// localStorage writes don't fire 'storage' in the same tab, so notify subscribers manually.
const setStoredAuth = (authenticated: boolean) => {
  if (authenticated) {
    window.localStorage.setItem(AUTH_STORAGE_KEY, 'true');
  } else {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
  window.dispatchEvent(new StorageEvent('storage', { key: AUTH_STORAGE_KEY }));
};

export default function Home() {
  const isAuthenticated = useSyncExternalStore(
    subscribeToAuth,
    getAuthSnapshot,
    getServerAuthSnapshot
  );
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (username === AUTH_USERNAME && password === AUTH_PASSWORD) {
      setError('');
      setPassword('');
      setStoredAuth(true);
      return;
    }

    setError('Invalid credentials.');
  };

  const handleLogout = () => {
    setUsername('');
    setPassword('');
    setError('');
    setStoredAuth(false);
  };

  if (isAuthenticated) {
    return <KanbanBoard username={AUTH_USERNAME} onLogout={handleLogout} />;
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg items-center justify-center px-6">
      <div className="w-full rounded-[28px] border border-(--stroke) bg-white p-8 shadow-(--shadow)">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-(--gray-text)">
          Project Management MVP
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-foreground">
          Sign in
        </h1>
        <p className="mt-3 text-sm leading-6 text-(--gray-text)">
          Use the MVP credentials to continue to your board.
        </p>
        <form className="mt-6 space-y-4" onSubmit={handleLogin}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-foreground">
              Username
            </span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-(--stroke) bg-white px-3 py-2 text-sm text-foreground outline-none transition focus:border-(--primary-blue)"
              placeholder="user"
              required
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-foreground">
              Password
            </span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-(--stroke) bg-white px-3 py-2 text-sm text-foreground outline-none transition focus:border-(--primary-blue)"
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
            className="w-full rounded-full bg-(--secondary-purple) px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  );
}
