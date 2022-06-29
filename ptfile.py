import os
import io
import json
import time
import struct
import hashlib

from os import PathLike
from enum import IntEnum
from typing import List

from unpackme import UnpackMeClientLoginInfo, UnpackMeClient


class CachedPTFileDecryptor:

    UNPACK_CACHE_DIR = "unpack-cache"
    TOKEN_FILENAME = os.path.join(UNPACK_CACHE_DIR, "token.json")

    @classmethod
    def set_cache_dir(cls, cache_dir):
        cls.UNPACK_CACHE_DIR = cache_dir
        cls.TOKEN_FILENAME = os.path.join(cls.UNPACK_CACHE_DIR, "token.json")

    def __init__(
        self,
        login_info=None,
        token_filename=None,
        decrypted_cache_dir=None,
    ):
        if login_info is None:
            login_info = UnpackMeClientLoginInfo()

        if token_filename is None:
            token_filename = self.TOKEN_FILENAME
        if decrypted_cache_dir is None:
            decrypted_cache_dir = self.UNPACK_CACHE_DIR

        self._login_info = login_info
        self._token_filename = token_filename
        self._decrypted_cache_dir = decrypted_cache_dir

        self._unpackme_client = UnpackMeClient(self._login_info)

        self._token = None
        self._commands = None
        self._command_ids_by_title = None

    def set_token(self, token):
        self._token = token
        self._unpackme_client.set_token(token)

    def get_token(self):
        return self._token

    def get_or_fetch_token(self, cached=True):
        if cached and os.path.exists(self._token_filename):
            with open(self._token_filename, "r", encoding="utf-8") as f:
                token_body = json.load(f)
            token = token_body["token"]
        else:
            token_body = self._unpackme_client.authenticate()
            token_dir = os.path.dirname(self._token_filename)
            if not os.path.exists(token_dir):
                os.makedirs(token_dir, exist_ok=True)
            with open(self._token_filename, "w", encoding="utf-8") as f:
                json.dump(token_body, f)
            token = token_body["token"]
        return token

    def ensure_token_is_set(self):
        if self._token is None:
            token = self.get_or_fetch_token()
            self.set_token(token)

    def get_command_id_by_title(self, command_title):
        if self._command_ids_by_title is None:
            self.ensure_token_is_set()
            response_body = self._unpackme_client.get_available_commands()
            self._commands = response_body
            self._command_ids_by_title = {
                item["commandTitle"]: item["commandId"] for item in self._commands
            }
        return self._command_ids_by_title[command_title]

    def create_decrypt_task_and_download(self, file):
        self.ensure_token_is_set()
        command_id = self.get_command_id_by_title("DJMax *.pt decrypt")
        task_created = self._unpackme_client.create_task_from_command_id(
            command_id, file
        )
        task_id = task_created["taskId"]
        completed = False
        while not completed:
            task_checked = self._unpackme_client.get_task_by_id(task_id)
            task_status = task_checked["taskStatus"]
            completed = task_status == "completed"
            if not completed:
                time.sleep(500 / 1000)
        response = self._unpackme_client.download_task(task_id)
        return response

    def buffer_from_file(self, file):
        if isinstance(file, bytes):
            buffer = file
        elif isinstance(file, str) or isinstance(file, PathLike):
            with open(file, "rb") as f:
                buffer = f.read()
        elif isinstance(file, io.RawIOBase):
            buffer = file.read()
        else:
            raise TypeError()
        return buffer

    def decrypt_ptfile(self, file, cached=True):
        file_buffer = self.buffer_from_file(file)
        md5hash = hashlib.md5(file_buffer)
        md5hash_hex = md5hash.hexdigest()
        cached_filename = os.path.join(
            self._decrypted_cache_dir, "{}.pt".format(md5hash_hex[:7])
        )
        if cached and os.path.exists(cached_filename):
            with open(cached_filename, "rb") as f:
                decrypted_file_content = f.read()
        else:
            response = self.create_decrypt_task_and_download(file)
            decrypted_file_content = response.content
            if not os.path.exists(self._decrypted_cache_dir):
                os.makedirs(self._decrypted_cache_dir, exist_ok=True)
            with open(cached_filename, "wb") as f:
                f.write(decrypted_file_content)
        return decrypted_file_content


