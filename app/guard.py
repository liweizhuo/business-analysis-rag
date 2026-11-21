"""保守SQL门禁：当前仅开放单表、固定金额聚合；不声称支持任意SQL。

模型直接生成SQL，程序解析并核验其结构；未开放结构一律拒绝。
命名占位符先作为SQLGlot参数解析，通过后才转PyMySQL绑定形式。
"""
import re
from dataclasses import dataclass
import sqlglot
from sqlglot import exp


@dataclass(frozen=True)
class CheckedQuery:
    sql: str
    parameters: dict
    operation: str


def validate(candidate, config, identity):
    sql = candidate['sql']
    operation = candidate['operation']
    params = candidate['parameters']
    if operation not in {'value', 'qoq'} or not isinstance(sql, str):
        raise ValueError('当前仅开放单期金额和环比金额查询')
    expected_params = {'current', 'base'} if operation == 'qoq' else {'current'}
    if not isinstance(params, dict) or set(params) != expected_params:
        raise ValueError('查询参数不符合约定')
    for period in params.values():
        if not isinstance(period, str) or not re.fullmatch(r'\d{4}Q[1-4]', period):
            raise ValueError('季度参数格式错误')
        if not config['rule']['effective_from'] <= period <= config['rule']['effective_until']:
            raise ValueError('查询周期不在已发布规则适用期')
    if operation == 'qoq':
        def quarter_index(p):
            return int(p[:4]) * 4 + int(p[-1])
        if quarter_index(params['current']) - quarter_index(params['base']) != 1:
            raise ValueError('环比必须比较相邻季度')
    if candidate['rule_ids'] != [config['rule']['id']]:
        raise ValueError('指标规则引用不一致')
    trees = sqlglot.parse(sql, read='mysql')
    if len(trees) != 1 or not isinstance(trees[0], exp.Select):
        raise ValueError('仅开放单条SELECT')
    tree = trees[0]
    # 用完整AST与允许的语义结构逐项比较，而非只检查SELECT开头。
    # 只将WHERE的AND顺序归一化；OR、子查询、额外条件不能通过。
    periods = 'quarter IN (:base, :current)' if operation == 'qoq' else 'quarter = :current'
    table = config['table']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
        raise ValueError('维护配置表名非法')
    expected = sqlglot.parse_one(
        f'SELECT quarter, SUM(amount_yuan) AS amount FROM {table} '
        f'WHERE snapshot_id = :snapshot_id AND region = :authorized_region '
        f'AND include_flag = 1 AND {periods} GROUP BY quarter', read='mysql')

    def normalized(node):
        copy = node.copy()
        where = copy.args.get('where')
        predicates = []
        if where:
            def flatten(expr):
                if isinstance(expr, exp.And):
                    flatten(expr.left)
                    flatten(expr.right)
                else:
                    predicates.append(expr.sql(dialect='mysql'))
            flatten(where.this)
            copy.set('where', None)
        return copy, sorted(predicates)

    if normalized(tree) != normalized(expected):
        raise ValueError('SQL超出已开放聚合结构或遗漏权限、版本、业务约束')
    # 不允许检查后由模型改写；从同一已核验AST序列化执行。
    final_sql = tree.sql(dialect='mysql')
    final_sql = re.sub(r':([A-Za-z_][A-Za-z0-9_]*)', r'%(\1)s', final_sql)
    bound = dict(params, snapshot_id=config['snapshot_id'],
                 authorized_region=identity['authorized_region'])
    return CheckedQuery(final_sql, bound, operation)
