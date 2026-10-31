import webpackBundle from 'next/dist/compiled/webpack/webpack.js';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import nextConfig from '../next.config.js';

const { webpack } = webpackBundle;

for (const [dependency, entryPoint] of [
  ['@mui/icons-material', 'helpers/interopRequireDefault'],
  ['react-syntax-highlighter', 'regenerator/index'],
]) {
  test(`development refresh can compile ${dependency}'s nested Babel ${entryPoint}`, async t => {
    const temporaryRoot = fs.realpathSync(os.tmpdir());
    const directory = fs.mkdtempSync(path.join(temporaryRoot, 'dbgpt-refresh-'));
    t.after(() => {
      assert.equal(path.dirname(fs.realpathSync(directory)), temporaryRoot);
      fs.rmSync(directory, { recursive: true, force: true });
    });
    const runtime = path.join(directory, 'node_modules', dependency, 'node_modules/@babel/runtime');
    const helper = path.join(runtime, `${entryPoint}.js`);
    fs.cpSync(path.dirname(fileURLToPath(import.meta.resolve('@babel/runtime/package.json'))), runtime, {
      recursive: true,
    });
    const entry = path.join(directory, 'entry.cjs');
    fs.writeFileSync(entry, `module.exports = require(${JSON.stringify(helper)});`);

    const configured = nextConfig.webpack(
      {
        module: {
          rules: [
            {
              include: runtime,
              use: fileURLToPath(import.meta.resolve('next/dist/compiled/@next/react-refresh-utils/dist/loader.js')),
            },
          ],
        },
        resolve: {},
        plugins: [],
      },
      { dev: true, isServer: false },
    );
    const compiler = webpack({
      mode: 'development',
      target: 'node',
      entry,
      devtool: false,
      module: configured.module,
      plugins: [new webpack.HotModuleReplacementPlugin()],
      output: { path: path.join(directory, 'dist'), filename: 'bundle.cjs', library: { type: 'commonjs2' } },
    });
    const stats = await new Promise((resolve, reject) => {
      compiler.run((error, result) => {
        compiler.close(closeError => (error || closeError ? reject(error || closeError) : resolve(result)));
      });
    });
    assert.equal(stats.hasErrors(), false, stats.toString({ all: false, errors: true }));
    const { default: exported } = await import(pathToFileURL(path.join(directory, 'dist/bundle.cjs')).href);
    if (entryPoint.startsWith('helpers/')) assert.deepEqual(exported('value'), { default: 'value' });
    else {
      const generated = exported.wrap(context => {
        switch (context.next) {
          case 0:
            context.next = 2;
            return 'value';
          default:
            return context.stop();
        }
      });
      assert.deepEqual(generated.next(), { value: 'value', done: false });
      assert.deepEqual(generated.next(), { value: undefined, done: true });
    }
  });
}
