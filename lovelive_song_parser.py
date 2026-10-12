#!/usr/bin/env python3

import os
import sys
import re
import aiohttp
import json
import asyncio
import locale

from bs4 import BeautifulSoup as bs
from local import local
from progress import Progress
from urllib import parse

if sys.platform == 'win32':
    import ctypes
    ui_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    LANG = locale.windows_locale[ui_id].split('_')[0]
else:
    LANG = locale.getdefaultlocale()[0].split('_')[0]
PR = Progress()


class LLSongs:

    # Set variables
    def __init__(self):
        self.__URL_FANDOM = 'https://love-live.fandom.com/api.php'     # Change links to Fandom
        self.__URL_GROUPS = [                                          # if they have changed or
            ['Love_Live!', 'text_m'],                                  # new ones have been added.
            ['Love_Live!_Sunshine!!', 'text_aq'],
            ['Love_Live!_Nijigasaki_High_School_Idol_Club', 'text_ng'],
            ['Love_Live!_Superstar!!', 'text_li']
        ]
        self.__songs_list = {}
        self.__amount_songs = 0
        self.__amount_songs_downloaded = 0
        self.__amount_error_songs = 0
        self.LL_FILE = 'lovelive_songs_list.json' # It can be changed.
        self.CHUNK_SIZE = 8192 # Download chunk size

    def load_songs_list(self):
        self.__amount_songs = 0
        try:
            self.__songs_list = json.load(open(self.LL_FILE))
            for key in self.__songs_list:
                self.__amount_songs += len(self.__songs_list[key])
            return self.__songs_list
        except:
            return False

    async def __parse_song(self, song, group, session):
        async with session.get(self.__URL_FANDOM + '?page=' + song, params={'action' : 'parse', 'format' : 'json'}) as resp:
            result = await resp.json()
        result = bs(result['parse']['text']['*'], 'html.parser')
        if 'Redirect to' in str(result):
            return await self.__parse_song(result.find('a').attrs['href'][6:], group, session)
        for source in result.find_all('source'):
            song_result = [
                        parse.unquote(source.attrs['src'].split('/')[-3].replace('_', ' ')),
                        '/'.join(source.attrs['src'].split('/')[:-2])
            ]
            self.__songs_list[group].append(song_result)
            self.__amount_songs += 1
            PR.print_progress(
                    get_l('received_song') + \
                    ' [' + str(self.__amount_songs) + ']: ' + \
                    song_result[0])

    async def __parse_list(self, group, session):
        async with session.get(self.__URL_FANDOM + '?page=' + group[0], params={'action' : 'parse', 'format' : 'json'}) as resp:
            result = await resp.json()
        result = bs(result['parse']['text']['*'], 'html.parser').find_all('div', attrs={'class' : group[1]})
        self.__songs_list[group[0].replace('_', ' ')] = []
        tasks = []
        for i in result:
            for a in i.find_all('a'):
                try:
                    if 'wiki' in a.attrs['href']:
                        tasks.append(loop.create_task(self.__parse_song(a.attrs['href'][6:], group[0].replace('_', ' '), session)))
                except KeyError:
                    pass
        await asyncio.wait(tasks)

    async def __download_song(self, song_info, group: str, session):
        song_path = os.path.join('Songs', group, song_info[0])
        try:
            with open(song_path, 'wb') as f:
                async with session.get(song_info[1]) as resp:
                    async for chunk in resp.content.iter_chunked(self.CHUNK_SIZE):
                        f.write(chunk)
                        f.flush()
            self.__amount_songs_downloaded += 1
        except Exception as e:
            PR.print_last_progress(get_l('error_while_download') + ' ' + song_info[0] + ': ' + str(e))
            self.__amount_error_songs += 1
            self.__amount_songs -= 1
        error_text = ''
        if self.__amount_error_songs:
            error_text = ' E:' + str(self.__amount_error_songs)
        PR.print_progress(
                    get_l('downloaded_song') + \
                    ' [' + str(self.__amount_songs_downloaded) + '/' + str(self.__amount_songs) + \
                    error_text + ']: ' + song_info[0]
        )

    # Updates songs database
    async def update_songs_list(self):
        self.__songs_list = {}
        self.__amount_songs = 0
        print(get_l('updating_songs'))
        async with aiohttp.ClientSession() as session:
            await asyncio.wait([loop.create_task(self.__parse_list(group, session)) for group in self.__URL_GROUPS])
        PR.print_last_progress(get_l('update_completed') + ' ' + str(self.__amount_songs))
        print(get_l('writing_to_file'))
        json.dump(self.__songs_list, open(self.LL_FILE, 'w'), indent=4)
        return self.__songs_list

    # Downloads songs
    async def download_songs(self, groups: iter = None, parallel=20):
        self.__amount_songs_downloaded = 0
        self.__amount_error_songs = 0
        if not self.__songs_list:
            print(get_l('no_database'))
            await self.update_songs_list()
        print(get_l('download_started'))
        try:
            os.mkdir('Songs')
        except FileExistsError:
            pass
        if not groups:
            groups = self.__songs_list.keys()
        self.__amount_songs = 0
        already_downloaded = 0
        uniq_res = {}
        uniq_links = set()
        for group in groups:                   # It's check duplicate files.
            uniq_res[group] = []               # You can improve this by changing the algorithm or database structure
            for i in self.__songs_list[group]: # and then send the Pull Request.
                is_uniq = True
                if i[1] in uniq_links:
                    is_uniq = False
                else:
                    uniq_links.add(i[1])
                    for v in self.__songs_list:
                        if os.path.exists(os.path.join('Songs', v, i[0])):
                            already_downloaded += 1
                            is_uniq = False
                            break
                if is_uniq:
                    uniq_res[group].append(i)
                    self.__amount_songs += 1
        async with aiohttp.ClientSession() as session:
            for group in uniq_res:
                if not uniq_res[group]:
                    continue
                try:
                    os.mkdir(os.path.join('Songs', group))
                except FileExistsError:
                    pass
                for i in range(0, len(uniq_res[group]), parallel):
                    await asyncio.wait([loop.create_task(self.__download_song(song_info, group, session)) for song_info in uniq_res[group][i:i+parallel]])
        PR.print_last_progress(
                get_l('download_completed') + ' ' + str(self.__amount_songs_downloaded) + \
                ', ' + get_l('already_downloaded') + ' ' + str(already_downloaded) + \
                ', ' + get_l('failed_download') + ' ' + str(self.__amount_error_songs)
        )

