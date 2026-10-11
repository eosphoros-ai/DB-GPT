
<h1 align="center">
  <a href="https://dbgpt.site"><img width="96" src="https://github.com/eosphoros-ai/DB-GPT-Web/assets/10321453/062ee3ea-fac2-4437-a392-f4bc5451d116" alt="DB-GPT"></a>
  <br>
  DB-GPT-Web
</h1>

_<p align="center">DB-GPT Chat UI, LLM to Vision.</p>_

<p align="center">
  <a href="https://github.com/eosphoros-ai/DB-GPT-Web/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg?label=License&style=flat" />
  </a>
  <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
    <img alt="Release Notes" src="https://img.shields.io/github/release/eosphoros-ai/DB-GPT" />
  </a>
  <a href="https://github.com/eosphoros-ai/DB-GPT-Web/issues">
    <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/DB-GPT-Web" />
  </a>
  <a href="https://discord.gg/7uQnPuveTY">
    <img alt="Discord" src="https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat" />
  </a>
</p>

---

## 👋 Introduction

***DB-GPT-Web*** is an **Open source chat UI** for [**DB-GPT**](https://github.com/eosphoros-ai/DB-GPT).
Also, it is a **LLM to Vision** solution. 

[DB-GPT-Web](https://dbgpt.site) is an Open source Tailwind and Next.js based chat UI for AI and GPT projects. It beautify a lot of markdown labels, such as `table`, `thead`, `th`, `td`, `code`, `h1`, `h2`, `ul`, `li`, `a`, `img`. Also it define some custom labels to adapted to AI-specific scenarios. Such as `plugin running`, `knowledge name`, `Chart view`, and so on.

## 💪🏻 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) >= 20.19
- [npm](https://npmjs.com/) 10 (CI pins 10.8.2)
- Supported OSes: Linux, macOS and Windows

### Installation

Use npm with the checked-in `package-lock.json` for dependency management.

```sh
# Install dependencies
npm ci
```

### Usage
```sh
cp .env.template .env
```
The existing backend address in `next.config.js` is `http://127.0.0.1:5670`.
Update that configuration if your backend uses a different address.

```sh
# development model
npm run dev
```

## 🚀 Use In DB-GPT

```sh
bash ../scripts/build_web_static.sh
```

`npm run build` creates a server deployment for `npm start`. `npm run compile`
uses Next's static export mode and writes `out/` for the Python-served UI.

## 📚 Documentation

For full documentation, visit [document](https://docs.dbgpt.site/).


## Usage
  [gpt-vis](https://github.com/eosphoros-ai/DB-GPT/gpt-vis) for markdown support.
  [ant-design](https://github.com/ant-design/ant-design) for ui components.
  [next.js](https://github.com/vercel/next.js) for server side rendering.
  [@antv/g2](https://github.com/antvis/g2#readme) for charts.

## License

DB-GPT-Web is licensed under the [MIT License](LICENSE).

---

Enjoy using DB-GPT-Web to build stunning UIs for your AI and GPT projects.

🌟 If you find it helpful, don't forget to give it a star on GitHub! Stars are like little virtual hugs that keep us going! We appreciate every single one we receive.

For any queries or issues, feel free to open an [issue](https://github.com/eosphoros-ai/DB-GPT-Web/issues) on the repository.

Happy coding! 😊


## antdbgptweb installation

### deploy in local environment:
