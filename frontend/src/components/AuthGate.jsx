import { useEffect, useState } from "react";
import {
  clearSession,
  developmentIdentity,
  initializeAuth,
  signIn,
  signInConfigured,
  signOut,
} from "../services/auth";

export default function AuthGate({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(
    !developmentIdentity && signInConfigured,
  );
  const [error, setError] = useState("");

  useEffect(() => {
    if (developmentIdentity || !signInConfigured) return;
    let cancelled = false;
    initializeAuth()
      .then((result) => {
        if (!cancelled) setUser(result);
      })
      .catch(() => {
        if (!cancelled)
          setError("Unable to complete sign-in. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    const expire = () => {
      void clearSession();
      setUser(null);
      setError("Your session has expired. Please sign in again.");
    };
    window.addEventListener("documind:session-expired", expire);
    return () => {
      cancelled = true;
      window.removeEventListener("documind:session-expired", expire);
    };
  }, []);

  if (developmentIdentity || user) {
    return (
      <>
        <div className="session-indicator flex flex-wrap items-center justify-end gap-3 border-b border-line bg-sidebar px-5 py-2 text-xs text-secondary">
          <span>
            {developmentIdentity
              ? "Local development workspace"
              : user.profile.name || "Private workspace"}
          </span>
          {!developmentIdentity && (
            <button
              onClick={() =>
                signOut().catch(() =>
                  setError("Unable to sign out. Please try again."),
                )
              }
              className="font-semibold underline"
            >
              Sign out
            </button>
          )}
          {error && <span role="alert">{error}</span>}
        </div>
        {children}
      </>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted px-6 text-primary">
      <section className="w-full max-w-md rounded-2xl border border-line bg-surface p-8 shadow-sm">
        <p className="text-xs font-semibold tracking-widest text-secondary">
          DocuMind AI
        </p>
        <h1 className="mt-3 text-2xl font-semibold">
          Your private document workspace
        </h1>
        <p className="mt-3 text-sm leading-6 text-secondary">
          Understand documents, review evidence, and turn findings into useful
          actions.
        </p>
        {loading ? (
          <p className="mt-6 text-sm" role="status">
            Checking your session…
          </p>
        ) : signInConfigured ? (
          <button
            className="mt-6 w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-on-accent"
            onClick={() =>
              signIn().catch(() =>
                setError("Unable to open sign-in. Please try again."),
              )
            }
          >
            Sign in to continue
          </button>
        ) : (
          <p className="mt-6 rounded-xl bg-muted p-4 text-sm text-secondary">
            Sign-in is being set up. Contact your workspace administrator for
            access.
          </p>
        )}
        {error && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}
