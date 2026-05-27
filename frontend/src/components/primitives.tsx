/**
 * Shared design-system primitives (SDD §13.4.0). One vocabulary reused on every
 * tab: provenance pill (E/H/I/U), confidence dot, model status, filter chips,
 * buttons, cards — all drawing from the shared MVA dark tokens (translucent
 * `*-soft` fill + bright text). No bespoke palette per component.
 */
import type { ReactNode } from "react";

import type { Confidence, ModelStatus, Provenance } from "../types";

const PROV_LABEL: Record<Provenance, string> = {
  E: "LLM-extracted",
  H: "Heuristic (parser)",
  I: "LLM-inferred",
  U: "User-edited",
};

/** Provenance pill: H/E bordered mono; I renders as E + low-confidence dot; U as edited. */
export function ProvenancePill({ source }: { source: Provenance }) {
  const letter = source === "I" ? "E" : source;
  return (
    <span
      title={PROV_LABEL[source]}
      className="mono inline-flex items-center rounded border border-border bg-elev px-1.5 py-0.5 text-[10px] font-semibold text-dim"
      data-testid="provenance-pill"
      data-source={source}
    >
      {source === "U" ? "✎ U" : letter}
      {source === "I" && <ConfidenceDot confidence="Low" />}
    </span>
  );
}

const DOT: Record<Confidence, string> = {
  High: "bg-green",
  Medium: "bg-amber",
  Low: "bg-red",
};

export function ConfidenceDot({ confidence }: { confidence: Confidence }) {
  return (
    <span
      title={`confidence ${confidence.toLowerCase()}`}
      className={`ml-1 inline-block h-2 w-2 rounded-full ${DOT[confidence]}`}
      data-testid="confidence-dot"
      data-confidence={confidence}
    />
  );
}

const STATUS: Record<ModelStatus, string> = {
  Analyzed: "text-green border-green/40 bg-green-soft",
  Partial: "text-amber border-amber/40 bg-amber-soft",
  Failed: "text-red border-red/40 bg-red-soft",
};

/** Explicit Partial/Failed label, distinct from the confidence dot (NFR-7). */
export function StatusBadge({ status }: { status: ModelStatus }) {
  if (status === "Analyzed") return null;
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${STATUS[status]}`}>
      {status}
    </span>
  );
}

export function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={
        "rounded-full border px-2.5 py-1 text-xs transition-colors " +
        (active
          ? "border-accent bg-accent-soft text-accent"
          : "border-border text-dim hover:text-text")
      }
    >
      {label}
    </button>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
  testid,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
  type?: "button" | "submit";
  testid?: string;
}) {
  const base = "rounded px-3 py-1.5 text-sm font-semibold transition-colors disabled:opacity-40";
  const cls =
    variant === "primary"
      ? "bg-accent text-[var(--btn-primary-fg)] hover:brightness-110"
      : "border border-border text-dim hover:text-text hover:border-accent";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${cls}`} data-testid={testid}>
      {children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-border bg-panel p-4 shadow-elev ${className}`}>
      {children}
    </div>
  );
}

const ROLE_TAG: Record<string, string> = {
  Source: "text-accent bg-accent-soft",
  Intermediate: "text-purple bg-purple-soft",
  Output: "text-green bg-green-soft",
};

export function RoleTag({ role }: { role: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${ROLE_TAG[role] ?? "text-dim"}`}>
      {role}
    </span>
  );
}
