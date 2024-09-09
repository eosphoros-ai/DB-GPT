# Chat Knowledge Base

`Chat knowledge Base` provides the ability to question and answer questions based on private domain knowledge, and can build intelligent question and answer systems, reading assistants and other products based on the `knowledge base`. `RAG` technology is also used in DB-GPT to enhance knowledge retrieval.


## Noun explanation

:::info note

`Knowledge Space`: is a document space that manages a type of knowledge. Document knowledge of the same type can be uploaded to a knowledge space.
:::


## Steps
The knowledge base operation process is relatively simple and is mainly divided into the following steps.
- 1.Create knowledge space
- 2.Upload documents
- 3.Wait for document vectorization
- 4.Select Knowledge Base App
- 5.Chat With App


### Create knowledge space

At first open the `Construct App` and select the `Knowledge` on the top.

<p align="center">
  <img src={'/img/app/knowledge_build_v0.6.jpg'} width="800px" />
</p>

Select the knowledge base, click the `Create` button, and fill in the necessary information to complete the creation of the knowledge space.


<p align="center">
  <img src={'/img/app/knowledge_space_v0.6.jpg'} width="800px" />
</p>

### Upload documents

Document addition currently supports multiple types, such as plain text, URL crawling, and various document types such as PDF, Word, and Markdown. Select a specific document to `upload`.

<p align="left">
  <img src={'/img/chat_knowledge/upload_doc.png'} width="720px" />
</p>


Select one or more corresponding documents and click `next`.


<p align="left">
  <img src={'/img/chat_knowledge/upload_doc_finish.png'} width="720px" />
</p>

###  Documents Segmentation

Choose Document Segmentation, you can choose to segment the document by chunk size, separator, paragraph or markdown header. The default is to segment the document by chunk size.

and click Process, it will take a few minutes to complete the document segmentation.

<p align="left">
  <img src={'/img/chat_knowledge/doc_segmentation.png'} width="720px" />
</p>

:::tip
**Automatic: The document is automatically segmented according to the document type.**

**Chunk size: The number of words in each segment of the document. The default is 512 words.**
    - chunk size: The number of words in each segment of the document. The default is 512 words.
    - chunk overlap: The number of words overlapped between each segment of the document. The default is 50 words.
** Separator:segmentation by separator ** 
    - separator: The separator of the document. The default is `\n`.
    - enable_merge: Whether to merge the separator chunks according to chunk_size after splits. The default is `False`.
** Page: page segmentation, only support .pdf and .pptx document.**

** Paragraph: paragraph segmentation, only support .docx document.**
    - separator: The paragraph separator of the document. The default is `\n`.

** Markdown header: markdown header segmentation, only support .md document.**
:::


### Waiting for document vectorization

Click on the `knowledge space` and observe the document `slicing` + `vectorization` status in the lower left corner. When the status reaches `FINISHED`, you can start a knowledge base conversation.


<p align="left">
  <img src={'/img/chat_knowledge/waiting_doc_vector.png'} width="720px" />
</p>


### Knowledge base chat

Click the `Chat`button to start a conversation with the knowledge base.


<p align="left">
  <img src={'/img/chat_knowledge/chat.png'} width="720px" />
</p>


### Reading assistant
In addition to the above capabilities, you can also upload documents directly in the knowledge base dialogue window, and the document will be summarized by default. This capability can be used as a `reading assistant` to assist document reading.

<p align="left">
  <img src={'/img/chat_knowledge/read_helper.gif'} width="720px" />
</p>