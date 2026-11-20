import type { ComponentProps } from "react";
import { useTranslation } from "react-i18next";
import type SemanticProvenance from "../../../web/new-components/chat/content/SemanticProvenance";
import QueryArtifactBlock from "../../../web/new-components/chat/content/QueryArtifactBlock";
import Markdown from "./markdown";

// Preserve saved answers and provenance without fetching current semantic
// definitions or opening authenticated application routes from an export.
export default function OfflineSemanticProvenance({
  content,
  sources,
  mode = "sources",
  querySources = [],
  readGaps = [],
}: ComponentProps<typeof SemanticProvenance>) {
  const { t } = useTranslation();
  if (mode === "answer") return <Markdown>{content}</Markdown>;
  if (!sources.length && !querySources.length && !readGaps.length) return null;
  return (
    <details className="mt-5 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
      <summary className="cursor-pointer text-sm font-semibold">
        {t("semantic_provenance_title")}
      </summary>
      <div className="mt-3 space-y-3">
        {sources.map((source) => (
          <details key={source.key}>
            <summary className="cursor-pointer text-sm">
              {source.name}
              {source.version ? ` v${source.version}` : ""}
            </summary>
            <pre className="overflow-auto whitespace-pre-wrap break-words text-xs">
              {JSON.stringify(source.snapshot, null, 2)}
            </pre>
          </details>
        ))}
        {querySources.map((source) => (
          <QueryArtifactBlock key={source.key} payload={source.payload} />
        ))}
        {readGaps.map((gap) => (
          <p key={gap.key} className="text-xs text-gray-500 dark:text-gray-400">
            {gap.connId} · {t(`semantic_provenance_status_${gap.status}`)}
          </p>
        ))}
      </div>
    </details>
  );
}
