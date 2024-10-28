# Prompts

In the actual application development process, Prompt needs to be customized in different scenarios, Agent, RAG and other modules. In order to make the editing and adjustment of Prompt more flexible, an independent Prompt module is created.

## Browse

As shown in the figure below, click **Application Management** ->**Prompt** You can enter the corresponding management interface. The interface displays a custom prompt list by default, and you can manage all prompts.

<p align="center">
  <img src={'/img/app/prompt_v0.6.jpg'} width="800px" />
</p>

## Added
Next, let's see how to create a new prompt. Click the **Add Prompt**  button and the prompt edit box will pop up.

<p align="center">
  <img src={'/img/app/prompt_add_v0.6.jpg'} width="800px" />
</p>

We define four types of prompts: 
- AGENT: Agent Prompt 
- SCENE: Scene Prompt 
- NORMAL: Normal prompt word 
- EVALUATE: Evaluation Mode Prompt

When the AGENT type is selected, all registered agents can be seen in the drop-down list menu, and you can select an agent to set the prompt.

<p align="center">
  <img src={'/img/app/agent_prompt_v0.6.jpg'} width="400px" />
</p>

After setting the prompt, a unique UID will be generated. You can bind the corresponding prompt according to the ID when using it.

<p align="center">
  <img src={'/img/app/agent_prompt_code_v0.6.jpg'} width="800px" />
</p>


## Usage

Enter the AWEL editing interface, as shown below, click **Application Management** -> **Create Workflow**


<p align="center">
  <img src={'/img/app/awel_create.6.jpg'} width="800px" />
</p>

Find the Agent resource and select the AWEL Layout Agent operator. We can see that each Agent contains the following information: 

- Profile
- Role
- Goal
- Resource (AWELResource): The resource that Agent depends on 
- AgentConfig(AWELAgentConfig) Agent Config
- AgentPrompt: Prompt

<p align="center">
  <img src={'/img/app/agent_prompt_awel_v0.6.jpg'} width="800px" />
</p>

Click the [+] next to **AgentPrompt**, select the Prompt operator that pops up, and select the corresponding Prompt name or UID in the parameter panel to bind our newly created Prompt to the Agent, and debug the Agent's behavior in turn.
