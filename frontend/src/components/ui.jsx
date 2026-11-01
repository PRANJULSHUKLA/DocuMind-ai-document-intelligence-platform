import { useEffect, useId, useRef } from "react";
import { AlertCircle, Info, Loader2, X } from "lucide-react";

export function Button({
  variant = "secondary",
  className = "",
  children,
  ...props
}) {
  return (
    <button
      type="button"
      className={`ui-button ui-button--${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
export function Card({
  as: Tag = "section",
  className = "",
  children,
  ...props
}) {
  return (
    <Tag className={`ui-card ${className}`} {...props}>
      {children}
    </Tag>
  );
}
export function Input({ className = "", ...props }) {
  return <input className={`ui-input ${className}`} {...props} />;
}
export function Badge({ tone = "neutral", children }) {
  return <span className={`ui-badge ui-badge--${tone}`}>{children}</span>;
}
export function StatusMessage({ title, children, tone = "info", action }) {
  const Icon = tone === "error" ? AlertCircle : Info;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`ui-status ui-status--${tone}`}
    >
      <Icon size={18} aria-hidden="true" />
      <div>
        <p className="font-semibold">{title}</p>
        {children && <div className="mt-1 text-sm">{children}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}
export function Skeleton({ label = "Loading", rows = 3 }) {
  return (
    <div role="status" aria-label={label} className="space-y-3 p-5">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="ui-skeleton" />
      ))}
    </div>
  );
}
export function TabBar({ label, tabs, value, onChange }) {
  const refs = useRef([]);
  return (
    <div role="tablist" aria-label={label} className="ui-tabs">
      {tabs.map((tab, i) => (
        <button
          key={tab.value}
          ref={(el) => {
            refs.current[i] = el;
          }}
          role="tab"
          type="button"
          aria-selected={value === tab.value}
          tabIndex={value === tab.value ? 0 : -1}
          onClick={() => onChange(tab.value)}
          onKeyDown={(event) => {
            const next =
              event.key === "ArrowRight"
                ? (i + 1) % tabs.length
                : event.key === "ArrowLeft"
                  ? (i + tabs.length - 1) % tabs.length
                  : event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? tabs.length - 1
                      : null;
            if (next !== null) {
              event.preventDefault();
              onChange(tabs[next].value);
              refs.current[next]?.focus();
            }
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
export function Dialog({ open, title, onClose, children }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
      previous?.focus();
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="ui-dialog"
      aria-label={title}
      onCancel={onClose}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const targets = [
          ...event.currentTarget.querySelectorAll(
            'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
          ),
        ].filter((el) => el.getClientRects().length);
        const first = targets[0],
          last = targets.at(-1);
        if (!first) {
          event.preventDefault();
          return;
        }
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
    >
      <header className="flex items-center justify-between gap-4">
        <h2>{title}</h2>
        <Button aria-label="Close dialog" onClick={onClose}>
          <X size={18} />
        </Button>
      </header>
      <div className="mt-5">{children}</div>
    </dialog>
  );
}
export function Tooltip({ label, children }) {
  const id = useId();
  return (
    <span className="ui-tooltip" tabIndex={0} aria-describedby={id}>
      {children}
      <span id={id} role="tooltip">
        {label}
      </span>
    </span>
  );
}
export function ListHeader({ title, description, action }) {
  return (
    <div className="ui-list-header">
      <div>
        <h3>{title}</h3>
        {description && (
          <p className="mt-1 text-sm text-secondary">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
export function Busy({ children }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
      {children}
    </span>
  );
}
