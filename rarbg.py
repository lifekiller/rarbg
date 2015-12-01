''' rarbg api → rss
    https://torrentapi.org/apidocs_v2.txt '''

import asyncio

from datetime import datetime, timedelta
from dateutil import parser
from email.utils import formatdate
from urllib.parse import parse_qs

from aiohttp import get, web
from humanize import naturalsize
from jinja2 import Template


API_ENDPOINT = 'https://torrentapi.org/pubapi_v2.php'
TEMPLATE = Template(open('feed.xml').read())
TOKEN_LIFESPAN = timedelta(minutes=15)

app = web.Application()
app.token = None
app.token_got = datetime.now()


async def update_token():
    token_expired = datetime.now() > app.token_got + TOKEN_LIFESPAN
    if not app.token or token_expired:
        resp = await get(API_ENDPOINT, params={'get_token': 'get_token'})
        data = await resp.json()
        app.token = data['token']
        app.token_got = datetime.now()


async def rarbg_rss(request):
    params = dict(request.GET)
    print(params)

    await update_token()
    params.update(token=app.token, format='json_extended')

    resp = await get(API_ENDPOINT, params=params)
    data = await resp.json()

    if 'error' in data:
        print('! too many requests')
        return web.HTTPServiceUnavailable(text=data['error'])

    for i in data['torrent_results']:
        i.update(
            pubdate=formatdate(parser.parse(i['pubdate']).timestamp()),
            hsize=naturalsize(i['size'], gnu=True),
            hash=parse_qs(i['download'])['magnet:?xt'][0].split(':')[-1],
        )

    result = TEMPLATE.render(title='rarbg', entries=data['torrent_results'])
    return web.Response(text=result)


app.router.add_route('GET', '/', rarbg_rss)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    handler = app.make_handler()
    f = loop.create_server(handler, '0.0.0.0', 8080)
    srv = loop.run_until_complete(f)
    print('serving on', srv.sockets[0].getsockname())
    loop.run_forever()