def get_l(string: str):
    try:
        return local[string][LANG]
    except KeyError:
        return local[string]['en']

def get_consest(string: str, default=True):
    if default:
        answer = input(string + ' [Y/n]: ').lower()
    else:
        answer = input(string + ' [y/N]: ').lower()
    if answer:
        if 'y' in answer:
            return True
        elif 'n' in answer:
            return False
    return default

def choice_options(options: iter, string: str):
    print()
    for idx in range(len(options)):
        print('\t' + str(idx + 1), '-', options[idx])
    answer = input('\n' + string + ' (' + get_l('default') + ' ' + get_l('all') + '): ')
    if not answer or not answer.isdigit():
        return options
    res = set()
    for i in answer:
        try:
            res.add(options[int(i) - 1])
        except:
            pass
    if not res:
        return options
    return tuple(res)

async def main():
    LL = LLSongs()
    DEFAULT_PARALLEL = 5
    if get_consest(get_l('q_update')):
        songs_list = await LL.update_songs_list()
    else:
        songs_list = LL.load_songs_list()
    if not songs_list:
        print(get_l('no_database'))
        songs_list = await LL.update_songs_list()
    groups = choice_options(sorted(list(songs_list.keys())), get_l('choose_groups'))
    while True:
        parallel = input(get_l('choose_parallel') + ' (' + get_l('default') + ' ' + str(DEFAULT_PARALLEL) + ' - ' + get_l('not_recommend_parallel').upper() + '): ')
        if not parallel:
            parallel = DEFAULT_PARALLEL
            break
        if re.fullmatch(r'^[1-9](?:\d+)?$', parallel):
            parallel = int(parallel)
            break
    await LL.download_songs(groups, parallel)

async def close():
    for task in asyncio.tasks.all_tasks(loop):
        if task is not asyncio.tasks.current_task(loop):
            task.cancel()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    try:
        sys.exit(loop.run_until_complete(main()))
    except KeyboardInterrupt:
        loop.run_until_complete(close())
        print('\n' + get_l('interrupt'))
        sys.exit(1)

