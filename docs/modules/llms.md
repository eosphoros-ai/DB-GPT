# LLMs

In the underlying large model integration, we have designed an open interface that supports integration with various large models. At the same time, we have a very strict control and evaluation mechanism for the effectiveness of the integrated models. In terms of accuracy, the integrated models need to align with the capability of ChatGPT at a level of 85% or higher. We use higher standards to select models, hoping to save users the cumbersome testing and evaluation process in the process of use.

##  Multi LLMs Usage
To use multiple models, modify the LLM_MODEL parameter in the .env configuration file to switch between the models.

Notice: you can create .env file from .env.template, just use command like this:
```
cp .env.template .env
```