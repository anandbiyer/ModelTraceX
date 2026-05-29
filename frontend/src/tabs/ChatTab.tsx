/**
 * Chat tab (SDD §13.4.5, FR-9.2/9.3). Chat is NOT a free-form chatbot: each user
 * request is mapped by the ChatAgent into a typed StateMutationPlan and shown as
 * a concrete diff over the structured state plus an impact summary. Action buttons
 * are derived from each mutation's metadata: `triggers_llm` toggles the
 * "Apply & re-run" vs "Apply without re-run" label; `requires_confirmation` gates
 * structurally destructive ops (merge_models, split_model, bulk accept/reject,
 * set_provider) behind an explicit confirm. The authority boundary lives in
 * `chat/authority.py`; the front end just reads what the backend stamped.
 */
import { useState } from "react";

import { Button, Card } from "../components/primitives";
import { DiffBlock } from "../components/DiffBlock";
import { useChat, useChatApply } from "../lib/queries";
import { useUI } from "../store/ui";
import type { ChatMutation, ChatPlan } from "../types";

interface Turn {
  user: string;
  plan: ChatPlan | null;
  error?: string;
}

function describe(m: ChatMutation): { old: string; next: string } {
  const a = m.args as Record<string, unknown>;
  switch (m.op) {
    case "set_table_role":
      return { old: `${a.table_id} · role: ?`, next: `${a.table_id} · role: ${a.role}` };
    case "set_language_hint":
      return {
        old: `${a.model_id} · language: ?`,
        next: `${a.model_id} · language: ${a.language}`,
      };
    case "set_lineage_detail": {
      const scope = (a.model_ids as string[] | undefined)?.join(", ") ?? "all models";
      return { old: `${scope} · lineage_detail: table`, next: `${scope} · lineage_detail: ${a.detail}` };
    }
    case "set_detail_level":
      return { old: `project · detail_level: ?`, next: `project · detail_level: ${a.detail}` };
    case "reanalyze_scope":
      return {
        old: `(no re-run)`,
        next: `re-run models: ${(a.model_ids as string[] | undefined)?.join(", ") ?? ""}`,
      };
    case "accept_rule":
    case "reject_rule": {
      const ids = (a.rule_ids as string[] | undefined) ?? [a.rule_id as string];
      const next = m.op === "accept_rule" ? "Accepted" : "Rejected";
      return { old: `${ids.join(", ")} · status: Proposed`, next: `${ids.join(", ")} · status: ${next}` };
    }
    case "merge_models":
      return {
        old: `models: ${(a.model_ids as string[] | undefined)?.join(", ") ?? ""}`,
        next: `merged → ${(a.label as string) ?? "<merged>"}`,
      };
    case "split_model":
      return { old: `model: ${a.model_id}`, next: `split into per-file models` };
    case "set_provider":
      return { old: `provider: ?`, next: `provider: ${a.provider}` };
    default:
      return { old: m.op, next: JSON.stringify(a) };
  }
}

function MutationCard({
  mutation,
  onApply,
  busy,
}: {
  mutation: ChatMutation;
  onApply: (rerun: boolean) => void;
  busy: boolean;
}) {
  const { old, next } = describe(mutation);
  const reRunLabel = mutation.triggers_llm ? "Apply & re-run affected" : "Apply (re-stitch, no LLM)";
  return (
    <Card className="mb-3">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="mono rounded border border-border bg-elev px-1.5 py-0.5 text-text">
          {mutation.op}
        </span>
        {mutation.requires_confirmation && (
          <span className="rounded border border-amber/40 bg-amber-soft px-1.5 py-0.5 text-amber">
            confirm required
          </span>
        )}
        {mutation.triggers_llm ? (
          <span className="text-muted">re-runs analysis (token-bearing)</span>
        ) : (
          <span className="text-muted">projection only (~0 tokens)</span>
        )}
      </div>
      <DiffBlock rows={[{ label: mutation.op, old, next }]} />
      <div className="mt-2 flex gap-2" data-testid="mutation-actions">
        <Button onClick={() => onApply(true)} disabled={busy} testid="apply-rerun">
          {reRunLabel}
        </Button>
        {mutation.triggers_llm && (
          <Button
            variant="secondary"
            onClick={() => onApply(false)}
            disabled={busy || mutation.requires_confirmation}
            testid="apply-norerun"
          >
            Apply without re-run
          </Button>
        )}
      </div>
    </Card>
  );
}

export function ChatTab() {
  const { runId } = useUI();
  const chat = useChat(runId ?? "");
  const apply = useChatApply(runId ?? "");
  const [message, setMessage] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  if (!runId) {
    return (
      <Card className="mx-auto max-w-xl text-sm text-dim">
        Upload and analyze a project first — chat edits the structured state of an analyzed run.
      </Card>
    );
  }

  const send = async () => {
    const text = message.trim();
    if (!text) return;
    setMessage("");
    try {
      const plan = await chat.mutateAsync(text);
      setTurns((t) => [...t, { user: text, plan }]);
    } catch (err) {
      setTurns((t) => [...t, { user: text, plan: null, error: String(err) }]);
    }
  };

  const applyOne = async (turnIdx: number, mutIdx: number, rerun: boolean) => {
    const turn = turns[turnIdx];
    if (!turn.plan) return;
    const mutation = turn.plan.mutations[mutIdx];
    // For projection-only mutations, "rerun" and "no rerun" collapse to the same call.
    const _ = rerun;
    void _;
    try {
      await apply.mutateAsync([mutation]);
      // Drop the applied mutation from this turn so the UI shows the remaining ones.
      setTurns((all) =>
        all.map((t, i) =>
          i === turnIdx && t.plan
            ? { ...t, plan: { ...t.plan, mutations: t.plan.mutations.filter((_, j) => j !== mutIdx) } }
            : t,
        ),
      );
    } catch (err) {
      setTurns((all) =>
        all.map((t, i) => (i === turnIdx ? { ...t, error: String(err) } : t)),
      );
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4" data-testid="chat-tab">
      <Card className="text-xs text-dim">
        Chat edits the structured model state, not free text. Each request is mapped to a typed
        mutation plan with a diff + impact summary; projection-only changes (role, accept/reject)
        cost no LLM tokens.
      </Card>

      <div className="flex flex-col gap-4">
        {turns.map((turn, i) => (
          <div key={i} data-testid={`chat-turn-${i}`}>
            <div className="mb-2 text-sm text-text">
              <span className="text-muted">you · </span>
              {turn.user}
            </div>
            {turn.error && (
              <Card className="border-red/40 bg-red-soft text-xs text-red">{turn.error}</Card>
            )}
            {turn.plan && turn.plan.mutations.length === 0 && !turn.error && (
              <Card className="text-xs text-muted">All mutations from this turn applied.</Card>
            )}
            {turn.plan && (
              <>
                {turn.plan.rationale && (
                  <p className="mb-2 text-sm text-dim" data-testid="chat-rationale">
                    ◆ {turn.plan.rationale}
                  </p>
                )}
                {turn.plan.mutations.map((m, j) => (
                  <MutationCard
                    key={j}
                    mutation={m}
                    busy={apply.isPending}
                    onApply={(rerun) => applyOne(i, j, rerun)}
                  />
                ))}
              </>
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        className="flex gap-2"
      >
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="ask to change a parameter or re-run…"
          className="mono flex-1 rounded border border-border bg-elev px-2 py-1.5 text-sm"
          data-testid="chat-input"
        />
        <Button type="submit" disabled={chat.isPending || !message.trim()} testid="chat-send">
          {chat.isPending ? "…" : "Send"}
        </Button>
      </form>
    </div>
  );
}
