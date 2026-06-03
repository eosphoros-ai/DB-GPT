#!/usr/bin/env python3
"""Fill English locale for phase2 keys using existing zh->en mapping in locales."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "web" / "locales"
CJK = re.compile(r"[\u4e00-\u9fff]")
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)

# Manual EN for strings not in existing locale map
MANUAL: dict[str, str] = {
    "删除成功": "Deleted successfully",
    "待处理": "Pending",
    "确认删除吗？": "Are you sure you want to delete?",
    "轮待回放...": " rounds pending replay...",
    "搜索知识库": "Search knowledge base",
    "可以问我任何问题": "Ask me anything",
    "数据集数量": "Dataset count",
    "文件下载失败": "File download failed",
    "没有匹配的对话": "No matching conversations",
    "新对话": "New chat",
    "数据格式错误": "Invalid data format",
    "获取评估列表失败": "Failed to load evaluation list",
    "分享链接已复制到剪贴板！": "Share link copied to clipboard!",
    "终止话题": "End topic",
    "搜索数据库": "Search database",
    "权限管理": "Permission management",
    "加载历史对话失败": "Failed to load chat history",
    "场景类型": "Scene type",
    "请输入测试问题": "Enter a test question",
    "sql查询": "SQL query",
    "确认删除吗": "Confirm delete?",
    "个数据库可用": " databases available",
    "个技能可用": " skills available",
    "暂无合适的可视化视图": "No suitable chart view",
    "测评结果": "Evaluation results",
    "加载示例失败: ": "Failed to load example: ",
    "添加成功": "Added successfully",
    "刚刚": "Just now",
    "暂无历史记录": "No history yet",
    "步": " steps",
    "未找到匹配的知识库": "No matching knowledge base",
    "数值": "Numeric",
    "并行参数": "Parallel parameters",
    "清除历史": "Clear history",
    "返回": "Back",
    "执行过程": "Execution process",
    "评分明细": "Score details",
    "暂无可用知识库": "No knowledge base available",
    "暂停回复": "Pause reply",
    "创建分享链接失败，请稍后重试": "Failed to create share link, please try again later",
    "个人": "Personal",
    "评测数据": "Evaluation data",
    "请先开始一段对话再分享": "Start a conversation before sharing",
    "召回结果": "Recall results",
    "再来一次": "Try again",
    "发起成功": "Started successfully",
    "加载失败": "Load failed",
    "向量检索设置": "Vector retrieval settings",
    "发起测评": "Start evaluation",
    "储存方式": "Storage mode",
    "储存类型": "Storage type",
    "编辑数据集": "Edit dataset",
    "Header信息格式不正确,请输入有效的JSON格式": "Invalid Header JSON format",
    "数据集名称": "Dataset name",
    "更新时间": "Updated at",
    "表单验证失败:": "Form validation failed:",
    "正在加载示例...": "Loading example...",
    "上传文件": "Upload file",
    "上传成功": "Uploaded successfully",
    "成员": "Members",
    "项": " items",
    " 项": " items",
    "个输出": " outputs",
    " 个输出": " outputs",
    "月": "/",
    "日": "",
    "复制SQL": "Copy SQL",
    "反馈成功": "Feedback submitted",
    "数据类型": "Data type",
    "星期六": "Saturday",
    "或许你想问：": "You might want to ask:",
    "列信息": "Column info",
    "字段列表：": "Field list:",
    "复制全部": "Copy all",
    "昨天": "Yesterday",
    "操作成功": "Operation successful",
    "星期二": "Tuesday",
    "查看回复引用": "View reply reference",
    "星期四": "Thursday",
    "星期五": "Friday",
    "项)": " items)",
    "浏览器阻止了弹出窗口，请允许后重试": "Popup blocked by browser, please allow and retry",
    "暂无文件": "No files yet",
    "下载成功": "Download successful",
    "数据规模：": "Data size:",
    "星期一": "Monday",
    "下载失败": "Download failed",
    "星期日": "Sunday",
    "请稍候，结果即将显示": "Please wait, results will appear shortly",
    "数据观察": "Data observation",
    "星期三": "Wednesday",
    "我可以帮您：": "I can help you:",
    "今天": "Today",
    "点击分析当前异常": "Click to analyze current anomaly",
    "点击左侧的步骤卡片以显示执行结果": "Click a step card on the left to view results",
    "回复引用": "Reply reference",
    "选择一个步骤查看详情": "Select a step to view details",
    "链接": "Link",
    "SQL已复制到剪贴板": "SQL copied to clipboard",
    "列": "Column",
    "暂无输出结果": "No output yet",
    "代码文件": "Code file",
    "分析总结": "Analysis summary",
    "渲染结果": "Rendered result",
    "源代码": "Source code",
    "图表": "Chart",
    "代码": "Code",
    "管理员（工号，去前缀0）：": "Admin (employee ID, leading zeros removed):",
    "管理数据库 →": "Manage databases →",
    "文件暂不可下载": "File not available for download",
    "个知识库可用": " knowledge bases available",
    "文件预览失败": "File preview failed",
    "管理技能 →": "Manage skills →",
    "暂无可用数据库": "No database available",
    "测评状态": "Evaluation status",
    "添加数据集": "Add dataset",
    "失败": "Failed",
    "确认删除这条对话记录吗？": "Delete this conversation?",
    "管理知识库 →": "Manage knowledge →",
    "评测指标": "Evaluation metrics",
    "未找到匹配的技能": "No matching skills found",
    "查看日志与评分": "View logs and scores",
    "score阈值": "Score threshold",
    "召回配置": "Recall configuration",
    "编码": "Encoding",
    "验证通过": "Validation passed",
    "召回方法": "Recall method",
    "运行中": "Running",
    "上传图标": "Upload icon",
    "测试": "Test",
    "测试问题": "Test question",
    "Response Mapping配置格式不正确,请输入有效的JSON格式": "Invalid Response Mapping JSON format",
    "数据集": "Dataset",
    "关联问题:": "Related questions:",
    "请输入密码": "Enter password",
    "你的反馈助我进步": "Your feedback helps me improve",
    "暂无可用技能": "No skills available",
    "场景参数": "Scene parameters",
    "未找到匹配的数据库": "No matching database found",
    "测评编码": "Evaluation code",
    "上传中": "Uploading",
    "帮助中心": "Help center",
    "搜索对话...": "Search conversations...",
    "标题": "Title",
    "名称必须是字母、数字或下划线，并使用下划线分隔多个单词": "Name must use letters, numbers, or underscores, separated by underscores",
    "值": "Value",
}


def parse(path: Path) -> dict[str, str]:
    return dict(PAIR.findall(path.read_text(encoding="utf-8")))


def patch_file(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, val in updates.items():
        esc = val.replace("\\", "\\\\").replace("'", "\\'")
        text, _ = re.subn(
            rf"^(\s+{re.escape(key)}\s*:\s*)'(?:\\'|[^'])*'",
            rf"\1'{esc}'",
            text,
            count=1,
            flags=re.M,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    total = 0
    for mod in ("common", "chat", "flow"):
        en_p = LOCALES / "en" / f"{mod}.ts"
        zh_p = LOCALES / "zh" / f"{mod}.ts"
        en, zh = parse(en_p), parse(zh_p)
        zh_to_en = {zh[k]: en[k] for k in en if k in zh and not CJK.search(en[k])}
        updates: dict[str, str] = {}
        for key, en_val in en.items():
            if not CJK.search(en_val):
                continue
            z = zh.get(key, en_val)
            new = zh_to_en.get(z) or MANUAL.get(z)
            if new and not CJK.search(new):
                updates[key] = new
        if updates:
            patch_file(en_p, updates)
            total += len(updates)
            print(f"{mod}: {len(updates)} en values fixed")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
