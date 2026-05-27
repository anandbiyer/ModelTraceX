/**
 * App root: the shared app-shell (header + five-tab bar) with the active tab's
 * content. Server state is provided by TanStack Query (see main.tsx); UI/session
 * state (active tab, selection, filters) by Zustand (SDD §13.4.7).
 */
import { AppShell } from "./components/AppShell";
import { useUI } from "./store/ui";
import { ChatTab } from "./tabs/ChatTab";
import { DataQualityTab } from "./tabs/DataQualityTab";
import { LineageTab } from "./tabs/LineageTab";
import { ReviewTab } from "./tabs/ReviewTab";
import { UploadTab } from "./tabs/UploadTab";

export default function App() {
  const tab = useUI((s) => s.tab);
  return (
    <AppShell>
      {tab === "Upload" && <UploadTab />}
      {tab === "Review" && <ReviewTab />}
      {tab === "Lineage" && <LineageTab />}
      {tab === "Data Quality" && <DataQualityTab />}
      {tab === "Chat" && <ChatTab />}
    </AppShell>
  );
}
