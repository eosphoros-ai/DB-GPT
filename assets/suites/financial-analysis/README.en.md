# Financial Report Analysis

Upload annual-report PDFs to inspect evidence-backed financial findings or compare companies and reporting years. A database connection is not required.

## Shortcuts

| Shortcut | Input | Purpose |
| --- | --- | --- |
| `/annual-report` | One annual-report PDF | Analyze operations, earnings quality, margins, expenses, cash flow and the balance sheet |
| `/compare-reports` | Two to five annual-report PDFs | Compare companies in the same reporting year, or one company across reporting years |
| `/stock-quote` | Stock names, codes, indices, industries or themes | Look up CN/BJ A-shares, ETFs, HK shares, major CN/HK indices, or check A-share sector performance, breadth, gainers and decliners |

Type `/` in the home or conversation input or start from a shortcut on this page. For an annual-report task, attach the PDFs and describe your question. Follow up in the original conversation to use the saved report.

## Reports and evidence

Stock quotes require no attachment, business database or market-data key. Asking for Tencent’s current price returns the provider’s latest quote and timestamp. Asking for its closing price checks the HKEX daily report and indicates when confirmation is pending. Mainland closing prices are checked against the listing exchange. A follow-up about turnover reads the saved quote.

Ask how optical modules or semiconductors performed today to see the Eastmoney A-share board index and up to three gainers and decliners. For a broader theme such as tech stocks, select a sector by name or number. A follow-up about earlier rankings uses the saved snapshot.

You can ask in ordinary chat or start with the stock shortcut. The agent considers the whole question before loading the skill. It can discuss a long-term investment thesis directly. If you ask for both today's performance and what it implies about demand, it retrieves the quote and then addresses the inference.

Dedicated financial tools extract values, calculate metrics, analyze topics and review findings. Reports appear in the conversation with references to source pages and calculations. Valid findings remain available when another topic fails or lacks data; only published reports count as complete.

## Supported documents

The current extractor supports Chinese-language, RMB-denominated annual-report PDFs with a text layer for non-financial companies. Scanned documents, automatic OCR, quarterly reports, currency conversion and specialized financial-company statements are not supported. Automated extraction and model review are not human verification.

Specify whether the comparison concerns peers or reporting years. Ambiguous company identities, years and baselines must be clarified before analysis. Multiple attachments alone do not request a comparison.
