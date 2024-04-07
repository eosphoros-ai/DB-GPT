
import Plugin from '@oceanbase-odc/monaco-plugin-ob';

let plugin: Plugin;

export function register(): Plugin {
  if (plugin) {
    return plugin;
  }
  plugin = new Plugin();
  plugin.setup();
  return plugin;
}
