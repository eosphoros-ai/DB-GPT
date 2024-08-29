# TuGraph
TuGraph图数据库由蚂蚁集团与清华大学联合研发，构建了一套包含图存储、图计算、图学习、图研发平台的完善的图技术体系，支持海量多源的关联数据的实时处理，显著提升数据分析效率，支撑了蚂蚁支付、安全、社交、公益、数据治理等300多个场景应用。拥有业界领先规模的图集群，解决了图数据分析面临的大数据量、高吞吐率和低延迟等重大挑战，是蚂蚁集团金融风控能力的重要基础设施，显著提升了欺诈洗钱等金融风险的实时识别能力和审理分析效率，并面向金融、工业、政务服务等行业客户。TuGraph产品家族中，开源产品包括：TuGraph DB、TuGraph Analytics、OSGraph、ChatTuGraph等。内源产品包括：GeaBase、GeaFlow、GeaLearn、GeaMaker等。

TuGraph企业级图数据管理平台提供对关联数据的复杂、深度分析功能。TuGraph以分布式集群架构，支持海量数据的高吞吐、高可用性、高并发读写和ACID事务操作。通过对数据的分片、分区，支持水平扩展，提供对点、边、属性、拓扑等结构的查询、过滤、索引等功能。TuGraph提供离线、近线、在线的图算法和图学习能力，内置数十种算法，能够对全图、子图、动态图的模式和特征进行处理，通过可视化或数据服务形式与外部数据源交互。此外，TuGraph提供可视化的展示和操作界面，覆盖图研发和服务的全生命周期，支持主流的图查询语言，提供便捷的访问和开发接口，能够与外部多模数据源进行导入导出、存量/增量/批量更新和备份。TuGraph还提供精美和实用的图生产环境管理监控，满足企业用户的技术和业务应用需要。

TuGraph在金融风控方面的应用实践主要包括个人信贷业务、反欺诈、洗钱路径追踪等问题。利用多维交叉关联信息深度刻画申请和交易行为，识别多种复杂、规模化、隐蔽性的欺诈网络和洗钱网络；结合聚类分析、风险传播等算法，实时计算用户的风险评分，在风险行为发生前预先识别，帮助金融机构提升效率、降低风险。基于TuGraph企业级图数据管理平台，蚂蚁集团增加反欺诈稽核金额6%，反洗钱风险审理分析效率提升90%。每天计算近10亿用户大约200亿左右边关系，对疑似团伙类犯罪风险识别能力提高近10倍。此外，为某银行提供的信贷图平台提升了13%的风控模型区分度；为某银行完成的信用卡申请团伙欺诈分析方案，运算时间缩短至原有的1/60；为某银行搭建的企业风险图平台，在对小微企业评级放贷问题中，担保圈识别准确率达到90%以上。


## 1. TuGraph DB

### 1.1 简介
TuGraph DB 是支持大数据容量、低延迟查找和快速图分析功能的高效图数据库。TuGraph社区版于2022年9月开源，提供了完整的图数据库基础功能和成熟的产品设计（如ACID兼容的事务、编程API和配套工具等），适用于单实例部署。社区版支持TB级别的数据规模，为用户管理和分析复杂关联数据提供了高效、易用、可靠的平台，是学习TuGraph和实现小型项目的理想选择。

### 1.2 TuGraph特性
TuGraph是支持大数据量、低延迟查找和快速图分析功能的高效图数据库。TuGraph也是基于磁盘的数据库，支持存储多达数十TB的数据。TuGraph提供多种API，使用户能够轻松构建应用程序，并使其易于扩展和优化。

它具有如下功能特征：

* 属性图模型
* 实时增删查改
* 多重图（点间允许多重边）
* 多图（大图与多个子图）
* 完善的ACID事务处理，隔离级别为可串行化（serializable）
* 点边索引
* 混合事务和分析处理（HTAP），支持图查询、图分析、图学习
* 主流图查询语言（OpenCypher、ISO GQL等）
* 支持OLAP API，内置30多种图分析算法
* 基于C++/Python的存储过程，含事务内并行Traversal API
* 提供图可视化工具
* 在性能和可扩展性方面的支持：
* 千万点/秒的高吞吐率
* TB级大容量
* 高可用性支持
* 高性能批量导入
* 在线/离线的备份恢复


主要功能：

- 标签属性图模型
- 完善的 ACID 事务处理
- 内置 34 图分析算法
- 支持全文/主键/二级索引
- OpenCypher 图查询语言
- 基于 C++/Python 的存储过程

性能和可扩展性：

