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
        self.file_paths:  list  = []
        self.file_list:   dict  = {}
        self.file_buff:   dict  = {
            "memes": {
                "img": [],
                "vid": []
            },

            "nsfw": {
                "img": [],
                "vid": []
            },
        }
        self.pic_exts:   tuple = ('.png', '.jpg', '.jpeg')

        self.stopped:    bool  = True
        self.music_curr: Optional[str] = None

        # Files
        for dirtype in os.listdir(file_dir):
            self.file_list[dirtype] = []

            for file in os.listdir(f'{file_dir}/{dirtype}'):
                self.file_list[dirtype].append(file)
                self.file_paths.append(f'{file_dir}/{dirtype}/{file}')

        # Music
        for artist in list(filter(lambda x: x != '_ignore', os.listdir(music_dir))):
            self.music_list[artist] = {}

            for album in os.listdir(f'{music_dir}/{artist}'):
                self.music_list[artist][album] = []

                for track in os.listdir(f'{music_dir}/{artist}/{album}'):
                    track_title: str = track[:-4]

                    self.music_list[artist][album].append(track_title)
                    self.music_paths[track_title] = f'{music_dir}/{artist}/{album}/{track}'


    #
    def _file_random_filtered(self, arg: str, ext: tuple, buff: list) -> str:
        return random.choice(
            list(filter(
                lambda x: f'/{arg}/' in x and os.path.splitext(x)[1] in ext and x not in buff,
                self.file_paths
            ))
        )

    def _file_random_ext(self, arg: str) -> tuple:
        return ('.mp4') if arg == 'vid' else self.pic_exts

    def _file_list_ext(self, arr: list) -> list:
        return [
            list(filter(lambda x: os.path.splitext(x)[1] in self.pic_exts, arr)),
            list(filter(lambda x: '.mp4' in x, arr))
        ]

    def _file_specific_file(self, arg: str) -> list:
        return list(filter(lambda x: f'/{arg}' in x, self.file_paths))
    
    def _determineSendFileName(self, filepath: str) -> str:
        fname: str = os.path.basename(filepath)

        return f'SPOILER_{fname}' if 'nsfw' in filepath else fname
    #


    def auto_play(self, res, vc) -> None:
        next_track: str = random.choice(list(self.music_paths.values()))

        if not self.stopped and not vc.is_playing():
            self.music_curr = next_track

            vc.play(
                discord.FFmpegPCMAudio(source=next_track), 
                after=lambda _: self.auto_play(res, vc)
            )


    async def set_bot_avatar(self, picture: str) -> None:
        with open(picture, "rb") as file:
            await self.user.edit(avatar=file.read())


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

                $file <file> -> sends the specified file
                $file <img|vid|list> <memes|nsfw> -> sends a random file

                $now -> displays information about current song

                $tracks -> views available artists
                $tracks <artist> -> views artists' albums
                $tracks <artist> <album> -> views albums' tracks

                $stop -> stops the music
                $pause -> pauses the music
                $resume -> resumes the music
                ''')

            # Send a file
            case 'file':
                try: 
                    isAnExtension: bool = MSG_ARG1.endswith(('.mp4', *self.pic_exts))

                    if MSG_ARG2 not in ['memes', 'nsfw'] and not isAnExtension: 
                        raise Exception
                except:
                    await self.say(res, f'{PREFIX}file <img|vid|list> <memes|nsfw>\n{PREFIX}file <file>')
                    return
                

                # Get the list of all files
                if MSG_ARG1 == 'list':
                    pic, vid = self._file_list_ext(self.file_list[MSG_ARG2])

                    await self.say(res, f'-Images-\n{'\n'.join(pic)}\n\n-Videos-\n{'\n'.join(vid)}')
                    return


                # Send a specific file
                if isAnExtension:
                    try: file: str = self._file_specific_file(MSG_ARG1)[0]
                    except:
                        await self.say(res, 'File does not exist')
                        return

                    fname: str = self._determineSendFileName(file)

                    await res.channel.send(file=discord.File(file, fname)) 
                    return


                # Random file
                if MSG_ARG1 in ['img', 'vid']:
                    ext:  tuple = self._file_random_ext(MSG_ARG1)
                    buff: list  = self.file_buff[MSG_ARG2][MSG_ARG1]
                    file: list  = self._file_random_filtered(MSG_ARG2, ext, buff)
                    fname: str = self._determineSendFileName(file)

                    if len(buff) > 4:
                        buff.pop(0)

                    buff.append(file)

                    self.file_buff[MSG_ARG2][MSG_ARG1] = buff

                    await res.channel.send(file=discord.File(file, fname))
                    return
                

                await self.say(res, f'{PREFIX}file <img|vid|list> <memes|nsfw>\n{PREFIX}file <file>')

            # Now
            case 'now':
                if not self.music_curr:
                    await self.say(res, 'Im not playing any music right now')
                    return

                s: list = self.music_curr.split('/')[1:]

                artist, album, track = [' '.join(re.findall('[a-zA-Z][^A-Z]*', x)) for x in s]

                track = track[track.find('_') + 1:]
                track = track.replace('.mp3', '').replace('_', ' ')
                track = f'{track[0].upper()}{track[1:]}'

                await self.say(res, f'Currently playing: \n\nArtist: {artist}\nAlbum: {album}\nTrack: {track}')

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
                    await self.say(res, f'{PREFIX}play random\n{PREFIX}play X')
                    return


                if MSG_ARG1 == 'random':
                    trackpath: str = random.choice(list(self.music_paths.values()))
                    trackname: str = 'random music'

                else:
                    play_next = lambda: None

                    try: 
                        trackpath: str = self.music_paths[MSG_ARG1]
                        trackname: str = MSG_ARG1
                    except:
                        await self.say(res, f'Track {MSG_ARG1} not found')
                        return


                if not AUTHOR_VOICE:
                    await self.say(res, f'No voice channel')
                    return


                vc = BOT_VOICE_CLIENT if BOT_VOICE_CLIENT else await AUTHOR_VOICE.channel.connect()

                if vc.is_playing():
                    self.stopped = True
                    vc.stop()

                if 'play_next' not in locals():
                    play_next = lambda: self.auto_play(res, vc)

                self.music_curr = trackpath
                self.stopped = False

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
