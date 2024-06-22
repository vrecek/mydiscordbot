# Basic discord bot
It allows to: <br>
- play music <br>
- send files

# Requirements
- linux file structure paths <br>
- ffmpeg <br>
- pip install -r requirements.txt

# .env
TOKEN="discord bot token" <br>
PREFIX="command prefix"

# Directory structure
### Music
/music/-artist-/-album-/-song-.mp3
### Files
/files/-foldername-/-file-

# Usage
play **song** -> plays specified song <br>
play random -> continously plays random songs <br>
play random **artist** -> continously plays random **artist** songs <br>
play random **artist** -album- -> continously plays random **artist** **album** songs <br> <br>

now -> displays information about the current song <br>
skip **int** -> skips the current song by **int** seconds <br>
volume **0-200** -> changes the volume <br> <br>

file **file** -> sends the specified file <br>
file **img|vid|list** **memes|nsfw** -> sends a random file / lists available files <br> <br>

tracks -> views available artists <br>
tracks **artist** -> views **artist** albums <br>
tracks **artist** **album** -> views **album** tracks <br> <br>

stop -> stops the music <br> 
pause -> pauses the music <br>
resume -> resumes the music