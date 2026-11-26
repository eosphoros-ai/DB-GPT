import React, { useState } from "react";

const chapters = [
  { time: 0, en: "Introduction", zh: "产品介绍" },
  { time: 5.7, en: "Data and semantics", zh: "数据与语义" },
  { time: 17, en: "Experts and skills", zh: "专家与技能" },
  { time: 29.6, en: "Workflow", zh: "工作流" },
  { time: 42.5, en: "Dashboard templates", zh: "看板模板" },
  { time: 62.3, en: "Live dashboard case", zh: "真实看板案例" },
  { time: 83.9, en: "Preview board view", zh: "完整看板视角" },
];

const youtubeUrl = "https://www.youtube.com/watch?v=tZeYgy8nuhQ";
const bilibiliUrl = "https://www.bilibili.com/video/BV1zPyJz7EdU/";

export default function ProductFilm({ locale = "en", platform }) {
  const [chapterSelection, setChapterSelection] = useState(null);
  const isChinese = locale === "zh-CN";
  const isBilibili = (platform || (isChinese ? "bilibili" : "youtube")) === "bilibili";
  const start = Math.floor(chapterSelection?.time || 0);
  const autoplay = chapterSelection ? 1 : 0;
  const source = isBilibili
    ? `https://player.bilibili.com/player.html?bvid=BV1zPyJz7EdU&p=1&autoplay=${autoplay}&t=${start}`
    : `https://www.youtube-nocookie.com/embed/tZeYgy8nuhQ?rel=0&playsinline=1&start=${start}&autoplay=${autoplay}`;
  const watchUrl = isBilibili ? bilibiliUrl : youtubeUrl;
  const chapterUrl = (time) => `${watchUrl}${isBilibili ? "?" : "&"}t=${Math.floor(time)}`;

  return (
    <figure style={{ margin: "1.5rem 0" }}>
      <iframe
        key={`${isBilibili}-${chapterSelection?.index ?? "initial"}`}
        src={source}
        title={isChinese ? "DB-GPT 产品演示 · 哔哩哔哩" : "DB-GPT product demo · YouTube"}
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen"
        allowFullScreen
        referrerPolicy="strict-origin-when-cross-origin"
        style={{ display: "block", width: "100%", aspectRatio: "16 / 9", border: 0, borderRadius: "16px", background: "#101218" }}
      />
      <figcaption style={{ marginTop: "0.75rem", color: "var(--ifm-color-emphasis-700)", fontSize: "0.9rem" }}>
        {isChinese
          ? "约 97 秒 · 4K 源片 · 英文演示。包含主要模块、看板模板和真实 /dashboard 案例，并实际进入 Preview 看板视角。"
          : "97 seconds · 4K source · English demo. Explore the modules, dashboard templates and a real /dashboard case, including the actual switch to Preview board view."}
      </figcaption>
      <nav
        aria-label={isChinese ? "视频章节" : "Video chapters"}
        style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}
      >
        {chapters.map((chapter, index) => (
          <a
            key={chapter.time}
            href={chapterUrl(chapter.time)}
            className="button button--secondary button--sm"
            onClick={(event) => {
              if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
                event.preventDefault();
                setChapterSelection({ time: chapter.time, index });
              }
            }}
          >
            {isChinese ? chapter.zh : chapter.en}
          </a>
        ))}
        <a className="button button--outline button--primary button--sm" href={watchUrl} target="_blank" rel="noopener noreferrer">
          {isChinese ? "在哔哩哔哩观看" : "Watch on YouTube"}
        </a>
      </nav>
      <p style={{ fontSize: "0.85rem", marginTop: "0.75rem", color: "var(--ifm-color-emphasis-600)" }}>
        {isChinese
          ? "播放画质取决于平台转码、账号与播放器设置；若嵌入播放不可用，请在哔哩哔哩打开。等待区间经过加速剪辑。模板示例与真实数据案例分别展示；部分内置封面仍保留中文。模块概览不代表所有连接器、知识检索和定时任务均已执行。"
          : "Playback quality depends on platform processing, your account and player settings. If the embed is unavailable, open YouTube. Waiting intervals are accelerated. Template illustrations and the query-backed case are shown separately; some built-in covers retain Chinese labels. Module overviews do not imply that every connector, retrieval path or scheduled task was executed."}
      </p>
    </figure>
  );
}
