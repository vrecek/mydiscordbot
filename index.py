import discord
import os
import random
import signal
import re
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
        intents.voice_states = True

        super().__init__(intents=intents)

        self.music_list:  dict  = {}
        self.music_paths: dict  = {}
        self.music_dir:   str   = music_dir

        self.file_dir:    str   = file_dir
        self.file_paths:  list  = {}
        self.file_list:   dict  = {}
        self.file_buff:   dict  = {}
        self.file_buff_s: int   = 5

        self.nsfw_dirs:   list  = ['nsfw']

        self.pic_exts:    tuple = ('.png', '.jpg', '.jpeg')
        self.vid_exts:    tuple = ('.mp4')

        self.stopped:     bool  = True
        self.music_curr:  Optional[str] = None

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
                    track_title: str = track[:-4]

                    self.music_list[artist][album].append(track_title)
                    self.music_paths[track_title] = f'{music_dir}/{artist}/{album}/{track}'


    # Cleaners
    
    def _file_random_filter_ext(self, arr: list, exts: tuple) -> list:
        return [x for x in arr if os.path.splitext(x)[1] in exts]
    
    # # # # #


    # Options

    # now
    async def getCurrentSongInfo(self, res: Optional[any] = None) -> Optional[list]:
        if not self.music_curr:
            if res:
                await self.say(res, 'Im not playing any music right now')
                return
            else: return [None, None, None]

        s: list = self.music_curr.split('/')[1:]

        artist, album, track = [' '.join(re.findall('[a-zA-Z][^A-Z]*', x)) for x in s]

        track = track[track.find('_') + 1:]
        track = track.replace('.mp3', '').replace('_', ' ')
        track = f'{track[0].upper()}{track[1:]}'

        if res:
            await self.say(res, f'Currently playing: \n\nArtist: {artist}\nAlbum: {album}\nTrack: {track}')
        else: return [artist, album, track]

    # # # # #

    def determineSpoilerFileName(self, filepath: str) -> str:
        fname:  str = os.path.basename(filepath)
        isNsfw: bool = any([f'/{x}/' in filepath for x in self.nsfw_dirs])

        return f'SPOILER_{fname}' if isNsfw else fname
    
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

            randomFrom = self.music_paths[random.choice(artistTracks)]

        else:
            randomFrom = random.choice(list( self.music_paths.values() ))


        return randomFrom

    def auto_play(self, res, vc, artist: str = None, album: str = None) -> None:
        next_track: str = self.getRandomSong(artist, album)

        if not self.stopped and not vc.is_playing():
            self.music_curr = next_track

            vc.play(
                discord.FFmpegPCMAudio(source=next_track), 
                after=lambda _: self.auto_play(res, vc, artist, album)
            )

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

                $file <file> -> sends the specified file
                $file <img|vid|list> <memes|nsfw> -> sends a random file

                $now -> displays information about the current song

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
                    vid:   list = [x for x in files if os.path.splitext(x)[1] in self.vid_exts]
                    pic:   list = [x for x in files if os.path.splitext(x)[1] in self.pic_exts]

                    await self.say(res, f'-IMAGES-\n{'\n'.join(pic)}\n\n-VIDEOS-\n{'\n'.join(vid)}')
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
                    random_item:   str  = random.choice(filtered_buff)

                    if len(buff_list) >= self.file_buff_s:
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

            # List tracks
            case 'tracks':
                if not MSG_ARG1 or MSG_ARG1 not in self.music_list:
                    await self.say(res, f'Available artists: \n-{'\n-'.join(list(self.music_list.keys()))}')
                
                elif not MSG_ARG2 or MSG_ARG2 not in self.music_list[MSG_ARG1]:
                    await self.say(res, f'Available {MSG_ARG1} albums: \n-{'\n-'.join(self.music_list[MSG_ARG1])}')
                
                else:
                    await self.say(res, f'{MSG_ARG1} - {MSG_ARG2} tracks: \n-{'\n-'.join(self.music_list[MSG_ARG1][MSG_ARG2])}')

            # Play
            case 'play':
                if not MSG_ARG1:
                    await self.say(res, f'{PREFIX}play random\n{PREFIX}play random <artist>\n{PREFIX}play random <artist> <album>\n{PREFIX}play <song>')
                    return

                if not AUTHOR_VOICE:
                    await self.say(res, f'Please connect to the voice channel')
                    return


                vc = BOT_VOICE_CLIENT if BOT_VOICE_CLIENT else await AUTHOR_VOICE.channel.connect()
                if vc.is_playing():
                    self.stopped = True
                    vc.stop()


                if MSG_ARG1 == 'random':
                    try: trackpath: str = self.getRandomSong(MSG_ARG2, MSG_ARG3)
                    except Exception as e:
                        await self.say(res, str(e))
                        return

                    tracktext: str = f'random music\nStarting with:'

                    play_next = lambda: self.auto_play(res, vc, MSG_ARG2, MSG_ARG3)

                else:
                    play_next = lambda: None

                    try: 
                        trackpath: str = self.music_paths[MSG_ARG1]
                        tracktext: str = 'selected song:'
                    except:
                        await self.say(res, f'Track {MSG_ARG1} not found')
                        return


                self.music_curr = trackpath
                self.stopped = False

                artist, album, track = await self.getCurrentSongInfo()
                trackname: str = f'{tracktext} {artist} - {track} ({album})'

                vc.play(
                    discord.FFmpegPCMAudio(source=trackpath), 
                    after=lambda _: play_next()
                )

                await self.say(res, f'Playing {trackname}')

            # Stop
            case 'stop':
                if BOT_VOICE_CLIENT and BOT_VOICE_CLIENT.is_playing():
                    self.stopped    = True
                    self.music_curr = None

                    await self.say(res, 'Stopped music')
                    BOT_VOICE_CLIENT.stop()

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
