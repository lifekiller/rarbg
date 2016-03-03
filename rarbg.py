''' rarbg api → rss
    https://torrentapi.org/apidocs_v2.txt '''

import asyncio

from datetime import datetime, timedelta
from email.utils import formatdate
from urllib.parse import parse_qs

from aiohttp import get, web
from dateutil import parser
from humanize import naturalsize
from jinja2 import Template
from click import secho

API_ENDPOINT = 'https://torrentapi.org/pubapi_v2.php'
API_RATE_LIMIT = timedelta(seconds=2)
TOKEN_LIFESPAN = timedelta(minutes=15)

TEMPLATE = Template('''
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
    <channel>
        <title>{{title}}</title>
        <link>https://torrentapi.org/apidocs_v2.txt</link>
        <ttl>3600</ttl>
        {% for entry in entries %}
        <item>
            <title>{{entry.title}} ({{entry.hsize}})</title>
            <description/>
            <guid>{{entry.hash}}</guid>
            <pubDate>{{entry.pubdate}}</pubDate>
            <enclosure
                url="{{entry.download}}"
                length="{{entry.size}}"
                type="application/x-bittorrent" />
        </item>
        {% endfor %}
    </channel>
</rss>
''')

app = web.Application()
app.token = None
app.token_got = datetime.now()
app.counter = 0


class RateLimit:

    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.next_call = datetime.now()

    async def __aenter__(self):
        now = datetime.now()
        self.next_call = max(now, self.next_call) + self.rate_limit
        sleep = self.next_call - now - self.rate_limit
        await asyncio.sleep(sleep.total_seconds())

    async def __aexit__(self, exc_type, exc, tb):
        pass


api_rate_limit = RateLimit(API_RATE_LIMIT)


def pretty(data: dict):
    return ', '.join(['='.join(pair) for pair in data.items()])


async def update_token():
    token_expired = datetime.now() > app.token_got + TOKEN_LIFESPAN
    if not app.token or token_expired:
        resp = await get(API_ENDPOINT, params={'get_token': 'get_token'})
        data = await resp.json()
        app.token = data['token']
        app.token_got = datetime.now()
        secho('token refreshed - {}'.format(app.token), fg='yellow')


async def api(params):
    app.counter += 1
    request_id = app.counter
    query_text = pretty(params)
    secho('[{}] {}'.format(request_id, query_text), fg='cyan')

    async with api_rate_limit:
        await update_token()
        params.update(token=app.token, format='json_extended')
        resp = await get(API_ENDPOINT, params=params)
        data = await resp.json()

    if 'error' in data:
        secho('[{}] {}'.format(request_id, data['error']), fg='red')
        return web.HTTPServiceUnavailable(text=data['error'])

    for i in data['torrent_results']:
        i.update(
            pubdate=formatdate(parser.parse(i['pubdate']).timestamp()),
            hsize=naturalsize(i['size'], gnu=True),
            hash=parse_qs(i['download'])['magnet:?xt'][0].split(':')[-1],
        )

    num_results = len(data['torrent_results'])
    secho('[{}] {} results'.format(request_id, num_results), fg='green')

    result = TEMPLATE.render(title='rarbg', entries=data['torrent_results'])
    return web.Response(text=result)


async def rarbg_rss(request):
    params = dict(request.GET)
    if 'string' in request.match_info:
        params.update(mode='search', search_string=request.match_info['string'])
    if 'imdb' in request.match_info:
        params.update(mode='search', search_imdb=request.match_info['imdb'])
    if 'tvdb' in request.match_info:
        params.update(mode='search', search_tvdb=request.match_info['tvdb'])
    return await api(params)


app.router.add_route('GET', '/', rarbg_rss)
app.router.add_route('GET', '/search/{string}', rarbg_rss)
app.router.add_route('GET', '/imdb/{imdb}', rarbg_rss)
app.router.add_route('GET', '/tvdb/{tvdb}', rarbg_rss)


def main():
    loop = asyncio.get_event_loop()
    handler = app.make_handler()
    f = loop.create_server(handler, '0.0.0.0', 4444)
    srv = loop.run_until_complete(f)
    loop.run_until_complete(update_token())
    secho('serving on {}:{}'.format(*srv.sockets[0].getsockname()), fg='yellow')
    loop.run_forever()


if __name__ == '__main__':
    main()
