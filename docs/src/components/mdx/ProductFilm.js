import React, { useRef } from "react";
import useBaseUrl from "@docusaurus/useBaseUrl";

const chapters = [
  { time: 0, en: "Introduction", zh: "产品介绍" },
  { time: 5.7, en: "Data and semantics", zh: "数据与语义" },
  { time: 17, en: "Experts and skills", zh: "专家与技能" },
  { time: 29.6, en: "Workflow", zh: "工作流" },
  { time: 42.5, en: "Dashboard templates", zh: "看板模板" },
  { time: 62.3, en: "Live dashboard case", zh: "真实看板案例" },
  { time: 83.9, en: "Preview board view", zh: "完整看板视角" },
];

export default function ProductFilm({ locale = "en" }) {
  const player = useRef(null);
  const isChinese = locale === "zh-CN";
  const source = useBaseUrl("/video/db-gpt-product-film-4k.mp4");
  const poster = useBaseUrl("/img/db-gpt-product-film-poster.jpg");

  const seek = (time) => {
    if (player.current) {
      player.current.currentTime = time;
      player.current.focus();
    }
  };

  return (
    <figure style={{ margin: "1.5rem 0" }}>
      <video
        ref={player}
        controls
        playsInline
        preload="metadata"
        poster={poster}
        aria-label={isChinese ? "DB-GPT 产品演示视频" : "DB-GPT product demo film"}
        style={{ width: "100%", aspectRatio: "16 / 9", borderRadius: "16px", background: "#101218" }}
      >
        <source src={source} type="video/mp4" />
        <a href={source}>{isChinese ? "打开视频" : "Open the video"}</a>
      </video>
      <figcaption style={{ marginTop: "0.75rem", color: "var(--ifm-color-emphasis-700)", fontSize: "0.9rem" }}>
        {isChinese
          ? "约 97 秒 · 4K · 英文演示。包含主要模块、看板模板和真实 /dashboard 案例，并实际进入 Preview 看板视角。"
          : "97 seconds · 4K · English demo. Explore the modules, dashboard templates and a real /dashboard case, including the actual switch to Preview board view."}
      </figcaption>
      <nav
        aria-label={isChinese ? "视频章节" : "Video chapters"}
        style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}
      >
        {chapters.map((chapter) => (
          <button
            key={chapter.time}
            type="button"
            className="button button--secondary button--sm"
            onClick={() => seek(chapter.time)}
          >
            {isChinese ? chapter.zh : chapter.en}
          </button>
        ))}
        <a className="button button--outline button--primary button--sm" href={source} download>
          {isChinese ? "下载 4K 视频" : "Download 4K video"}
        </a>
      </nav>
      <p style={{ fontSize: "0.85rem", marginTop: "0.75rem", color: "var(--ifm-color-emphasis-600)" }}>
        {isChinese
          ? "等待区间经过加速剪辑。模板示例与真实数据案例分别展示；部分内置封面仍保留中文。模块概览不代表所有连接器、知识检索和定时任务均已执行。"
          : "Waiting intervals are accelerated. Template illustrations and the query-backed case are shown separately; some built-in covers retain Chinese labels. Module overviews do not imply that every connector, retrieval path or scheduled task was executed."}
      </p>
    </figure>
  );
}
