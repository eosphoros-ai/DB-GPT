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
    jieba.load_userdict("/datas/liab/DB-GPT-main/tests/userdict.txt")
    tokenizerd_query = list(jieba.cut(query))
    tokenized_corpus = [list(jieba.cut(doc)) for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    doc_scores = bm25.get_scores(tokenizerd_query)
    return score_normalize(doc_scores)



