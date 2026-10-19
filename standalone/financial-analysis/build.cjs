const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const dir = __dirname;
const repo = path.resolve(dir, '../..');
const web = path.join(repo, 'web');
const requireWeb = createRequire(path.join(web, 'package.json'));
const webpack = requireWeb('webpack');
const postcss = requireWeb('postcss');
const tailwind = requireWeb('tailwindcss');
const TerserPlugin = requireWeb('terser-webpack-plugin');
const out = path.join(dir, '.work');
const financial = path.join(web, 'new-components/financial-analysis');
const hashes = () => Object.fromEntries(fs.readdirSync(financial).map(name => [name, crypto.createHash('sha256').update(fs.readFileSync(path.join(financial, name))).digest('hex')]));
const original = hashes();
const exportRuntime = process.argv.includes('--export-runtime');
const progressPreview = process.argv.includes('--progress-preview');

async function build() {
  fs.mkdirSync(out, { recursive: true });
  const config = {
    mode: 'production', target: ['web', 'es2020'], context: dir,
    entry: path.join(dir, progressPreview ? 'progress-preview.tsx' : process.argv.includes('--workflow-preview') ? 'workflow-preview.tsx' : exportRuntime ? 'export-entry.tsx' : 'entry.tsx'), devtool: false,
    output: { path: out, filename: 'demo.js', iife: true, publicPath: '', chunkLoading: false },
    resolve: {
      extensions: ['.tsx', '.ts', '.js', '.mjs', '.json'],
      modules: ['node_modules', path.join(web, 'node_modules')],
      alias: {
        ...(progressPreview ? Object.fromEntries([
          '@/components/chat/chat-content/code-preview$', '@/components/chat/chat-content/config$',
          '@/new-components/charts$', '@antv/gpt-vis$', './ConversationTracePanel$',
          './ParallelTasksPanel$', '@/new-components/financial-analysis/FinancialReportArtifact$',
        ].map(name => [name, path.join(dir, 'adapters/progress-unused.tsx')])) : {}),
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
    optimization: { splitChunks: false, runtimeChunk: false, minimizer: [new TerserPlugin({ parallel: false, extractComments: false, terserOptions: { format: { comments: false } } })] },
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
  if (assets.some(name => name !== 'demo.js' && !name.endsWith('.css'))) throw new Error(`Unexpected external assets: ${assets}`);
  const sources = stats.compilation.modules;
  const forbidden = [...sources].map(module => module.resource || '').filter(name => /[\\/]web[\\/](client|app)[\\/]|[\\/]node_modules[\\/]next[\\/]/.test(name));
  if (forbidden.length) throw new Error(`Server/app runtime leaked into standalone: ${forbidden.join(', ')}`);
  const content = [
    path.join(financial, '**/*.tsx'), path.join(dir, '**/*.tsx'),
    path.join(web, 'new-components/chat/content/ManusLeftPanel.tsx'),
    path.join(web, 'new-components/chat/content/TaskPlanCard.tsx'),
    ...(progressPreview ? [path.join(web, 'new-components/chat/content/ManusRightPanel.tsx'),
      path.join(web, 'new-components/chat/content/FinancialProgressPanel.tsx')] : []),
    path.join(web, 'new-components/chat/content/ObservationFormatter.tsx'),
  ].map(name => name.replace(/\\/g, '/'));
  const nativeTailwind = require(path.join(web, 'tailwind.config.js'));
  const utilities = await postcss([tailwind({ ...nativeTailwind, content, theme: { ...nativeTailwind.theme, fontFamily: { sans: ['Segoe UI', 'Microsoft YaHei', 'system-ui', 'sans-serif'] } } })]).process('@tailwind base;\n@tailwind components;\n@tailwind utilities;', { from: undefined });
  const css = utilities.css + '\n' + fs.readFileSync(path.join(dir, 'shell.css'), 'utf8') + '\n' + assets.filter(name => name.endsWith('.css')).map(name => fs.readFileSync(path.join(out, name), 'utf8')).join('\n');
  if (/@import\b|url\(\s*['"]?(?!data:)[^)'"\s]/i.test(css)) throw new Error('External CSS dependency detected');
  const js = fs.readFileSync(path.join(out, 'demo.js'), 'utf8');
  const diagnostics = `window.__DEMO_DIAGNOSTICS__={errors:[],violations:[],resources:[]};addEventListener('error',e=>window.__DEMO_DIAGNOSTICS__.errors.push(e.message||'Asset error'));addEventListener('unhandledrejection',e=>window.__DEMO_DIAGNOSTICS__.errors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>window.__DEMO_DIAGNOSTICS__.violations.push(e.violatedDirective+': '+e.blockedURI));new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.name.startsWith('data:'))window.__DEMO_DIAGNOSTICS__.resources.push(e.name)}).observe({type:'resource',buffered:true});{const original=console.error;console.error=function(...args){window.__DEMO_DIAGNOSTICS__.errors.push(args.map(String).join(' '));original.apply(console,args)}};`;
  const reportDataNode = exportRuntime ? '<script type="application/json" id="financial-report-data"><!--FINANCIAL_REPORT_JSON--></script>' : '';
  const html = `<!doctype html>\n<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><link rel="icon" href="data:,"><title>DB-GPT Financial Analysis ${exportRuntime ? 'Report' : 'Demo'}</title><style>${css.replace(/<\/style/gi, '<\\/style')}</style></head><body><div id="root"></div>${reportDataNode}<noscript>请启用 JavaScript 以使用交互式财务分析报告。</noscript><script>${diagnostics}${js.replace(/<\/script/gi, '<\\/script')}</script></body></html>`;
  // Optional output path lets regression builds preserve the delivered demo.
  const output = process.argv[2] ? path.resolve(process.argv[2]) : path.join(repo, 'DB-GPT-Financial-Analysis-Demo.html');
  fs.writeFileSync(output, html, 'utf8');
  if (JSON.stringify(original) !== JSON.stringify(hashes())) throw new Error('Development source changed during build');
  fs.writeFileSync(path.join(out, 'build-report.json'), JSON.stringify({ output, bytes: Buffer.byteLength(html), assets, originalSourceHashes: original, modules: [...sources].map(module => module.resource).filter(Boolean) }, null, 2));
  console.log(`Built ${output}\n${Buffer.byteLength(html).toLocaleString()} bytes; one inline script, all CSS/assets inline; development sources unchanged.`);
}
build().catch(error => { console.error(error); process.exitCode = 1; });
