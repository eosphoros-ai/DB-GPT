# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/6 上午10:38
'''
def score_normalize(data_list):
    max_value = max(data_list)
    min_value = min(data_list)
    return [(i-min_value)/(max_value-min_value) for i in data_list]

def calcuate_bm25(corpus, query):
    import jieba
    from rank_bm25 import BM25Okapi
    jieba.load_userdict("/datas/liab/DB-GPT/tests/userdict.txt")
    stop_words = [' ','\t','\n']
    with open('/datas/liab/DB-GPT/tests/stopwords.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                stop_words.append(line)

    tokenizerd_query = [jiebaword.upper() for jiebaword in list(jieba.cut(query))  if jiebaword not in stop_words]
    print('tokenizerd_query',tokenizerd_query)
    tokenized_corpus = [[jiebaword.upper() for jiebaword in list(jieba.cut(doc)) if jiebaword not in stop_words] for doc in corpus]
    print('tokenized_corpus',tokenized_corpus)
    bm25 = BM25Okapi(tokenized_corpus)
    doc_scores = bm25.get_scores(tokenizerd_query)
    return score_normalize(doc_scores)



