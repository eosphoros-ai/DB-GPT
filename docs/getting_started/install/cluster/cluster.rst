LLM Deployment
==================================
In the exploration and implementation of AI model applications, it can be challenging to directly integrate with model services. Currently, there is no established standard for deploying large models, and new models and inference methods are constantly being released. As a result, a significant amount of time is spent adapting to the ever-changing underlying model environment. This, to some extent, hinders the exploration and implementation of AI model applications.

We divide the deployment of large models into two layers: the model inference layer and the model deployment layer. The model inference layer corresponds to model inference frameworks such as vLLM, TGI, and TensorRT. The model deployment layer interfaces with the inference layer below and provides model serving capabilities above. We refer to this layer's framework as the model deployment framework. Positioned above the inference frameworks, the model deployment framework offers capabilities such as multiple model instances, multiple inference frameworks, multiple service protocols, multi-cloud support, automatic scaling, and observability.

In order to deploy DB-GPT to multiple nodes, you can deploy a cluster. The cluster architecture diagram is as follows:

.. raw:: html

    <img src="../../../_static/img/muti-model-cluster-overview.png" />

Design of DB-GPT:
-----------------

DB-GPT is designed as a llm deployment framework, taking into account the above design objectives.

- Support for llm and inference frameworks: DB-GPT supports the simultaneous deployment of llm and is compatible with multiple inference frameworks such as vLLM, TGI, and TensorRT.

- Scalability and stability: DB-GPT has good scalability, allowing easy addition of new models and inference frameworks. It utilizes a distributed architecture and automatic scaling capabilities to handle high concurrency and large-scale requests, ensuring system stability.

- Performance optimization: DB-GPT undergoes performance optimization to provide fast and efficient model inference capabilities, preventing it from becoming a performance bottleneck during inference.

- Management and observability capabilities: DB-GPT offers management and monitoring functionalities, including model deployment and configuration management, performance monitoring, and logging. It can generate reports on model performance and service status to promptly identify and resolve issues.

- Lightweight: DB-GPT is designed as a lightweight framework to improve deployment efficiency and save resources. It employs efficient algorithms and optimization strategies to minimize resource consumption while maintaining sufficient functionality and performance.

1.Support for multiple models and inference frameworks
-----------------
The field of large models is evolving rapidly, with new models being released and new methods being proposed for model training and inference. We believe that this situation will continue for some time.

For most users exploring and implementing AI applications, this situation has its pros and cons. The benefits are apparent, as it brings new opportunities and advancements. However, one drawback is that users may feel compelled to constantly try and explore new models and inference frameworks.

In DB-GPT, seamless support is provided for FastChat, vLLM, and llama.cpp. In theory, any model supported by these frameworks is also supported by DB-GPT. If you have requirements for faster inference speed and concurrency, you can directly use vLLM. If you want good inference performance on CPU or Apple's M1/M2 chips, you can use llama.cpp. Additionally, DB-GPT also supports various proxy models from OpenAI, Azure OpenAI, Google BARD, Wenxin Yiyan, Tongyi Qianwen, and Zhipu AI, among others.

2.Have good scalability and stability
-----------------
A comprehensive model deployment framework consists of several components: the Model Worker, which directly interfaces with the underlying inference frameworks; the Model Controller, which manages and maintains multiple model components; and the Model API, which provides external model serving capabilities.

The Model Worker plays a crucial role and needs to be highly extensible. It can be specialized for deploying large language models, embedding models, or other types of models. The choice of Model Worker depends on the deployment environment, such as a regular physical server environment, a Kubernetes environment, or specific cloud environments provided by various cloud service providers.

Having different Model Worker options allows users to select the most suitable one based on their specific requirements and infrastructure. This flexibility enables efficient deployment and utilization of models across different environments.

The Model Controller, responsible for managing model metadata, also needs to be scalable. Different deployment environments and model management requirements may call for different choices of Model Controllers.

Furthermore, I believe that model serving shares many similarities with traditional microservices. In microservices, a service can have multiple instances, and all instances are registered in a central registry. Service consumers retrieve the list of instances based on the service name from the registry and select a specific instance for invocation using a load balancing strategy.

Similarly, in model deployment, a model can have multiple instances, and all instances can be registered in a model registry. Model service consumers retrieve the list of instances based on the model name from the registry and select a specific instance for invocation using a model-specific load balancing strategy.

Introducing a model registry, responsible for storing model instance metadata, enables such an architecture. The model registry can leverage existing service registries used in microservices (such as Nacos, Eureka, etcd, Consul, etc.) as implementations. This ensures high availability of the entire deployment system.

3.High performance for framework.
------------------
and optimization are complex tasks, and inappropriate framework designs can increase this complexity. In our view, to ensure that the deployment framework does not lag behind in terms of performance, there are two main areas of focus:

Avoid excessive encapsulation: The more encapsulation and longer the chain, the more challenging it becomes to identify performance issues.

High-performance communication design: High-performance communication involves various aspects that cannot be elaborated in detail here. However, considering that Python occupies a prominent position in current AIGC applications, asynchronous interfaces are crucial for service performance in Python. Therefore, the model serving layer should only provide asynchronous interfaces and be compatible with the layers that interface with the model inference framework. If the model inference framework offers asynchronous interfaces, direct integration should be implemented. Otherwise, synchronous-to-asynchronous task conversion should be used to provide support.

4.Management and monitoring capabilities.
------------------
In the exploration or production implementation of AIGC (Artificial Intelligence and General Computing) applications, it is important for the model deployment system to have certain management capabilities. This involves controlling the deployed model instances through APIs or command-line interfaces, such as for online/offline management, restarting, and debugging.

Observability is a crucial capability in production systems, and I believe it is equally, if not more, important in AIGC applications. This is because user experiences and interactions with the system are more complex. In addition to traditional observability metrics, we are also interested in user input information and corresponding contextual information, which specific model instance and parameters were invoked, the content and response time of model outputs, user feedback, and more.

By analyzing this information, we can identify performance bottlenecks in model services and gather user experience data (e.g., response latency, problem resolution, and user satisfaction extracted from user content). These insights serve as important foundations for further optimizing the entire application.

* On :ref:`Deploying on standalone mode <standalone-index>`. Standalone Deployment.
* On :ref:`Deploying on cluster mode <local-cluster-index>`. Cluster Deployment.


.. toctree::
   :maxdepth: 2
   :caption: Cluster deployment
   :name: cluster_deploy
   :hidden:

   ./vms/standalone.md
   ./vms/index.md
