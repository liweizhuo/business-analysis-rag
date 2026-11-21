"""集中读取服务端配置；密钥不会传给浏览器或模型。"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# 始终从工程根目录加载.env，避免不同启动目录造成配置文件定位错误。
load_dotenv(ROOT / '.env')


def env(name: str, default: str = '') -> str:
    return os.getenv(name, default)


def business() -> dict:
    # 这里只读取维护者发布的配置，不允许模型生成或覆盖业务规则。
    # 相对路径基于ROOT；修改配置后下次读取即可生效，正式发布应避免中途修改。
    return json.loads((ROOT / env('CONFIG_FILE', 'config/business.json')).read_text('utf-8'))
