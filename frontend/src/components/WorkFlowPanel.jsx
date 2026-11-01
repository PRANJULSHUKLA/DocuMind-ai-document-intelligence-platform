import {
  AlertCircle,
  CheckCircle2,
  Eye,
  ShieldCheck,
  Zap,
  Clock3,
  ArrowRight,
} from "lucide-react";

function priorityClasses(priority) {
  switch (String(priority || "").toLowerCase()) {
    case "critical":
      return {
        badge: "bg-danger-soft text-danger ring-danger",
        border: "border-danger",
        dot: "bg-danger-soft",
      };

    case "high":
      return {
        badge: "bg-warning-soft text-warning ring-warning",
        border: "border-warning",
        dot: "bg-warning-soft",
      };

    case "medium":
      return {
        badge: "bg-warning-soft text-warning ring-warning",
        border: "border-warning",
        dot: "bg-warning-soft",
      };

    default:
      return {
        badge: "bg-raised text-secondary ring-line",
        border: "border-line",
        dot: "bg-zinc-400",
      };
  }
}

function ActionCard({ action }) {
  const styles = priorityClasses(action.priority);

  return (
    <div className={`rounded-2xl border ${styles.border} bg-surface p-4`}>
      <div className="flex items-start gap-3">
        <span
          className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${styles.dot}`}
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-primary">
              {action.title || "Action"}
            </h4>

            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${styles.badge}`}
            >
              {action.priority || "medium"}
            </span>

            {action.requires_human_approval && (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
                <ShieldCheck size={11} />
                Human approval
              </span>
            )}
          </div>

          <p className="mt-2 text-sm leading-6 text-secondary">
            {action.action}
          </p>

          {action.reason && (
            <div className="mt-3">
              <p className="text-xs font-semibold tracking-wider text-secondary">
                Why
              </p>

              <p className="mt-1 text-sm leading-6 text-secondary">
                {action.reason}
              </p>
            </div>
          )}

          {action.evidence && (
            <div className="mt-3 rounded-xl bg-muted p-3">
              <p className="text-xs font-semibold tracking-wider text-secondary">
                Evidence
              </p>

              <p className="mt-1 text-sm leading-6 text-secondary">
                “{action.evidence}”
              </p>
            </div>
          )}

          {action.source && (
            <p className="mt-3 text-xs text-secondary">
              Source:{" "}
              <span className="font-medium text-secondary">
                {action.source}
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionSection({ icon, title, description, actions }) {
  return (
    <div>
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-raised text-secondary">
          {icon}
        </div>

        <div>
          <h3 className="text-sm font-semibold text-primary">{title}</h3>

          <p className="mt-1 text-xs text-secondary">{description}</p>
        </div>
      </div>

      <div className="space-y-3">
        {actions.length === 0 ? (
          <div className="rounded-2xl bg-muted p-4 text-sm text-secondary">
            No actions identified.
          </div>
        ) : (
          actions.map((action, index) => (
            <ActionCard key={`${action.title}-${index}`} action={action} />
          ))
        )}
      </div>
    </div>
  );
}

export default function WorkflowPanel({ workflow }) {
  if (!workflow) {
    return null;
  }

  const readiness = workflow.readiness_status || "insufficient_information";

  const readinessConfig = {
    ready: {
      label: "Ready",
      className: "bg-success-soft text-success",
      icon: <CheckCircle2 size={18} />,
    },

    conditionally_ready: {
      label: "Conditionally ready",
      className: "bg-warning-soft text-warning",
      icon: <AlertCircle size={18} />,
    },

    not_ready: {
      label: "Not ready",
      className: "bg-danger-soft text-danger",
      icon: <AlertCircle size={18} />,
    },

    insufficient_information: {
      label: "Insufficient information",
      className: "bg-raised text-secondary",
      icon: <Eye size={18} />,
    },
  };

  const readinessData =
    readinessConfig[readiness] || readinessConfig.insufficient_information;

  const immediateActions = workflow.immediate_actions || [];

  const upcomingActions = workflow.upcoming_actions || [];

  const monitoringItems = workflow.monitoring_items || [];

  return (
    <div className="space-y-6">
      {/* ================================================= */}
      {/* HEADER */}
      {/* ================================================= */}

      <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-on-accent">
                <Zap size={18} />
              </div>

              <div>
                <p className="text-xs font-semibold tracking-wider text-secondary">
                  Workflow Agent
                </p>

                <h2 className="text-lg font-semibold text-primary">
                  Action plan
                </h2>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-secondary">
              {workflow.overall_assessment ||
                "No overall assessment was returned."}
            </p>
          </div>

          <div
            className={`flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ${readinessData.className}`}
          >
            {readinessData.icon}
            {readinessData.label}
          </div>
        </div>
      </div>

      {/* ================================================= */}
      {/* HUMAN APPROVAL */}
      {/* ================================================= */}

      {workflow.human_approval_required && (
        <div className="rounded-2xl border border-accent bg-accent-soft/50 p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
              <ShieldCheck size={19} />
            </div>

            <div>
              <h3 className="text-sm font-semibold text-accent">
                Human approval required
              </h3>

              <p className="mt-1 text-sm leading-6 text-accent">
                {workflow.approval_reason ||
                  "One or more actions require human review before execution."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ================================================= */}
      {/* ACTION SUMMARY */}
      {/* ================================================= */}

      <div className="grid gap-4 sm:grid-cols-3">
        <WorkflowMetric
          icon={<Zap size={17} />}
          label="Immediate"
          value={immediateActions.length}
        />

        <WorkflowMetric
          icon={<ArrowRight size={17} />}
          label="Upcoming"
          value={upcomingActions.length}
        />

        <WorkflowMetric
          icon={<Clock3 size={17} />}
          label="Monitor"
          value={monitoringItems.length}
        />
      </div>

      {/* ================================================= */}
      {/* ACTIONS */}
      {/* ================================================= */}

      <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
        <div className="space-y-8">
          <ActionSection
            icon={<Zap size={16} />}
            title="Immediate actions"
            description="Resolve these items first."
            actions={immediateActions}
          />

          <div className="border-t border-line" />

          <ActionSection
            icon={<ArrowRight size={16} />}
            title="Upcoming actions"
            description="Actions to complete after the immediate issues are addressed."
            actions={upcomingActions}
          />

          <div className="border-t border-line" />

          <ActionSection
            icon={<Eye size={16} />}
            title="Monitoring"
            description="Information that should continue to be watched."
            actions={monitoringItems}
          />
        </div>
      </div>
    </div>
  );
}

function WorkflowMetric({ icon, label, value }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-raised text-secondary">
        {icon}
      </div>

      <p className="mt-4 text-xs text-secondary">{label}</p>

      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
