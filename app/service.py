"""主线编排入口：知识→模型SQL→门禁→MySQL→确定性计算→回答。"""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from .db import connection
from .guard import validate
from .knowledge import knowledge
from .llm import generate
from .settings import business


def ask(question, identity, confirmed_context):
    # 第1步：读取已发布的指标、schema、知识版本和数据版本。
    # identity由API密钥映射得到，不能使用问题中自称的身份或地区。
    config = business()
    if not config['published']:
        raise ValueError('业务规则尚未核对发布，请先完善业务配置')
    if config['rule']['source_version'] != config['knowledge_version']:
        raise ValueError('规则与知识版本不一致')
    # 第2步：原问题做dense/sparse编码，召回子块，再恢复和重排父文。
    # evidence提供口径依据，不包含经营明细的完整汇总。
    evidence = knowledge().search(question, config)
    if not evidence:
        return dict(status='clarify', answer='未找到当前有效的口径依据，暂停查数。', evidence=[])
    context = dict(current_date=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(),
                   confirmed_history=confirmed_context)
    # 第3步：真正调用生成模型，输出候选SQL或澄清，不在这里执行SQL。
    candidate = generate(question, config, evidence, context)
    if candidate['status'] != 'ok':
        if candidate['sql'] is not None or candidate['parameters'] != {}:
            raise ValueError('非查询响应不得携带SQL或参数')
        return dict(status=candidate['status'], answer=candidate['message'], evidence=evidence)
    # 第4步：模型不能给自己授权。门禁核对SQL结构与口径，
    # 然后用服务端snapshot_id、authorized_region绑定可信参数。
    checked = validate(candidate, config, identity)
    with connection() as conn:
        with conn.cursor() as cursor:
            # 第5步：只执行已校验SQL，参数单独交驱动绑定，不能字符串拼接。
            cursor.execute(checked.sql, checked.parameters)
            rows = cursor.fetchmany(3)
    # 第6步：查询成功不等于结果完整；检查实际返回季度与预期一致。
    expected = set(candidate['parameters'].values())
    if len(rows) > len(expected) or len({r['quarter'] for r in rows}) != len(rows):
        raise ValueError('结果粒度不符合约定')
    amounts = {r['quarter']: r['amount'] for r in rows}
    if set(amounts) != expected or any(v is None for v in amounts.values()):
        return dict(status='no_data', answer='缺少完整期间数据，不自动补零。', evidence=evidence)
    current = candidate['parameters']['current']
    # 第7步：金额用Decimal，不用浮点数；缺记录和NULL不能默认为0。
    current_amount = Decimal(str(amounts[current]))
    answer = f'{current}新签金额为{current_amount}元。'
    if checked.operation == 'qoq':
        base = candidate['parameters']['base']
        first = Decimal(str(amounts[base]))
        delta = current_amount - first
        answer += f'基期{base}为{first}元，差额为{delta}元。'
        answer += (f'环比增长率为{delta / first * 100:.2f}%。' if first > 0
                   else '基期为零或负数，不输出普通增长率。')
    answer += f'统计范围：{identity["authorized_region"]}；数据截至：{config["data_as_of"]}。'
    return dict(status='ok', answer=answer, evidence=evidence,
                sql=checked.sql, rows=[{k: str(v) for k, v in row.items()} for row in rows],
                snapshot_id=config['snapshot_id'], rule_id=config['rule']['id'])
