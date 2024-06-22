import discord
import os
import random
import signal
import re
import subprocess
import threading
import ffmpeg
import json
from dotenv import load_dotenv
from typing import Optional
from itertools import chain


load_dotenv('.env')
signal.signal(signal.SIGINT, lambda x,y: exit(0))


TOKEN:     str = os.getenv('TOKEN')
PREFIX:    str = os.getenv('PREFIX')
MUSIC_DIR: str = 'music'
FILE_DIR:  str = 'files'


class DClient(discord.Client):
    def __init__(self, music_dir: str, file_dir: str):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states    = True

        super().__init__(intents=intents)

        self.file_list:      dict  = {}
        self.file_paths:     list  = {}
        self.file_dir:       str   = file_dir
        self.file_buff:      dict  = {}
        self.file_buff_size: int   = 5

        self.music_list:  dict  = {}
        self.music_paths: dict  = {}
        self.music_dir:   str   = music_dir
        self.music_curr:  Optional[dict] = None

        self.time_thread: any   = None
        self.lock_thread: any   = None

        self.nsfw_dirs:   list  = ['nsfw']
        self.pic_exts:    tuple = ('.png', '.jpg', '.jpeg')
        self.vid_exts:    tuple = ('.mp4')
        self.lock:        bool  = False
        self.stopped:     bool  = True
        self.volume:      float = 1.0

        # Files
        for dirtype in os.listdir(file_dir):
            self.file_list[dirtype] = []
            self.file_buff[dirtype] = {"img": [], "vid": []}

            for file in os.listdir(f'{file_dir}/{dirtype}'):
                self.file_list[dirtype].append(file)
                self.file_paths[file] = f'{file_dir}/{dirtype}/{file}'

        # Music
        for artist in list(filter(lambda x: x != '_ignore', os.listdir(music_dir))):
            self.music_list[artist] = {}

            for album in os.listdir(f'{music_dir}/{artist}'):
                self.music_list[artist][album] = []

                for track in os.listdir(f'{music_dir}/{artist}/{album}'):
                    # Assume .mp3 (4 characters)
                    track_title: str = track[:-4]

                    self.music_list[artist][album].append(track_title)
                    self.music_paths[track_title] = f'{music_dir}/{artist}/{album}/{track}'


    # Cleaners
    
    def _file_random_filter_ext(self, arr: list, exts: tuple) -> list:
        return [x for x in arr if os.path.splitext(x)[1] in exts]

    def _countTimeLoop(self, vc) -> None:
        if self.time_thread:
            self.time_thread.cancel()
            self.time_thread = None

        def fn() -> None:
            if vc.is_playing():
                self.music_curr['curr_duration'] += 1

            self.time_thread = threading.Timer(1.0, fn)
            self.time_thread.start()

        fn()

    def _random_after(self, res, vc, MSG_ARG2, MSG_ARG3) -> None:
        if self.lock: return
        self.auto_play(res, vc, MSG_ARG2, MSG_ARG3)

    def _specific_after(self, vc) -> None:
        if self.lock: return
        self.stopCurrentSong(vc)

    def unlockFn(self) -> None:
        self.lock = False
        
    # # # # #


    # Options

    # now
    async def getCurrentSongInfo(self, res: Optional[any] = None) -> Optional[list]:
        current: Optional[dict] = self.music_curr

        if not current:
            if res:
                await self.say(res, 'Im not playing any music right now')
                return
            else: return [None, None, None]


        splitted:       list = current['relpath'].split('/')[1:]
        total_duration: int  = current['total_duration']

        artist, album, track = [' '.join(re.findall('[a-zA-Z][^A-Z]*', x)) for x in splitted]

        track = track[track.find('_') + 1:]
        track = track.replace('.mp3', '').replace('_', ' ')
        track = f'{track[0].upper()}{track[1:]}'


        if res:
            time: str = f'{self.secondsToTime(current['curr_duration'])}/{self.secondsToTime(total_duration)}'

            await self.say(res, f'Currently playing: \n\nArtist: {artist}\nAlbum: {album}\nTrack: {track}\nDuration: {time}\nVolume: {int(self.volume * 100)}%')
        else: return [artist, album, track, total_duration]

    # # # # #

    def determineSpoilerFileName(self, filepath: str) -> str:
        fname:  str = os.path.basename(filepath)
        isNsfw: bool = any([f'/{x}/' in filepath for x in self.nsfw_dirs])

        return f'SPOILER_{fname}' if isNsfw else fname
    
    def secondsToTime(self, secs: int) -> str:
        m, s = divmod(secs, 60)

        return f'{ f"0{m}"[-2:] }:{ f"0{s}"[-2:] }'

    def stopCurrentSong(self, vc) -> None:
        vc.stop()

        if self.time_thread:
            self.time_thread.cancel()

        self.time_thread = None
        self.music_curr  = None
        self.stopped     = True

    def getRandomItem(self, arr: list) -> any:
        return arr[random.SystemRandom().randint(0, len(arr) - 1)]

    def getRandomSong(self, artist: str = None, album: str = None) -> str:
        if (
            (artist and artist not in self.music_list) or 
            (album and album not in self.music_list[artist])
        ):
            raise Exception('Artist and/or Album does not exist')

        if artist in self.music_list:
            artistTracks: list = self.music_list[artist]

            if album in artistTracks:
                artistTracks = artistTracks[album]
            else:
                artistTracks = list( chain.from_iterable(artistTracks.values()) )

            randomFrom: str = self.music_paths[self.getRandomItem(artistTracks)]

        else:
            randomFrom: str = self.getRandomItem( list(self.music_paths.values()) )

        return randomFrom

    def setTrack(self, trackpath: str, after_fn: callable) -> None:
        abspath:  str = f'{os.getcwd()}/{trackpath}'
        duration: str = ffmpeg.probe(abspath)['format']['duration']
        
        self.music_curr = {
            "relpath": trackpath,
            "abspath": abspath,
            "total_duration": int(float(duration)),
            "curr_duration": 0,
            "after_fn": after_fn
        }

    def auto_play(self, res, vc, artist: str = None, album: str = None) -> None:
        if not self.stopped and not vc.is_playing():
            next_track: str      = self.getRandomSong(artist, album)
            play_next:  callable = lambda _: self.auto_play(res, vc, artist, album)

            self.setTrack(next_track, play_next)
            self.play(vc)

    def play(self, vc, skipBy: Optional[int] = None) -> None:
        if vc.is_playing(): vc.stop()

        opt: dict = {'options': f'-af volume={self.volume}'}
        if skipBy:
            opt['before_options'] = f'-ss {skipBy}'

        self.stopped = False
        self._countTimeLoop(vc)

        vc.play(
            discord.FFmpegPCMAudio(self.music_curr['relpath'], **opt), 
            after=self.music_curr['after_fn']
        )

        threading.Timer(2.0, self.unlockFn).start()

    def returnInRows(self, arr: list, perRow: int, rowSpace: int, separator: str) -> str:
        out: str = ''

        for i,x in enumerate(arr):
            if int(i) % perRow == 0:
                out += '\n'

            out += f'{separator}{x}{' ' * rowSpace}'

        return out

    async def set_bot_avatar(self, picture: str) -> None:
        with open(picture, "rb") as file:
            await self.user.edit(avatar=file.read())
            print('Bot avatar changed')

    async def say(self, res, msg: str) -> None:
        await res.channel.send(f'** @{res.author.name}\n\n{msg} **')


    async def on_ready(self) -> None:
        print(f'\n===Ready in {client.guilds[0]}===')


    async def on_message(self, res) -> None:
        if not res.content:
            return

        MSG_PREFIX:  str  = res.content[0]
        MSG_AUTHOR:  str  = res.author.name
        AUTHOR_VOICE      = res.author.voice
        BOT_VOICE_CLIENT  = res.guild.voice_client

        splitted: list = res.content[1:].split(' ')
        splitted.extend([None, None, None])

        MSG_TEXT, MSG_ARG1, MSG_ARG2, MSG_ARG3, *_ = splitted

        if MSG_PREFIX != PREFIX: return

        
        match MSG_TEXT:
            # List available commands
            case 'help':
                await self.say(res, 
                '''
                $play <song> -> plays specified song
                $play random -> continously plays random songs
                $play random <artist> -> continously plays random <artist> songs
                $play random <artist> <album> -> continously plays random <artist> <album> songs

                $now -> displays information about the current song
                $skip <int> -> skips the current song by <int> seconds
                $volume <0-200> -> changes the volume

                $file <file> -> sends the specified file
                $file <img|vid|list> <memes|nsfw> -> sends a random file / lists available files

                $tracks -> views available artists
                $tracks <artist> -> views <artist> albums
                $tracks <artist> <album> -> views <album> tracks

                $stop -> stops the music
                $pause -> pauses the music
                $resume -> resumes the music
                ''')

            # Send a file
            case 'file':
                dirnames: list = self.file_list.keys()

                # List all files
                if MSG_ARG1 == 'list' and MSG_ARG2 in dirnames:
                    files: list = self.file_list[MSG_ARG2]

                    vid:   list = self._file_random_filter_ext(files, self.vid_exts)
                    vid = self.returnInRows(vid, 5, 2, '-')

                    pic:   list = self._file_random_filter_ext(files, self.pic_exts)
                    pic = self.returnInRows(pic, 5, 2, '-')

                    await self.say(res, f'Images:\n{pic}\n\nVideos:\n{vid}')
                    return


                filepath: Optional[str] = None

                # Send the specific file
                if MSG_ARG1 in self.file_paths and MSG_ARG1.endswith((*self.vid_exts, *self.pic_exts)):
                    filepath = self.file_paths[MSG_ARG1]

                # Send a random file
                if MSG_ARG1 in ['img', 'vid'] and MSG_ARG2 in dirnames:
                    files: list = self.file_list[MSG_ARG2]
                    
                    if MSG_ARG1 == 'img':
                        selected: list = self._file_random_filter_ext(files, self.pic_exts)
                    else:
                        selected: list = self._file_random_filter_ext(files, self.vid_exts)

                    buff_list:     list = self.file_buff[MSG_ARG2][MSG_ARG1]
                    filtered_buff: list = [x for x in selected if x not in buff_list]
                    random_item:   str  = self.getRandomItem(filtered_buff)

                    if len(buff_list) >= self.file_buff_size:
                        self.file_buff[MSG_ARG2][MSG_ARG1].pop(0)    

                    self.file_buff[MSG_ARG2][MSG_ARG1].append(random_item)

                    filepath = self.file_paths[random_item]


                if not filepath:
                    keys: str = ' | '.join(self.file_list.keys())

                    await self.say(res, f'Requested file does not exist\n\n{PREFIX}file <img | vid | list> <{keys}>\n{PREFIX}file <file>')
                    return


                filename: str = self.determineSpoilerFileName(filepath)
                await res.channel.send(file=discord.File(filepath, filename))

            # Now
            case 'now':
                await self.getCurrentSongInfo(res)

            # Volume
            case 'volume':
                if self.lock: return

                try: 
                    volume: float = int(MSG_ARG1) / 100

                    if volume > 2 or volume < 0: raise Exception()
                except:
                    await self.say(res, 'Please specify % value (0-200)')
                    return

                self.volume = volume

                duration: int = self.music_curr['curr_duration'] - 1

                if self.music_curr and (self.music_curr['total_duration'] - duration) <= 10:
                    await self.say(res, 'Volume will be changed on the next song')
                    return 

                self.lock = True
                self.play(BOT_VOICE_CLIENT, duration)

            # List tracks
            case 'tracks':
                ls:        str = ''
                msg:       str = ''
                separator: str = '-'

                if not MSG_ARG1 or MSG_ARG1 not in self.music_list:
                    ls  = self.returnInRows(self.music_list.keys(), 3, 2, separator)
                    msg = f'Available artists:\n{ls}'
                
                elif not MSG_ARG2 or MSG_ARG2 not in self.music_list[MSG_ARG1]:
                    ls  = self.returnInRows(self.music_list[MSG_ARG1], 2, 2, separator)
                    msg = f'Available {MSG_ARG1} albums:\n{ls}'
                
                else:
                    ls  = self.returnInRows(self.music_list[MSG_ARG1][MSG_ARG2], 4, 5, separator)
                    msg = f'{MSG_ARG1} - {MSG_ARG2} tracks:\n{ls}'

                await self.say(res, msg)

            # Skip by seconds
            case 'skip':
                if self.lock: return

                if not BOT_VOICE_CLIENT.is_playing():
                    await self.say(res, 'Im not playing any music right now')
                    return
                if not MSG_ARG1 or not MSG_ARG1.isnumeric():
                    await self.say(res, 'Please specify seconds')
                    return

                new_duration: int = self.music_curr['curr_duration'] + int(MSG_ARG1)

                if new_duration >= self.music_curr['total_duration']:
                    await self.say(res, 'Too many seconds to skip')
                    return

                self.lock = True
                self.music_curr['curr_duration'] = new_duration

                self.play(BOT_VOICE_CLIENT, new_duration)

            # Play
            case 'play':
                if self.lock: return

                if not MSG_ARG1:
                    await self.say(res, f'{PREFIX}play random\n{PREFIX}play random <artist>\n{PREFIX}play random <artist> <album>\n{PREFIX}play <song>')
                    return

                if not AUTHOR_VOICE:
                    await self.say(res, f'Please connect to the voice channel')
                    return

                vc = BOT_VOICE_CLIENT if BOT_VOICE_CLIENT else await AUTHOR_VOICE.channel.connect()

                if MSG_ARG1 == 'random':
                    try: trackpath: str = self.getRandomSong(MSG_ARG2, MSG_ARG3)
                    except Exception as e:
                        await self.say(res, str(e))
                        return

                    tracktext: str      = f'random music\nStarting with:'
                    play_next: callable = lambda _: self._random_after(res, vc, MSG_ARG2, MSG_ARG3)

                else:
                    play_next: callable = lambda _: self._specific_after(vc)

                    try: 
                        trackpath: str = self.music_paths[MSG_ARG1]
                        tracktext: str = 'selected song:'
                    except:
                        await self.say(res, f'Track {MSG_ARG1} not found')
                        return


                self.setTrack(trackpath, play_next)

                artist, album, track, duration = await self.getCurrentSongInfo()
                trackname: str = f'{tracktext} {artist} - {track} ({album}) [{self.secondsToTime(duration)}]'

                self.lock = True
                self.play(vc)

                await self.say(res, f'Playing {trackname}')

            # Stop
            case 'stop':
                if BOT_VOICE_CLIENT and BOT_VOICE_CLIENT.is_playing():
                    self.stopCurrentSong(BOT_VOICE_CLIENT)

                    await self.say(res, 'Stopped music')
                    return

                await self.say(res, 'Im not playing any music right now')

            # Pause
            case 'pause':
                if BOT_VOICE_CLIENT and BOT_VOICE_CLIENT.is_playing():
                    await self.say(res, 'Paused music')
                    BOT_VOICE_CLIENT.pause()

                    return

                await self.say(res, 'Im not playing any music right now')

            # Resume
            case 'resume':
                if not BOT_VOICE_CLIENT:
                    await self.say(res, 'Im not connected')
                    return

                if BOT_VOICE_CLIENT.is_playing():
                    await self.say(res, 'Im playing the music right now')
                    return

                if not self.music_curr:
                    await self.say(res, 'Im not playing any music right now')
                    return

                await self.say(res, 'Resumed music')
                BOT_VOICE_CLIENT.resume()



client = DClient(MUSIC_DIR, FILE_DIR)
# client.set_bot_avatar('botavatar.jpg')

client.run(TOKEN)