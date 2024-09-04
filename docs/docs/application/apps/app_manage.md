# App Manage

The application management panel provides many capabilities. Here we mainly introduce the management of the data intelligence application life cycle, including application creation, editing, deletion, and use.

<p align="center">
  <img src={'/img/app/app_manage_v0.6.jpg'} width="800px" />
</p>

As shown in the figure, the application management interface. First, let's take a look at the creation of an application. In DB-GPT, four application creation modes are provided. 

- Multi-agent automatic planning mode
- Task flow orchestration mode 
- Single Agent Mode 
- Native application mode

<p align="center">
  <img src={'/img/app/app_manage_mode_v0.6.jpg'} width="800px" />
</p>

Next, we will explain the creation of applications in each mode respectively. Native application mode In the early versions of DB-GPT, six types of native application scenarios were provided, such as `Chat DB`, `Chat Data`, `Chat Dashboard`, `Chat Knowledge Base`, `Chat Normal`, `Chat Excel`, etc. 

By creating a data intelligence application in the native application mode, you can quickly build a similar application based on your own database, knowledge base and other parameters. Click the upper right cornerCreate an applicationbutton, select **Native application mode**, enter the application name and description, click **Sure**

<p align="center">
  <img src={'/img/app/app_manage_chat_data_v0.6.jpg'} width="800px" />
</p>

After confirmation, enter the parameter selection panel. As shown in the figure below, we can see selection boxes such as application type, model, temperature, and recommended questions.

<p align="center">
  <img src={'/img/app/app_manage_chat_data_editor_v0.6.jpg'} width="800px" />
</p>

Here, we select **Chat Data**  Application, fill in the parameters in order according to the requirements. Note that in the data dialogue application, the parameter column needs to fill in the data source. If you do not have a data source, you need to follow [Data Source Tutorial](../datasources.md) to add it.


After completing the parameters, click **Save** to view related applications in the application panel.

<p align="center">
  <img src={'/img/app/app_manage_app_v0.6.jpg'} width="800px" />
</p>

Please note that after creating an application, there is a **Publish Application** button. Only after the application is published can it be discovered and used by other users.

<p align="center">
  <img src={'/img/app/app_manage_app_publish_v0.6.jpg'} width="800px" />
</p>

Finally, click the **Start a conversation** button to start a conversation with the application you just created.

<p align="center">
  <img src={'/img/app/app_manage_chat_v0.6.jpg'} width="800px" />
</p>

In addition, you can also edit and delete applications. Just operate on the corresponding interface.
