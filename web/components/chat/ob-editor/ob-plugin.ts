import type Plugin from '@oceanbase-odc/monaco-plugin-ob';

let plugin: Plugin;

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
  const module = await import('@oceanbase-odc/monaco-plugin-ob');
  const Plugin = module.default;
  if (plugin) {
    return plugin;
  }
  plugin = new Plugin();
  plugin.setup(['mysql']);
  return plugin;
}