- LDBC SNB世界记录保持者 (2022/9/1 https://ldbcouncil.org/benchmarks/snb/)
- 支持存储多达数十TB的数据
- 每秒访问数百万个顶点
- 快速批量导入

TuGraph DB的文档在[链接](https://tugraph-db.readthedocs.io/zh_CN/latest)，欢迎访问我们的[官网](https://www.tugraph.org)。

### 1.3 快速上手

一个简单的方法是使用docker进行设置，可以在[DockerHub](https://hub.docker.com/u/tugraph)中找到, 名称为`tugraph/tugraph-runtime-[os]:[tugraph version]`,
例如， `tugraph/tugraph-runtime-centos7:3.3.0`。

更多详情请参考 [快速上手文档](./docs/zh-CN/source/3.quick-start/1.preparation.md) 和 [业务开发指南](./docs/zh-CN/source/development_guide.md).

### 1.4 从源代码编译

建议在Linux系统中构建TuGraph DB，Docker环境是个不错的选择。如果您想设置一个新的环境，请参考[Dockerfile](ci/images).

以下是编译TuGraph DB的步骤：

1. 如果需要web接口运行`deps/build_deps.sh`，不需要web接口则跳过此步骤
2. 根据容器系统信息执行`cmake .. -DOURSYSTEM=centos`或者`cmake .. -DOURSYSTEM=ubuntu`
3. `make`
4. `make package` 或者 `cpack --config CPackConfig.cmake`

示例：`tugraph/tugraph-compile-centos7`Docker环境

```bash
$ git clone --recursive https://github.com/TuGraph-family/tugraph-db.git
$ cd tugraph-db
$ deps/build_deps.sh
$ mkdir build && cd build
$ cmake .. -DOURSYSTEM=centos7
$ make
$ make package
```

### 1.5 开发

我们已为在DockerHub中编译准备了环境docker镜像，可以帮助开发人员轻松入门，名称为 `tugraph/tugraph-compile-[os]:[compile version]`, 例如， `tugraph/tugraph-compile-centos7:1.1.0`。

## 2. TuGraph Analytics

### 2.1 介绍
**TuGraph Analytics** (别名：GeaFlow) 是蚂蚁集团开源的[**性能世界一流**](https://ldbcouncil.org/benchmarks/snb-bi/)的OLAP图数据库，支持万亿级图存储、图表混合处理、实时图计算、交互式图分析等核心能力，目前广泛应用于数仓加速、金融风控、知识图谱以及社交网络等场景。

关于GeaFlow更多介绍请参考：[GeaFlow介绍文档](docs/docs-cn/introduction.md)

GeaFlow设计论文参考：[GeaFlow: A Graph Extended and Accelerated Dataflow System](https://dl.acm.org/doi/abs/10.1145/3589771)

### 2.2 起源

早期的大数据分析主要以离线处理为主，以Hadoop为代表的技术栈很好的解决了大规模数据的分析问题。然而数据处理的时效性不足，
很难满足高实时需求的场景。以Storm为代表的流式计算引擎的出现则很好的解决了数据实时处理的问题，提高了数据处理的时效性。
然而，Storm本身不提供状态管理的能力， 对于聚合等有状态的计算显得无能为力。Flink
的出现很好的弥补了这一短板，通过引入状态管理以及Checkpoint机制，实现了高效的有状态流计算能力。

随着数据实时处理场景的丰富，尤其是在实时数仓场景下，实时关系运算(即Stream Join)
越来越多的成为数据实时化的难点。Flink虽然具备优秀的状态管理能和出色的性能，然而在处理Join运算，尤其是3度以上Join时，
性能瓶颈越来越明显。由于需要在Join两端存放各个输入的数据状态，当Join变多时，状态的数据量急剧扩大，性能也变的难以接受。
产生这个问题的本质原因是Flink等流计算系统以表作为数据模型，而表模型本身是一个二维结构，不包含关系的定义和关系的存储，
在处理关系运算时只能通过Join运算方式实现，成本很高。

在蚂蚁的大数据应用场景中，尤其是金融风控、实时数仓等场景下，存在大量Join运算，如何提高Join
的时效性和性能成为我们面临的重要挑战，为此我们引入了图模型。图模型是一种以点边结构描述实体关系的数据模型，在图模型里面，点代表实体，
边代表关系，数据存储层面点边存放在一起。因此，图模型天然定义了数据的关系同时存储层面物化了点边关系。基于图模型，我们实现了新一代实时计算
引擎GeaFlow，很好的解决了复杂关系运算实时化的问题。目前GeaFlow已广泛应用于数仓加速、金融风控、知识图谱以及社交网络等场景。

### 2.3 特性

* 分布式实时图计算
* 图表混合处理（SQL+GQL语言）
* 统一流批图计算
* 万亿级图原生存储
* 交互式图分析
* 高可用和Exactly Once语义
* 高阶API算子开发
* UDF/图算法/Connector插件支持
* 一站式图研发平台
* 云原生部署

### 2.4 快速上手

1. 准备Git、JDK8、Maven、Docker环境。
2. 下载源码：`git clone https://github.com/TuGraph-family/tugraph-analytics`
3. 项目构建：`mvn clean install -DskipTests`
4. 测试任务：`./bin/gql_submit.sh --gql geaflow/geaflow-examples/gql/loop_detection.sql`
3. 构建镜像：`./build.sh --all`
4. 启动容器：`docker run -d --name geaflow-console -p 8888:8888 geaflow-console:0.1`

更多详细内容请参考：[快速上手文档](docs/docs-cn/quick_start.md)。

### 2.5 开发手册

GeaFlow支持DSL和API两套编程接口，您既可以通过GeaFlow提供的类SQL扩展语言SQL+ISO/GQL进行流图计算作业的开发，也可以通过GeaFlow的高阶API编程接口通过Java语言进行应用开发。
* DSL应用开发：[DSL开发文档](docs/docs-cn/application-development/dsl/overview.md)
* API应用开发：[API开发文档](docs/docs-cn/application-development/api/guid.md)


### 2.6 技术架构

GeaFlow整体架构如下所示：

![GeaFlow架构](../static/img/geaflow_arch_new.png)

* [DSL层](./principle/dsl_principle.md)：即语言层。GeaFlow设计了SQL+GQL的融合分析语言，支持对表模型和图模型统一处理。
* [Framework层](./principle/framework_principle.md)：即框架层。GeaFlow设计了面向Graph和Stream的两套API支持流、批、图融合计算，并实现了基于Cycle的统一分布式调度模型。
* [State层](./principle/state_principle.md)：即存储层。GeaFlow设计了面向Graph和KV的两套API支持表数据和图数据的混合存储，整体采用了Sharing Nothing的设计，并支持将数据持久化到远程存储。
* [Console平台](./principle/console_principle.md)：GeaFlow提供了一站式图研发平台，实现了图数据的建模、加工、分析能力，并提供了图作业的运维管控支持。
* **执行环境**：GeaFlow可以运行在多种异构执行环境，如K8S、Ray以及本地模式。

### 2.7 应用场景

#### 2.7.1 实时数仓加速
数仓场景存在大量Join运算，在DWD层往往需要将多张表展开成一张大宽表，以加速后续查询。当Join的表数量变多时，传统的实时计算引擎很难
保证Join的时效性和性能，这也成为目前实时数仓领域一个棘手的问题。基于GeaFlow的实时图计算引擎，可以很好的解决这方面的问题。
GeaFlow以图作为数据模型，替代DWD层的宽表，可以实现数据实时构图，同时在查询阶段利用图的点边物化特性，可以极大加速关系运算的查询。

#### 2.7.2 实时归因分析
在信息化的大背景下，对用户行为进行渠道归因和路径分析是流量分析领域中的核心所在。通过实时计算用户的有效行为路径，构建出完整的转化路径，能够快速帮助业务看清楚产品的价值，帮助运营及时调整运营思路。实时归因分析的核心要点是准确性和实效性。准确性要求在成本可控下保证用户行为路径分析的准确性;实效性则要求计算的实时性足够高，才能快速帮助业务决策。
基于GeaFlow流图计算引擎的能力可以很好的满足归因分析的准确性和时效性要求。如下图所示：
![归因分析](../static/img/guiyin_analysis.png)
GeaFlow首先通过实时构图将用户行为日志转换成用户行为拓扑图，以用户作为图中的点，与其相关的每个行为构建成从该用户指向埋点页面的一条边.然后利用流图计算能力分析提前用户行为子图，在子图上基于归因路径匹配的规则进行匹配计算得出该成交行为相应用户的归因路径，并输出到下游系统。

#### 2.7.3 实时反套现
在信贷风控的场景下，如何进行信用卡反套现是一个典型的风控诉求。基于现有的套现模式分析，可以看到套现是一个环路子图，如何快速，高效在大图中快速判定套现，将极大的增加风险的识别效率。以下图为例，通过将实时交易流、转账流等输入数据源转换成实时交易图，然后根据风控策略对用户交易行为做图特征分析，比如环路检查等特征计算，实时提供给决策和监控平台进行反套现行为判定。通过GeaFlow实时构图和实时图计算能力，可以快速发现套现等异常交易行为，极大降低平台风险。
![实时反套现](../static/img/fantaoxian.png)



## 3. OSGraph

**OSGraph (Open Source Graph)** 是一个开源图谱关系洞察工具，基于GitHub开源数据全域图谱，实现开发者行为、项目社区生态的分析洞察。可以为开发者、项目Owner、开源布道师、社区运营等提供简洁直观的开源数据视图，帮助你和你的项目制作专属的开源名片、寻求契合的开发伙伴、挖掘深度的社区价值。


### 3.1 产品地址

**[https://osgraph.com](https://osgraph.com)**


### 3.2 快速开始

本地启动测试请参考：[OSGraph部署文档](docs/zh-CN/DeveloperManual.md)


### 3.3 功能介绍

当前产品默认提供了6张开源数据图谱供大家体验，包含项目类图谱3个（贡献、生态、社区）、开发类3个（活动、伙伴、兴趣）。


#### 3.3.1  项目贡献图谱

**发现项目核心贡献**：根据项目开发者研发活动信息（Issue、PR、Commit、CR等），找到项目核心贡献者。

**Q**：我想看看给Apache Spark项目写代码的都有谁？

**A**：选择“项目贡献图谱” - 搜索spark - 选择apache/spark。可以看到HyukjinKwon、dongjoon-hyun等核心贡献者，另外还一不小心捉到两个“显眼包”，AmplabJenkins、SparkQA这两个只参与CodeReview的机器人账号。

![](docs/img/spark-contrib.png)


#### 3.3.2 项目生态图谱

**洞察项目生态伙伴**：提取项目间的开发活动、组织等关联信息，构建项目核心生态关系。

**Q**：最近很火的开源大模型Llama3周边生态大致是什么样的？

**A**：选择“项目生态图谱” - 搜索llama3 - 选择meta-llama3/llama3。可以看到pytorch、tensorflow、transformers等知名AI项目，当然还有上科技头条的llama.cpp。比较惊喜的发现是ray竟然和llama3有不少公共开发者，可以深度挖掘一下。

![](docs/img/llama3-eco.png)



#### 3.3.3 项目社区图谱

**分析项目社区分布**：根据项目的开发活动、开发者组织等信息，提取项目核心开发者社区分布。

**Q**：大数据引擎Flink发展这么多年后的社区现状如何？

**A**：选择“项目社区图谱” - 搜索flink - 选择apache/flink。可以看到项目关注者主要来自中、美、德三国，而Alibaba组织是代码贡献的中坚力量。

![](docs/img/flink-comm.png)



#### 3.3.4 开发活动图谱

**展示个人开源贡献**：根据开发者研发活动信息（Issue、PR、Commit、CR等），找到参与的核心项目。

**Q**：大神Linus Torvalds最近在参与哪些开源项目？

**A**：选择“开发活动图谱” - 搜索torvalds。果然linux项目是torvalds的主要工作，不过llvm、mody、libgit2也有所参与，同时也看到他在subsurface这种“潜水日志管理工具”上的大量贡献，果然大佬的爱好都很广泛。

![](docs/img/torvalds-act.png)



#### 3.3.5 开源伙伴图谱

**寻找个人开源伙伴**：找到开发者在开源社区中，与之协作紧密的其他开发者。

**Q**：我想知道在开源社区有没有和我志同道合的人？

**A**：选择“开发伙伴图谱” - 搜索我的ID。让我震惊的是有那么多陌生人和我关注了同一批项目，这不得找机会认识一下，说不定就能找到新朋友了。而和我合作PR的人基本上都是我认识的朋友和同事，继续探索一下朋友们的开源伙伴，开源社区的“六度人脉”不就来了么。

![](docs/img/fanzhidongyzby-part.png)



#### 3.3.6 开源兴趣图谱

**挖掘个人开源兴趣**：根据参与的项目主题、标签等信息，分析开发者技术领域与兴趣。

**Q**：GitHub上最活跃的开发者对什么技术感兴趣？

**A**：选择“开源兴趣图谱” - 搜索sindresorhus（[GitHub用户榜](https://gitstar-ranking.com) No.1）。整体来看sindresorhus对node、npm、js很感兴趣，另外他发起的awesome项目足足30W星，令人咋舌！当前的开源兴趣数据主要来自项目有限的标签信息，后续借助AI技术可能会有更好的展现。

![](docs/img/sindresorhus-intr.png)


### 3.4 未来规划

未来将会有更多有趣的图谱和功能加入到OSGraph：

* 简单灵活的API设计，让图谱无限扩展。
* 自由高效的画布交互，无限探索数据价值。
* 图谱URL支持嵌入Markdown，制作我的开源名片。
* 基于AI技术的项目主题标签分析。
* 多人多项目联合分析，图谱洞察一键可达。
* 更丰富的数据展示与多维分析。
* **更多功能，与你携手共建……**



## 4. ChatTuGraph

ChatTuGraph通过AI技术为TuGraph赋能，可以为图业务研发效能、图产品解决方案、图数据智能分析、图任务自动管控等领域带来更丰富的应用场景。
目前ChatTuGraph通过图语言语料生成，借助大模型微调技术实现了自然语言的图数据分析，构建Graph RAG基于知识图谱实现检索增强生成，以降低大模型的推理幻觉，以及通过多智能体技术（Multiple Agents System）实现图数据上的AIGC、智能化等能力。
