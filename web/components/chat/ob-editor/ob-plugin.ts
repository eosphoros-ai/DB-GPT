import type Plugin from '@oceanbase-odc/monaco-plugin-ob';

declare global {
  interface Window {
    obMonaco?: { getWorkerUrl: (type: string) => string };
  }
}

let plugin: Plugin;

/** Initialize the cached MySQL Monaco plugin and point its prebuilt SQL workers at same-origin assets. */
export async function register(): Promise<Plugin> {
  window.obMonaco = {
    getWorkerUrl: (type: string) => {
      switch (type) {
        case 'mysql': {
          return location.origin + '/_next/static/ob-workers/mysql.js';
        }
        case 'obmysql': {
          return location.origin + '/_next/static/ob-workers/obmysql.js';
        }
        case 'oboracle': {
          return location.origin + '/_next/static/ob-workers/oracle.js';
        }
      }
      return '';
    },
  };
  const pluginModule = await import('@oceanbase-odc/monaco-plugin-ob');
  const Plugin = pluginModule.default;
  if (plugin) {
    return plugin;
  }
  plugin = new Plugin();
  plugin.setup(['mysql']);
  return plugin;
}
