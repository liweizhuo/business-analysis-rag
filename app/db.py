"""请求独立连接，只读事务；不把模型提供的身份当作授权。"""
from contextlib import contextmanager
import pymysql
from .settings import env


@contextmanager
def connection():
    # 创建请求独立连接。MYSQL_DATABASE虽然以sql.db占位，仍然是MySQL库名。
    # 管理员还应给该账号配置SELECT权限，本代码不会创建数据库和业务表。
    conn = pymysql.connect(
        host=env('MYSQL_HOST'), port=int(env('MYSQL_PORT', '3306')),
        user=env('MYSQL_USER'), password=env('MYSQL_PASSWORD'),
        database=env('MYSQL_DATABASE', 'sql.db'), charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10, read_timeout=15, write_timeout=10, autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute('SET SESSION MAX_EXECUTION_TIME=10000')
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            # 在同一事务中读取固定快照；数据发布者需保证版本记录不可变。
            cur.execute('START TRANSACTION READ ONLY')
        yield conn
    finally:
        # 只读请求不提交；正常或异常都释放事务和连接。
        conn.rollback()
        conn.close()
