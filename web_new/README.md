
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

- [Node.js](https://nodejs.org/) >= 16
- [npm](https://npmjs.com/) >= 8
- [yarn](https://yarnpkg.com/) >= 1.22
- Supported OSes: Linux, macOS and Windows

### Installation

```sh
# Install dependencies
npm install
yarn install
```

### Usage
```sh
cp .env.example .env
```
edit the `API_BASE_URL` to the real address

```sh
# development model
npm run dev
yarn dev
```

## 🚀 Use In DB-GPT

```sh
npm run compile
yarn compile

# copy compile file to DB-GPT static file dictory
cp -rf out/* ../dbgpt/app/static 

```

## 📚 Documentation

For full documentation, visit [document](https://docs.dbgpt.site/).


## Usage
  [react-markdown](https://github.com/remarkjs/react-markdown#readme) for markdown support.
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

1. 在 /etc/hosts文件增加一行, 必须配置本地xxx.alipay.net，否则无法接入线下的登陆系统
```
127.0.0.1 local.alipay.net
```

2. 在.env文件增加下面配置
deploy in local environment:
```
ANT_BUC_GET_USER_URL='http://antbuservice.stable.alipay.net/pub/getLoginUser.json?appName=antdbgpt'
ANT_BUC_NOT_LOGIN_URL='http://antbuservice.stable.alipay.net/pub/userNotLogin.htm?appName=antdbgpt&sourceUrl='
API_BASE_URL='http://local.alipay.net:5000'
```

OR modify file next.config.js
```
  env: {
    API_BASE_URL: process.env.API_BASE_URL || "http://local.alipay.net:5000",
    GITHUB_CLIENT_ID: process.env.GITHUB_CLIENT_ID,
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
    ANT_BUC_GET_USER_URL: 'http://antbuservice.stable.alipay.net/pub/getLoginUser.json?appName=antdbgpt',
    ANT_BUC_NOT_LOGIN_URL: 'http://antbuservice.stable.alipay.net/pub/userNotLogin.htm?appName=antdbgpt&sourceUrl='
  },
```


deploy in production environment:
```
ANT_BUC_GET_USER_URL=https://antbuservice.alipay.com/pub/getLoginUser.json?appName=antdbgpt
ANT_BUC_NOT_LOGIN_URL=https://antbuservice.alipay.com/pub/userNotLogin.htm?appName=antdbgpt&sourceUrl=
```
