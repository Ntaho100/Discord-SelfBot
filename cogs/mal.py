import aiohttp
import asyncio
import discord
import spice_api as spice

from bs4 import BeautifulSoup
from discord.ext import commands
from lxml import etree
from urllib.parse import parse_qs
from .utils import config
from .utils.checks import permEmbed, send


class Mal:

    def __init__(self, bot):
        self.bot = bot
        self.malid = None
        self.config = config.Config('config.json')
        self.loop = asyncio.get_event_loop()

    async def get_google_entries(self, query, search):
        params = {
            'as_q': search,
            'as_epq': query,
            'as_sitesearch': 'myanimelist.net'
            }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64)'
            }
        entries = []
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://www.google.com/search', params=params, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError('Google somehow failed to respond.')
                root = etree.fromstring(await resp.text(), etree.HTMLParser())
                search_nodes = root.findall(".//div[@class='g']")
                for node in search_nodes:
                    url_node = node.find('.//h3/a')
                    if url_node is None:
                        continue
                    url = url_node.attrib['href']
                    if not url.startswith('/url?'):
                        continue
                    if search in url:
                        if ('/recommendations/' in url) or ('/character/' in url) or ('/featured/' in url):
                            continue
                        url = parse_qs(url[5:])['q'][0]
                        entries.append(url)
                try:
                    content = entries[0].split('/')[4]
                except:
                    content = None
            cs.close()
        self.malid = content
        return content

    def getMal(self, i, _type):
        creds = spice.init_auth(self.config.get('mal_username', []), self.config.get('mal_password', []))
        return spice.search_id(int(i), spice.get_medium(_type), creds)

    def parse_content(self, i, _type):
        mal = self.getMal(i, _type)
        synopsis = BeautifulSoup(mal.synopsis, 'lxml').get_text().replace('[i]', '').replace('[/i]', '')
        synnew = ''
        for i in synopsis.split('.'):
            if (len(synnew + i + '.')) <= 1024:
                    synnew += i + '.'
            else:
                synnew += '..'
        if (mal.raw_data.start_date is None) or ('00' in mal.raw_data.start_date.text):
            start = 'Unknown'
        else:
            start = mal.raw_data.start_date.text
        if (mal.raw_data.end_date is None) or ('00' in mal.raw_data.end_date.text):
            end = 'Unknown'
        else:
            end = mal.raw_data.end_date.text
        e = discord.Embed(colour=0x0057e7, description='**Alternative:** {}'.format(mal.english))
        e.set_author(name=mal.title, icon_url='https://myanimelist.cdn-dena.com/img/sp/icon/apple-touch-icon-256.png')
        e.set_thumbnail(url=mal.image_url)
        e.add_field(name='Synopsis', value=synnew.replace('[Written by MAL Rewrite].', '')+' [[more]](https://myanimelist.net/anime/{}/)'.format(mal.id), inline=False)
        e.add_field(name='Score', value=mal.score + '/10', inline=True)
        if _type is 'anime':
            e.add_field(name='Episodes', value=mal.episodes, inline=True)
            e.add_field(name='Type', value=mal.anime_type, inline=True)
        elif _type is 'manga':
            chap = 'Unknown' if mal.chapters == '0' else mal.chapters
            e.add_field(name='Chapters', value=chap, inline=True)
            e.add_field(name='Type', value=mal.manga_type, inline=True)
        e.add_field(name='Status', value=mal.status, inline=True)
        if _type is 'anime':
            e.set_footer(text='Aired: {} - {}'.format(start, end))
        elif _type is 'manga':
            e.set_footer(text='Published: {} - {}'.format(start, end))
        return e

    # MyAnimelist Anime
    @commands.command()
    async def anime(self, ctx, *, query):
        se = await ctx.send(content='Searching...')
        try:
            content = await self.loop.run_in_executor(None, self.get_google_entries, query, 'anime')
            await content
        except RuntimeError as e:
            await send(ctx, content=str(e), ttl=3)
        else:
            if content is None:
                await send(ctx, content='No results found... sorry.', ttl=3)
            else:
                em = await self.loop.run_in_executor(None, self.parse_content, self.malid, 'anime')
                try:
                    if permEmbed(ctx.message):
                        await send(ctx, embed=em)
                    else:
                        await send(ctx, content='https://myanimelist.net/anime/{}'+content)
                except:
                    await send(ctx, content='Error!, Embed might have failed you', ttl=3, delete=False)
        await se.delete()

    # MyAnimelist Manga
    @commands.command()
    async def manga(self, ctx, *, query):
        se = await ctx.send(content='Searching...')
        try:
            i, link = await self.get_google_entries(query, 'manga')
        except RuntimeError as e:
            await send(ctx, content=str(e), ttl=3)
        else:
            if (i is None) or (not i.isdigit()):
                await se.delete()
                return await send(ctx, content='No results found... sorry.', ttl=3)
            else:
                em = await self.parse_content(i, link, 'manga')
                try:
                    if permEmbed(ctx.message):
                        await send(ctx, embed=em)
                    else:
                        await send(ctx, content=link)
                except:
                    await send(ctx, content='Error!, Embed might have failed you', ttl=3)
                await se.delete()


def setup(bot):
    bot.add_cog(Mal(bot))
