/**
 * Chat tab placeholder. The chat-to-state agent (typed StateMutationPlan, diff
 * blocks, targeted re-run, authority boundary) is Phase 3 (P3-1/P3-4). The tab
 * exists now so the five-tab bar (FR-9.1) is complete; the contract hint states
 * that chat edits the structured state, not free text.
 */
import { Card } from "../components/primitives";

export function ChatTab() {
  return (
    <Card className="mx-auto max-w-xl text-sm text-dim">
      <p className="mb-2 font-semibold text-text">Chat edits the structured model state, not free text.</p>
      <p className="text-muted">
        Natural-language commands (e.g. "treat staging tables as intermediate", "raise the scoring
        model to column level") map to a typed mutation plan with an impact summary and targeted
        re-run. This arrives in Phase 3.
      </p>
      <input
        disabled
        placeholder="ask to change a parameter or re-run… (Phase 3)"
        className="mono mt-3 w-full rounded border border-border bg-elev px-2 py-1 text-xs"
      />
    </Card>
  );
}
