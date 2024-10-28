// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const { ProvidePlugin } = require("webpack");
const path = require("path");
// const lightCodeTheme = require('prism-react-renderer/themes/github');
// const darkCodeTheme = require('prism-react-renderer/themes/dracula');
const {themes} = require('prism-react-renderer');
const lightCodeTheme = themes.github;
const darkCodeTheme = themes.dracula;
const isDev = process.env.NODE_ENV === "development";
const isBuildFast = !!process.env.BUILD_FAST;
const isVersioningDisabled = !!process.env.DISABLE_VERSIONING;
const versions = require("./versions.json");

console.log("versions", versions)

function isPrerelease(version) {
  return (
    version.includes('-') ||
    version.includes('alpha') ||
    version.includes('beta') ||
    version.includes('rc')
  );
}

function getLastStableVersion() {
  const lastStableVersion = versions.find((version) => !isPrerelease(version));
  if (!lastStableVersion) {
    throw new Error('unexpected, no stable Docusaurus version?');
  }
  return lastStableVersion;
}

function getNextVersionName() {
  return 'dev';
}

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'DB-GPT',
  tagline: 'Revolutionizing Database Interactions with Private LLM Technology',
  favicon: 'img/eosphoros.jpeg',

  // Set the production url of your site here
  url: 'http://docs.dbgpt.cn',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'eosphoros-ai', // Usually your GitHub org/user name.
  projectName: 'DB-GPT', // Usually your repo name.

  onBrokenLinks: isDev ? 'throw' : 'warn',
  onBrokenMarkdownLinks: isDev ? 'throw' : 'warn',

  // Even if you don't use internalization, you can use this field to set useful
  // metadata like html lang. For example, if your site is Chinese, you may want
  // to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh-CN'],
  },

  scripts: [
    {
      src: '/redirect.js',
      async: true,
    },
  ],

  markdown: {
    mermaid: true,
  },

  themes: [
    '@docusaurus/theme-mermaid',
    '@easyops-cn/docusaurus-search-local',
  ],

  plugins: [
    () => ({
      name: "custom-webpack-config",
      configureWebpack: () => ({
        plugins: [
          new ProvidePlugin({
            process: require.resolve("process/browser"),
          }),
        ],
        resolve: {
          fallback: {
            path: false,
            url: false,
          },
        },
        module: {
          rules: [
            {
              test: /\.m?js/,
              resolve: {
                fullySpecified: false,
              },
            },
            {
              test: /\.py$/,
              loader: "raw-loader",
              resolve: {
                fullySpecified: false,
              },
            },
            {
              test: /\.ipynb$/,
              loader: "raw-loader",
              resolve: {
                fullySpecified: false,
              },
            },
          ],
        },
      }),
    }),
  ],

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          includeCurrentVersion: true,
          // lastVersion: "current",
          lastVersion: isDev || isBuildFast || isVersioningDisabled ? "current" : getLastStableVersion(),
          onlyIncludeVersions: (() => {
            if (isBuildFast) {
                return ['current'];
            } else if (!isVersioningDisabled && (isDev)) {
              return ['current', ...versions.slice(0, 2)];
            }
            return undefined;
          })(),
          versions: {
            current: {
              label: `${getNextVersionName()}`,
            },
          },
          remarkPlugins: [
            [require("@docusaurus/remark-plugin-npm2yarn"), { sync: true }],
          ],

          async sidebarItemsGenerator({
            defaultSidebarItemsGenerator,
            ...args
          }){
            const sidebarItems = await defaultSidebarItemsGenerator(args);
            sidebarItems.forEach((subItem) => {
              // This allows breaking long sidebar labels into multiple lines
              // by inserting a zero-width space after each slash.
              if (
                "label" in subItem &&
                subItem.label &&
                subItem.label.includes("/")
              ){
                subItem.label = subItem.label.replace("/\//g", "\u200B");
              }
            });
            return sidebarItems;
          }
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
        },

        pages: {
          remarkPlugins: [require("@docusaurus/remark-plugin-npm2yarn")],
        },
        blog: {
          showReadingTime: true,
        },
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      defaultClassicDocs: '/docs/get_started',
      // Replace with your project's social card
      navbar: {
        hideOnScroll: true,
        logo: {
          alt: 'DB-GPT Logo',
          src: 'img/dbgpt_logo.svg',
          srcDark: 'img/DB-GPT_LOGO_White.svg',
          href: "/docs/overview"
        },

        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
            to: "/docs/overview",
          },
          {
            type: 'docSidebar',
            sidebarId: "tutorials",
            to: '/turtorials', 
            label: 'Turtorial', 
            position: 'left'
          },
          {
            href: 'https://github.com/eosphoros-ai/community',
            position: 'left',
            label: "Community",
            className: 'header-community-link',

          },
          {
            type: "docsVersionDropdown",
            position: "right",
            dropdownItemsAfter: [{to: '/versions', label: 'All versions'}],
            dropdownActiveClassDisabled: true,
          },
          {
            href: 'https://github.com/eosphoros-ai/DB-GPT',
            position: 'right',
            className: 'header-github-link',
          },
          {
            href: 'https://huggingface.co/eosphoros',
            position: 'right',
            label: "HuggingFace",
            className: 'header-huggingface-link',
          },
          {
            href: 'https://www.yuque.com/eosphoros/dbgpt-docs/bex30nsv60ru0fmx',
            position: 'left',
            label: "中文文档",
          },
          {to: '/blog', label: 'Blog', position: 'left'},
        ],
      },
      footer: {
        style: 'light',
        links: [
          {
            title: 'Community',
            items: [
              {
                label: 'Discord',
                href: 'https://discord.gg/erwfqcMP',
              },
              {
                label: "Dockerhub",
                href: "https://hub.docker.com/u/eosphorosai",
              },
            ],
          },
          {
            title: "Github",
            items: [
              {
                label: 'Github',
                href: 'https://github.com/eosphoros-ai/DB-GPT',
              },
              {
                label: "HuggingFace",
                href: "https://huggingface.co/eosphoros"
              }
            ]
          },
          {
            title: 'More',
            items: [
              {
                label: 'Hacker News',
                href: 'https://news.ycombinator.com/item?id=36038815',
              },
              {
                label: 'Twitter',
                href: 'https://twitter.com/DbGpt80100',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} DB-GPT`,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
      },
      colorMode: {
        defaultMode: 'light',
        disableSwitch: false,
        respectPrefersColorScheme: false,
      },
    }),
};

module.exports = config;