class SequentialUnpacker:
    def __init__(self, file):
        if isinstance(file, bytes):
            buffer = file
        elif isinstance(file, str) or isinstance(file, PathLike):
            with open(file, "rb") as f:
                buffer = f.read()
        elif isinstance(file, io.RawIOBase):
            buffer = file.read()
        else:
            raise TypeError()

        self._buffer = buffer
        self._offset = 0

    def start_from(self, offset=0):
        self._offset = offset

    def unpack_from(self, format, offset=None):
        if offset is None:
            offset = self._offset
        else:
            self.start_from(offset)
        result = struct.unpack_from(format, self._buffer, offset)
        read_byte_size = struct.calcsize(format)
        self._offset += read_byte_size
        return result

    def unpack(self, format):
        return self.unpack_from(format)


class PTFileBase:
    def __repr__(self):
        args = ", ".join(
            ["%s=%r" % (name, value) for name, value in self.__dict__.items()]
        )
        return "%s(%s)" % (self.__class__.__name__, args)

    def __iter__(self):
        return iter(self.__dict__.items())

    def __hash__(self):
        return hash(tuple(self))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return tuple(self) == tuple(other)

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return tuple(self) < tuple(other)


class PTFileHeader(PTFileBase):
    def __init__(
        self,
        version_major: int,
        version_minor: int,
        ticks_per_measure: int,
        master_bpm: float,
        number_of_tracks: int,
        total_ticks: int,
        time_in_seconds: int,
        number_of_sounds: int,
    ):
        self.version_major = version_major
        self.version_minor = version_minor
        self.ticks_per_measure = ticks_per_measure
        self.master_bpm = master_bpm
        self.number_of_tracks = number_of_tracks
        self.total_ticks = total_ticks
        self.time_in_seconds = time_in_seconds
        self.number_of_sounds = number_of_sounds


class PTFileSound(PTFileBase):
    def __init__(self, index: int, command: int, filename: str):
        self.index = index
        self.command = command
        self.filename = filename


class PTFileCommandType(IntEnum):

    GENERAL = 1
    VOLUME = 2
    BPM = 3
    BEAT = 4


class PTFileNoteParams:

    pass


class PTFileGeneralNoteParams(PTFileNoteParams, PTFileBase):
    def __init__(
        self,
        sound_index: int,
        volume: int,
        pan: int,
        attribute: int,
        duration: int,
    ):
        self.sound_index = sound_index
        self.volume = volume
        self.pan = pan
        self.attribute = attribute
        self.duration = duration

    def get_command_type(self):
        return PTFileCommandType.GENERAL

    def is_long_note(self):
        return self.duration > 6

    def is_equal(self, other):
        if not isinstance(other, PTFileGeneralNoteParams):
            return False
        return self == other

    def is_equal_except_duration(self, other):
        if not isinstance(other, PTFileGeneralNoteParams):
            return False
        exclude_names = {"duration"}
        self_tuple = tuple(
            (name, value)
            for name, value in self.__dict__.items()
            if name not in exclude_names
        )
        other_tuple = tuple(
            (name, value)
            for name, value in other.__dict__.items()
            if name not in exclude_names
        )
        return self_tuple == other_tuple

    def __lt__(self, other):
        if not isinstance(other, PTFileNoteParams):
            return NotImplemented
        elif isinstance(other, PTFileGeneralNoteParams):
            return tuple(self) < tuple(other)
        else:
            return self.get_command_type() < other.get_command_type()


class PTFileVolumeNoteParams(PTFileNoteParams, PTFileBase):
    def __init__(self, volume: int):
        self.volume = volume

    def get_command_type(self):
        return PTFileCommandType.VOLUME

    def __lt__(self, other):
        if not isinstance(other, PTFileNoteParams):
            return NotImplemented
        elif isinstance(other, PTFileVolumeNoteParams):
            return tuple(self) < tuple(other)
        else:
            return self.get_command_type() < other.get_command_type()


class PTFileBPMChangeNoteParams(PTFileNoteParams, PTFileBase):
    def __init__(self, tempo: float):
        self.tempo = tempo

    def get_command_type(self):
        return PTFileCommandType.BPM

    def __lt__(self, other):
        if not isinstance(other, PTFileNoteParams):
            return NotImplemented
        elif isinstance(other, PTFileBPMChangeNoteParams):
            return tuple(self) < tuple(other)
        else:
            return self.get_command_type() < other.get_command_type()


class PTFileBeatNoteParams(PTFileNoteParams, PTFileBase):
    def __init__(self, beat: int):
        self.beat = beat

    def get_command_type(self):
        return PTFileCommandType.BEAT

    def __lt__(self, other):
        if not isinstance(other, PTFileNoteParams):
            return NotImplemented
        elif isinstance(other, PTFileBeatNoteParams):
            return tuple(self) < tuple(other)
        else:
            return self.get_command_type() < other.get_command_type()


