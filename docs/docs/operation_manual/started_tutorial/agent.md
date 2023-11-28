# Data Agent

Regarding the use of plugin(data agent), the current project supports basic plugin warehouses and plugin expansion capabilities. The project currently has a built-in search plugin. Let's experience the basic usage of the plugin.

## Steps
The use of the default plugin mainly includes the following steps. For more advanced features, you can follow the subsequent advanced tutorials.
- 1.Enter the plugin market
- 2.View the list of plugins in the GitHub repository
- 3.Download the plugin
- 4.Select Data Agent 
- 5.Start chat

### View plugin list
First, you can click the `Update GitHub plugin` button, and the plugin list in the [GitHub plugin repository](https://github.com/eosphoros-ai/DB-GPT-Plugins) will automatically be displayed here.


<p align="left">
  <img src={'/img/plugin/show_plugin.png'} width="720px" />
</p>

### Download plugin

Click the `download` button to download the plugin locally

<p align="left">
  <img src={'/img/plugin/download.png'} width="720px" />
</p>

After the download is successful, you can see the plugin list in the my plugin interface. Of course, it also supports uploading models through local upload.

<p align="left">
  <img src={'/img/plugin/show_plugin_more.png'} width="720px" />
</p>


### Select `Data Agent`
Select the plugin dialog to enable plugin use.

<p align="left">
  <img src={'/img/plugin/choose_plugin.png'} width="720px" />
</p>


### Configure cookies

Before starting to use the default search plugin, you need to configure cookies. For detailed configuration tutorials, see the [plugin description](https://github.com/eosphoros-ai/DB-GPT-Plugins/tree/main/src/dbgpt_plugins/search_engine).

Specify the corresponding cookie configuration items in the `.env` file to complete the configuration.


### Start chat
After configuring cookies, we can start using the plugin.

<p align="left">
  <img src={'/img/plugin/chat.gif'} width="720px" />
</p>


:::info note

For more plugin expansion and advanced gameplay, welcome to [communicate](https://github.com/eosphoros-ai/DB-GPT/issues) with us.
:::
