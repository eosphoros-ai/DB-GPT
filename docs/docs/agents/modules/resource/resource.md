# Resource Introduction

Resources are a bridge for DB-GPT agents to interact with the outside world. They include
tools, databases, knowledge bases, etc.

## What Includes In Resources?

- **Tools**: The tools for this are similar to those used in some function calls.
- **Databases**: You can query and analyze data from databases.
- **Knowledge Bases**: External knowledge bases can be used to enrich the knowledge of the agent.
- **APIs**: You can call third-party APIs to get data or perform operations.
- **Files**: You can read and write some files.
- **Third-party Plugins**: You can use third-party plugins to enrich the functionality of the agent.
- ...

## Resource Pack

The resource pack is a collection of resources that can be used by agents. It usually contains some
tools, databases, knowledge bases, etc. 

You can wrap optional tools into `ToolPack`, or wrap all resources into `ResourcePack`.

## What's Next?

In following sections, we will introduce most of the resources that can be used in DB-GPT.