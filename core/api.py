from pathlib import Path

from ninja import NinjaAPI

api = NinjaAPI(
    title='API do Chatbot IntegraCAR',
    version='1.0.0',
    description=Path(__file__)
    .with_name('api_guide.md')
    .read_text(encoding='utf-8'),
    docs_url='/docs',
    openapi_url='/openapi.json',
)


api.add_router('', 'chat.api.chat_router')
