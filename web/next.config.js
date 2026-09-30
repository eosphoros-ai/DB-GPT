/** @type {import('next').NextConfig} */
const CopyPlugin = require('copy-webpack-plugin');
const MonacoWebpackPlugin = require('monaco-editor-webpack-plugin');
const { PHASE_DEVELOPMENT_SERVER } = require('next/constants');
const path = require('node:path');

module.exports = phase => {
  const development = phase === PHASE_DEVELOPMENT_SERVER;
  const staticExport = process.env.DBGPT_WEB_STATIC_EXPORT === '1';
  return {
    distDir: process.env.NEXT_DIST_DIR || '.next',
    ...(staticExport ? { output: 'export' } : {}),
    allowedDevOrigins: ['127.0.0.1'],
    // Next 16's Pages Router indicator can receive isrManifest before its
    // router is initialized. Disable only the badge; error overlays and HMR stay on.
    devIndicators: false,
    onDemandEntries: { maxInactiveAge: 25 * 1000, pagesBufferLength: 2 },
    ...(process.platform === 'win32' && !development ? { experimental: { cpus: 1 } } : {}),
    typescript: {
      ignoreBuildErrors: false,
      tsconfigPath: process.env.DBGPT_BUILD_TSCONFIG || 'tsconfig.json',
    },
    ...(!staticExport
      ? {
          async rewrites() {
            return [{ source: '/api/v1/:path*', destination: 'http://127.0.0.1:5670/api/v1/:path*' }];
          },
        }
      : {}),
    env: {
      API_BASE_URL: 'http://127.0.0.1:5670',
      GITHUB_CLIENT_ID: process.env.GITHUB_CLIENT_ID,
      GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
      GET_USER_URL: process.env.GET_USER_URL,
      LOGIN_URL: process.env.LOGIN_URL,
      LOGOUT_URL: process.env.LOGOUT_URL,
    },
    trailingSlash: true,
    images: { unoptimized: true },
    skipTrailingSlashRedirect: true,
    transpilePackages: [
      '@berryv/g2-react',
      '@antv/g2',
      'react-syntax-highlighter',
      '@antv/g6',
      '@antv/graphin',
      '@antv/gpt-vis',
    ],
    webpack: (config, { isServer, dev, webpack }) => {
      // Large editor/chart modules otherwise accumulate across page compilations.
      // Keep production caching; development can recompile evicted pages on demand.
      if (dev) config.cache = false;
      // Replace only OB's formatting adapter. SQL completion/tokenization and
      // its prebuilt workers remain unchanged; generated parsers stay out of pages.
      config.plugins.push(
        new webpack.NormalModuleReplacementPlugin(/^\.\.\/format$/, resource => {
          if (
            /[/\\]@oceanbase-odc[/\\]monaco-plugin-ob[/\\]dist[/\\](mysql|obmysql|oboracle)$/.test(resource.context)
          ) {
            resource.request = path.join(__dirname, 'components/chat/ob-editor/format.ts');
          }
        }),
      );
      // Use the packages' ESM entry points with Next's native transpilation.
      config.resolve.alias = {
        ...config.resolve.alias,
        '@berryv/g2-react$': path.join(__dirname, 'node_modules/@berryv/g2-react/es/index.js'),
        '@antv/gpt-vis$': path.join(__dirname, 'node_modules/@antv/gpt-vis/dist/esm/index.js'),
        '@antv/g6$': path.join(__dirname, 'node_modules/@antv/g6/esm/index.js'),
      };
      if (process.platform === 'win32' && !dev) config.parallelism = 2;
      config.resolve.fallback = { fs: false };
      if (!isServer) {
        config.plugins.push(
          new CopyPlugin({
            patterns: [
              {
                from: path.join(__dirname, 'node_modules/@oceanbase-odc/monaco-plugin-ob/worker-dist/'),
                to: 'static/ob-workers',
              },
            ],
          }),
        );
        config.plugins.push(new MonacoWebpackPlugin({ languages: ['sql'], filename: 'static/[name].worker.js' }));
      }
      return config;
    },
  };
};
