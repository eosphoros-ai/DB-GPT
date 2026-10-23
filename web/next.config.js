/** @type {import('next').NextConfig} */
const CopyPlugin = require("copy-webpack-plugin");
const MonacoWebpackPlugin = require("monaco-editor-webpack-plugin");
const path = require("path");

// Next.js 16 uses a config option for static export instead of `next export`.
const staticExport = process.env.DBGPT_WEB_STATIC_EXPORT === "1";

const nextConfig = {
  // Chart extensions require G2 from CommonJS. Bundle page dependencies so
  // they share Webpack module loading instead of racing native ESM imports.
  bundlePagesRouterDependencies: true,
  experimental: {
    esmExternals: "loose",
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // `next-transpile-modules` is unmaintained and does not support Next.js 16.
  // Next has had the same capability built in since 13.1.
  transpilePackages: [
    "@berryv/g2-react",
    "@antv/g2",
    "react-syntax-highlighter",
    "@antv/g6",
    "@antv/graphin",
    "@antv/gpt-vis",
  ],
  ...(staticExport ? { output: "export" } : {}),
  // Rewrites are not supported in static export mode.
  ...(staticExport
    ? {}
    : {
        async rewrites() {
          return [
            {
              source: '/api/v1/:path*',
              destination: 'http://127.0.0.1:5670/api/v1/:path*',
            },
          ];
        },
      }),
  env: {
    API_BASE_URL: "http://127.0.0.1:5670",
    GITHUB_CLIENT_ID: process.env.GITHUB_CLIENT_ID,
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
    GET_USER_URL: process.env.GET_USER_URL,
    LOGIN_URL: process.env.LOGIN_URL,
    LOGOUT_URL: process.env.LOGOUT_URL,
  },
  trailingSlash: true,
  images: { unoptimized: true },
  skipTrailingSlashRedirect: true,
  webpack: (config, { isServer, dev }) => {
    // Next 16's react-refresh loader appends an ESM-only snippet
    // (import.meta.webpackHot) to every non-.cjs module, which breaks
    // CommonJS refresh boundaries in node_modules (e.g. @babel/runtime
    // helpers under antd) with "Cannot use 'import.meta' outside a
    // module". Swap in a shim that picks the runtime variant by source
    // inspection. Dev client builds only.
    if (dev && !isServer) {
      const shim = path.join(__dirname, 'scripts/react-refresh-loader-cjs-safe.js');
      const isRefreshLoader = u => {
        const loader = typeof u === 'string' ? u : u && u.loader;
        return typeof loader === 'string' && loader.includes('@next/react-refresh-utils/dist/loader');
      };
      const walk = rules => {
        for (const rule of rules || []) {
          if (!rule || typeof rule !== 'object') continue;
          if (Array.isArray(rule.use)) {
            rule.use = rule.use.map(u => (isRefreshLoader(u) ? (typeof u === 'string' ? shim : { ...u, loader: shim }) : u));
          } else if (isRefreshLoader(rule.use)) {
            rule.use = shim;
          }
          if (Array.isArray(rule.oneOf)) walk(rule.oneOf);
          if (Array.isArray(rule.rules)) walk(rule.rules);
        }
      };
      walk(config.module.rules);
    }
    // transpilePackages still selects CommonJS entries that require ESM-only dependencies.
    config.resolve.alias = {
      ...config.resolve.alias,
      '@berryv/g2-react$': path.join(__dirname, 'node_modules/@berryv/g2-react/es/index.js'),
      '@antv/gpt-vis$': path.join(__dirname, 'node_modules/@antv/gpt-vis/dist/esm/index.js'),
      '@antv/g6$': path.join(__dirname, 'node_modules/@antv/g6/esm/index.js'),
      'react-syntax-highlighter$': path.join(__dirname, 'node_modules/react-syntax-highlighter/dist/esm/index.js'),
    };
    config.resolve.fallback = { fs: false };
    if (!isServer) {
      config.plugins.push(
        new CopyPlugin({
          patterns: [
            {
              from: path.join(
                __dirname,
                "node_modules/@oceanbase-odc/monaco-plugin-ob/worker-dist/"
              ),
              to: "static/ob-workers",
            },
          ],
        })
      );
      // 添加 monaco-editor-webpack-plugin 插件
      config.plugins.push(
        new MonacoWebpackPlugin({
          // 你可以在这里配置插件的选项，例如：
          languages: ["sql"],
          filename: "static/[name].worker.js",
        })
      );
    }
    return config;
  },
};

module.exports = nextConfig;
