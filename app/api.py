"""FastAPI入口；浏览器只提交问题与访问密钥，不持有数据库凭据。"""
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .settings import business
from .service import ask

app = FastAPI(title='经营分析问答系统')
app.mount('/assets', StaticFiles(directory=Path(__file__).parent / 'static'), name='assets')


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # 本版不信任浏览器回传的已确认历史，追问需重新写清问题。


@app.get('/', include_in_schema=False)
def index():
    return FileResponse(Path(__file__).parent / 'static' / 'index.html')


@app.get('/health')
def health():
    return {'status': 'ok', 'note': '仅表示Web服务存活，不表示外部服务已联通'}


@app.post('/api/ask')
def question(body: Question, x_api_key: str = Header(default='')):
    identity = business()['users'].get(x_api_key)
    if not identity:
        raise HTTPException(401, '访问密钥无效')
    try:
        return ask(body.question, identity, [])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # 外部错误细节不传给浏览器，避免暴露连接信息。
        import logging
        logging.getLogger(__name__).exception('问答处理失败')
        raise HTTPException(503, '外部服务暂不可用，请检查服务端日志和配置') from exc
