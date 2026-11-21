"""离线入口：只建立知识索引，不在在线请求中执行。"""
import hashlib
from pathlib import Path
from pymilvus import DataType
from app.knowledge import knowledge, sparse_row
from app.settings import env, business


def chunks(path):
    """按标题/段落生成父块，父块内生成重叠子块，保留原始行范围。"""
    lines = path.read_text('utf-8-sig').splitlines()
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    parents, buf, start = [], [], 1
    for number, line in enumerate(lines, 1):
        if buf and ((line.startswith('#') and len('\n'.join(buf)) > 300)
                    or len('\n'.join(buf)) + len(line) > 1200):
            parents.append((start, number - 1, '\n'.join(buf)))
            buf, start = [], number
        buf.append(line)
    if buf:
        parents.append((start, len(lines), '\n'.join(buf)))
    for start, end, parent in parents:
        parent_id = hashlib.sha256(f'{path.name}:{version}:{start}'.encode()).hexdigest()[:24]
        for offset in range(0, len(parent), 250):
            yield dict(id=f'{parent_id}_{offset}', text=parent[offset:offset+300],
                       parent_id=parent_id, parent_content=parent,
                       document_version=version, source_file=path.name,
                       start_line=start, end_line=end)


def main():
    # 离线建库要显式执行。本入口不导入经营金额，不修改MySQL。
    config = business()
    rows = list(chunks(Path(env('KNOWLEDGE_FILE', '知识库.md'))))
    if not rows:
        raise ValueError('知识库为空')
    engine = knowledge()
    client = engine.client
    # 首次创建集合；后续upsert保留其他版本，由在线发布版本过滤隔离。
    # 如果更换Embedding维度，须另建兼容集合，不可复用旧向量。
    if not client.has_collection(engine.collection):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field('id', DataType.VARCHAR, is_primary=True, max_length=128)
        for name, length in [('text', 8192), ('parent_content', 32768),
                             ('parent_id', 128), ('document_version', 128),
                             ('source_file', 1024), ('source', 128)]:
            schema.add_field(name, DataType.VARCHAR, max_length=length)
        for name in ['start_line', 'end_line']:
            schema.add_field(name, DataType.INT64)
        schema.add_field('dense_vector', DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field('sparse_vector', DataType.SPARSE_FLOAT_VECTOR)
        indexes = client.prepare_index_params()
        indexes.add_index(field_name='dense_vector', index_type='FLAT', metric_type='IP')
        indexes.add_index(field_name='sparse_vector', index_type='SPARSE_INVERTED_INDEX', metric_type='IP')
        client.create_collection(engine.collection, schema=schema, index_params=indexes)
    for start in range(0, len(rows), 32):
        batch = rows[start:start+32]
        vectors = engine.embedding([row['text'] for row in batch])
        records = [dict(row, source=config['source'],
                        dense_vector=vectors['dense'][i].tolist(),
                        sparse_vector=sparse_row(vectors['sparse'], i))
                   for i, row in enumerate(batch)]
        client.upsert(engine.collection, records)
    print('知识库写入完成。请核对后将以下版本登记到业务配置，再发布：')
    print(rows[0]['document_version'])


if __name__ == '__main__':
    main()
