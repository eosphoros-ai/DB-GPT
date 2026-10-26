const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const dir = __dirname;
const repo = path.resolve(dir, '../..');
const web = path.join(repo, 'web');
const requireWeb = createRequire(path.join(web, 'package.json'));
const webpack = requireWeb('webpack');
const postcss = requireWeb('postcss');
const tailwind = requireWeb('tailwindcss');
const terser = requireWeb('terser');
const financial = path.join(web, 'new-components/financial-analysis');
const args = process.argv.slice(2).filter(argument => argument !== '--export-runtime');
if (args.length > 1 || args.some(argument => argument.startsWith('--'))) {
  throw new Error('Usage: node build.cjs [output.html]');
}
const output = args.length ? path.resolve(args[0]) : path.join(dir, '.work', 'export-runtime.html');
const out = path.dirname(output);

async function build() {
  fs.mkdirSync(out, { recursive: true });
  const config = {
    mode: 'production', target: ['web', 'es2020'], context: dir,
    entry: path.join(dir, 'export-entry.tsx'), devtool: false,
    output: { path: out, filename: 'report.js', iife: true, publicPath: '', chunkLoading: false },
    resolve: {
      extensions: ['.tsx', '.ts', '.js', '.mjs', '.json'],
      modules: ['node_modules', path.join(web, 'node_modules')],
      alias: {
        'next/dynamic$': path.join(dir, 'adapters/dynamic.tsx'),
        'next/router$': path.join(dir, 'adapters/router.ts'),
        '@/app/chat-context$': path.join(dir, 'adapters/chat-context.tsx'),
        '@/modules/session-files$': path.join(dir, 'adapters/attachments.tsx'),
        '@/new-components/common/MarkdownContext$': path.join(dir, 'adapters/markdown.tsx'),
        '@': web,
      },
    },
    module: {
      parser: { javascript: { dynamicImportMode: 'eager' } },
      rules: [
        { test: /\.tsx?$/, exclude: /node_modules/, use: path.join(dir, 'ts-loader.cjs') },
        { test: /\.module\.css$/, use: path.join(dir, 'css-loader.cjs') },
        { test: /\.(png|jpe?g|svg|gif|webp|woff2?)$/, type: 'asset/inline' },
      ],
    },
    optimization: { splitChunks: false, runtimeChunk: false, minimize: false },
    plugins: [new webpack.optimize.LimitChunkCountPlugin({ maxChunks: 1 })],
    performance: false,
  };
  const stats = await new Promise((resolve, reject) => {
    const compiler = webpack(config);
    compiler.run((error, stats) => compiler.close(closeError => error || closeError ? reject(error || closeError) : resolve(stats)));
  });
  if (stats.hasErrors()) throw new Error(stats.toString({ all: false, errors: true }));
  if (stats.hasWarnings()) console.warn(stats.toString({ all: false, warnings: true }));
  const assets = stats.toJson({ all: false, assets: true }).assets.map(asset => asset.name);
  if (assets.some(name => name !== 'report.js' && !name.endsWith('.css'))) throw new Error(`Unexpected external assets: ${assets}`);
  const sources = stats.compilation.modules;
  const forbidden = [...sources].map(module => module.resource || '').filter(name => /[\\/]web[\\/](client|app)[\\/]|[\\/]node_modules[\\/]next[\\/]/.test(name));
  if (forbidden.length) throw new Error(`Server/app runtime leaked into offline report: ${forbidden.join(', ')}`);
  const content = [
    path.join(financial, '**/*.tsx'), path.join(dir, '**/*.tsx'),
    ...['ManusLeftPanel', 'TaskPlanCard', 'FinancialProgressPanel', 'ObservationFormatter']
      .map(name => path.join(web, `new-components/chat/content/${name}.tsx`)),
  ].map(name => name.replace(/\\/g, '/'));
  const nativeTailwind = require(path.join(web, 'tailwind.config.js'));
  const utilities = await postcss([tailwind({ ...nativeTailwind, content, theme: { ...nativeTailwind.theme, fontFamily: { sans: ['Segoe UI', 'Microsoft YaHei', 'system-ui', 'sans-serif'] } } })]).process('@tailwind base;\n@tailwind components;\n@tailwind utilities;', { from: undefined });
  const shell = "html,body,#root{margin:0;width:100%;height:100%;font-family:'Segoe UI','Microsoft YaHei',system-ui,sans-serif}body{overflow:hidden}";
  const css = utilities.css + '\n' + shell + '\n' + assets.filter(name => name.endsWith('.css')).map(name => fs.readFileSync(path.join(out, name), 'utf8')).join('\n');
  if (/@import\b|url\(\s*['"]?(?!data:)[^)'"\s]/i.test(css)) throw new Error('External CSS dependency detected');
  const minified = await terser.minify(fs.readFileSync(path.join(out, 'report.js'), 'utf8'), {
    format: { comments: false },
  });
  if (!minified.code) throw new Error('Offline runtime minification produced no code');
  const js = minified.code;
  const reportDataNode = '<script type="application/json" id="financial-report-data"><!--FINANCIAL_REPORT_JSON--></script>';
  const html = `<!doctype html>\n<html lang="<!--FINANCIAL_REPORT_LANGUAGE-->"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><link rel="icon" href="data:,"><title>DB-GPT Financial Analysis Report</title><style>${css.replace(/<\/style/gi, '<\\/style')}</style></head><body><div id="root"></div>${reportDataNode}<noscript><p lang="en">Enable JavaScript to use this interactive financial report.</p><p lang="zh-CN">请启用 JavaScript 以使用交互式财务分析报告。</p></noscript><script>${js.replace(/<\/script/gi, '<\\/script')}</script></body></html>`;
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, html, 'utf8');
  console.log(`Built ${output}\n${Buffer.byteLength(html).toLocaleString()} bytes; all scripts, styles and assets inline.`);
}
build().catch(error => { console.error(error); process.exitCode = 1; });