class PTFileNote(PTFileBase):
    def __init__(
        self,
        position: int,
        command_type: PTFileCommandType,
        params: PTFileNoteParams,
    ):
        self.position = position
        self.command_type = command_type
        self.params = params

    def is_general(self):
        return self.command_type == PTFileCommandType.GENERAL

    def is_equal(self, other):
        if not isinstance(other, PTFileNote):
            return False
        return self == other

    def is_equal_except_duration(self, other):
        if not isinstance(other, PTFileNote):
            return False
        if not self.is_general() or not other.is_general():
            return False
        exclude_names = {"params"}
        self_tuple = tuple(
            (name, value)
            for name, value in self.__dict__.items()
            if name not in exclude_names
        )
        other_tuple = tuple(
            (name, value)
            for name, value in other.__dict__.items()
            if name not in exclude_names
        )
        return self_tuple == other_tuple and self.params.is_equal_except_duration(
            other.params
        )


class PTFileTrack(PTFileBase):
    def __init__(self, name: str, ticks: int, notes: List[PTFileNote]):
        self.name = name
        self.ticks = ticks
        self.notes = notes


class PTFile(PTFileBase):

    CACHED_PTFILE_DECRYPTOR = CachedPTFileDecryptor()

    def __init__(
        self,
        header: PTFileHeader,
        sounds: List[PTFileSound],
        tracks: List[PTFileTrack],
    ):
        self.header = header
        self.sounds = sounds
        self.tracks = tracks

    @classmethod
    def parse(cls, file):
        if isinstance(file, bytes):
            buffer = file
        elif isinstance(file, str) or isinstance(file, PathLike):
            with open(file, "rb") as f:
                buffer = f.read()
        elif isinstance(file, io.RawIOBase):
            buffer = file.read()
        else:
            raise TypeError()

        def is_encrypted(buffer):
            offset = 0x18
            (first_song_index,) = struct.unpack_from("<H", buffer, offset)
            return first_song_index != 1

        def decrypt_buffer(buffer):
            return cls.CACHED_PTFILE_DECRYPTOR.decrypt_ptfile(buffer)

        if is_encrypted(buffer):
            buffer = decrypt_buffer(buffer)

        unpacker = SequentialUnpacker(buffer)

        # header
        (
            ptff,
            version_major,
            version_minor,
            ticks_per_measure,
            master_bpm,
            number_of_tracks,
            total_ticks,
            time_in_seconds,
            number_of_sounds,
        ) = unpacker.unpack("<4sBBHfHIfH")

        assert ptff == b"PTFF"

        header = PTFileHeader(
            version_major,
            version_minor,
            ticks_per_measure,
            master_bpm,
            number_of_tracks,
            total_ticks,
            time_in_seconds,
            number_of_sounds,
        )

        # sounds
        sound_entries = []
        for i in range(number_of_sounds):
            (index, command, filename) = unpacker.unpack("<HH64s")
            filename, _, _ = filename.partition(b"\0")
            filename = filename.decode()
            sound_entry = PTFileSound(index, command, filename)
            sound_entries.append(sound_entry)

        # tracks
        track_entries = []
        for i in range(number_of_tracks):
            (eztr, track_name, ticks, size_of_data) = unpacker.unpack("<4sxx64sIIxx")
            assert eztr == b"EZTR"
            track_name, _, _ = track_name.partition(b"\0")
            track_name = track_name.decode()
            size_of_note = 0x10
            number_of_notes = size_of_data // size_of_note
            note_entries = []
            for i in range(number_of_notes):
                position, command_type, params = unpacker.unpack("<IBxxx8s")
                if command_type == PTFileCommandType.GENERAL:
                    (sound_index, volume, pan, attribute, duration) = struct.unpack(
                        "<HBBBHx", params
                    )
                    params = PTFileGeneralNoteParams(
                        sound_index, volume, pan, attribute, duration
                    )
                elif command_type == PTFileCommandType.VOLUME:
                    (volume,) = struct.unpack("<Bxxxxxxx", params)
                    params = PTFileVolumeNoteParams(volume)
                elif command_type == PTFileCommandType.BPM:
                    (tempo,) = struct.unpack("<fxxxx", params)
                    params = PTFileBPMChangeNoteParams(tempo)
                elif command_type == PTFileCommandType.BEAT:
                    (beat,) = struct.unpack("<Hxxxxxx", params)
                    params = PTFileBeatNoteParams(beat)
                else:
                    raise TypeError("Unsupported command type")
                note_entry = PTFileNote(position, command_type, params)
                note_entries.append(note_entry)
            track_entry = PTFileTrack(track_name, ticks, note_entries)
            track_entries.append(track_entry)

        return cls(header, sound_entries, track_entries)
