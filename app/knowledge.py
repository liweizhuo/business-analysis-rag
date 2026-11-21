"""BGE-M3 dense/sparse → Milvus → 恢复父文 → CrossEncoder重排。"""
from functools import lru_cache
from milvus_model.hybrid import BGEM3EmbeddingFunction
from pymilvus import MilvusClient, AnnSearchRequest, WeightedRanker
from sentence_transformers import CrossEncoder
from .settings import env


def sparse_row(matrix, index):
    # 使用CSR的getrow，避免不同稀疏矩阵切片形式造成行索引差异。
    row = matrix.tocsr().getrow(index)
    return {int(k): float(v) for k, v in zip(row.indices, row.data)}


class Knowledge:
    def __init__(self):
        self.embedding = BGEM3EmbeddingFunction(
            model_name_or_path=env('EMBEDDING_MODEL', 'BGE-M3'), device='cpu',
            use_fp16=False,
        )
        self.client = MilvusClient(uri=env('MILVUS_URI'), token=env('MILVUS_TOKEN'))
        self.reranker = CrossEncoder(env('RERANKER_MODEL', '重排模型'))
        self.collection = 'business_knowledge'

    def search(self, question, config):
        # 在线只编码当前问题；离线已编码的子块保存在Milvus，不重新编码全文。
        vectors = self.embedding([question])
        # 过滤值来自维护配置，通过JSON转义构造表达式。
        import json
        expression = (f'source == {json.dumps(config["source"])} and '
                      f'document_version == {json.dumps(config["knowledge_version"])}')
        # 两个请求分别检索dense语义信号和learned sparse词项信号。
        # WeightedRanker用于一次融合，之后不再叠加RRF。
        requests = [
            AnnSearchRequest(data=[vectors['dense'][0].tolist()],
                             anns_field='dense_vector', limit=12, expr=expression,
                             param={'metric_type': 'IP', 'params': {}}),
            AnnSearchRequest(data=[sparse_row(vectors['sparse'], 0)],
                             anns_field='sparse_vector', limit=12, expr=expression,
                             param={'metric_type': 'IP', 'params': {}}),
        ]
        hits = self.client.hybrid_search(
            collection_name=self.collection, reqs=requests,
            ranker=WeightedRanker(0.7, 1.0), limit=12,
            output_fields=['parent_id', 'parent_content', 'document_version', 'source',
                           'source_file', 'start_line', 'end_line'],
        )[0]
        # 多个子块可能属于同一父块，按parent_id去重，避免上下文重复。
        parents = {}
        for hit in hits:
            item = dict(hit['entity'])
            item['evidence_id'] = item['parent_id']
            parents[item['parent_id']] = item
        docs = list(parents.values())
        if not docs:
            return []
        # CrossEncoder同时读取问题和父文打分，区别于向量点积检索。
        scores = self.reranker.predict([(question, d['parent_content']) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda pair: float(pair[1]), reverse=True)
        return [dict(doc, score=float(score)) for doc, score in ranked[:3]]


@lru_cache(maxsize=1)
def knowledge():
    # 在线首次使用时加载一次；每个服务进程独立缓存，不在每次提问时重建索引。
    return Knowledge()
