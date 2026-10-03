import type { IAgentPlugin, IMyPlugin } from '@/types/agent';

/** Adapt the installed-plugin API record to the shared marketplace card. */
export function installedPluginCard(plugin: IMyPlugin): IAgentPlugin {
  return {
    id: plugin.id,
    name: plugin.name,
    description: plugin.description,
    version: plugin.version,
    type: plugin.type,
    installed: 1,
    gmt_created: plugin.created_at,
    email: 'email' in plugin && typeof plugin.email === 'string' ? plugin.email : '',
    author: 'author' in plugin && typeof plugin.author === 'string' ? plugin.author : '',
    storage_channel:
      'storage_channel' in plugin && typeof plugin.storage_channel === 'string' ? plugin.storage_channel : '',
    storage_url: 'storage_url' in plugin && typeof plugin.storage_url === 'string' ? plugin.storage_url : '',
    download_param: '',
  };
}
