# Chat Knowledge

`Chat knowledge` provides the ability to question and answer questions based on private domain knowledge, and can build intelligent question and answer systems, reading assistants and other products based on the `knowledge base`. `RAG` technology is also used in DB-GPT to enhance knowledge retrieval.


## Noun explanation


:::info note

`Knowledge Space`: is a document space that manages a type of knowledge. Document knowledge of the same type can be uploaded to a knowledge space.
:::


## Steps
The knowledge base operation process is relatively simple and is mainly divided into the following steps.
- 1.Create knowledge space
- 2.Upload documents
- 3.Wait for document vectorization
- 4.Knowledge base chat


### Create knowledge space

Select the knowledge base, click the `Create` button, and fill in the necessary information to complete the creation of the knowledge space.



<p align="left">
  <img src={'/img/chat_knowledge/create_knowledge_base.png'} width="720px"/>
</p>

### Upload documents

Document addition currently supports multiple types, such as plain text, URL crawling, and various document types such as PDF, Word, and Markdown. Select a specific document to `upload`.

<p align="left">
  <img src={'/img/chat_knowledge/upload_doc.png'} width="720px" />
</p>


Select the corresponding document and click `Finish`.


<p align="left">
  <img src={'/img/chat_knowledge/upload_doc_finish.png'} width="720px" />
</p>


### Waiting for document vectorization

Click on the `knowledge space` and observe the document `slicing` + `vectorization` status in the lower left corner. When the status reaches `FINISHED`, you can start a knowledge base conversation.


<p align="left">
  <img src={'/img/chat_knowledge/waiting_doc_vector.png'} width="720px" />
</p>


### Knowledge base chat

Click the `Chat`button to start a conversation with the knowledge base.


<p align="left">
  <img src={'/img/chat_knowledge/chat.gif'} width="720px" />
</p>


### Reading assistant
In addition to the above capabilities, you can also upload documents directly in the knowledge base dialogue window, and the document will be summarized by default. This capability can be used as a `reading assistant` to assist document reading.

<p align="left">
  <img src={'/img/chat_knowledge/read_helper.gif'} width="720px" />
</p>