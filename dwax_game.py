#!/usr/bin/env python

from __future__ import annotations

import os
import asyncio

from os import PathLike
from enum import IntEnum
from pathlib import Path
from typing import List, Optional, Union, Tuple

import click

import pygame
import pygame_gui

from pygame import Rect, Color
from pygame.mixer import Sound, Channel
from pygame.time import Clock

from pygame_gui import UIManager
from pygame_gui.elements.ui_button import UIButton
from pygame_gui.elements.ui_text_box import UITextBox


from ptfile import (
    PTFileSound,
    PTFileCommandType,
    PTFileNote,
    PTFileTrack,
    PTFile,
)

from dwax_ui import FilteredUIFileDialog
from dwax_ui import UpdateableUIDropDownMenu


class GameObjectBase:
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


class GameSoundTable:
    def __init__(
        self,
        sounds: List[PTFileSound],
        sound_file_dir: Optional[Union[str, PathLike]] = None,
    ):
        if sound_file_dir is None:
            sound_file_dir = "."

        self._sounds = sounds
        self._sound_file_dir = Path(sound_file_dir)

        self._sound_by_index = {}
        self._sound_filename_by_index = {}

        for sound in self._sounds:
            sound_filename = self._sound_file_dir / sound.filename
            sound_filename = str(sound_filename)
            sound_object = Sound(sound_filename)
            self._sound_filename_by_index[sound.index] = sound_filename
            self._sound_by_index[sound.index] = sound_object

    def get_sound_filename_by_index(self, index):
        return self._sound_filename_by_index[index]

    def get_sound_by_index(self, index):
        return self._sound_by_index[index]


class GameTrackChannel:
    def __init__(self, channels: List[Channel]):
        self._channels = channels
        self._volume = 1.0
        self._channel_index = 0
        self._channels_len = len(self._channels)

    def set_volume(self, volume: float):
        self._volume = volume

    def find_free_channel(self):
        free_channel = self._channels[self._channel_index]
        self._channel_index += 1
        if self._channel_index >= self._channels_len:
            self._channel_index -= self._channels_len
        return free_channel

    def play_sound(
        self,
        sound: Sound,
        sound_volume: Optional[Union[float, Tuple[float, float]]] = None,
    ):
        channel = self.find_free_channel()
        channel.play(sound)

        if sound_volume is None:
            channel.set_volume(self._volume)
        else:
            if isinstance(sound_volume, tuple):
                channel.set_volume(
                    sound_volume[0] * self._volume,
                    sound_volume[1] * self._volume,
                )
            else:
                channel.set_volume(sound_volume * self._volume)


class GameTrackType(IntEnum):
    NONE = 0
    CMD = 1
    FG1 = 2
    FG2 = 3
    MR = 4
    BG = 5

    @classmethod
    def get_track_type(cls, track_index):
        if 0 <= track_index < 2:
            return cls.CMD
        elif 2 <= track_index < 12:
            return cls.FG1
        elif 12 <= track_index < 22:
            return cls.FG2
        elif 22 <= track_index < 23:
            return cls.MR
        else:
            return cls.BG


class GameTrackButtonType(IntEnum):
    BUTTON1 = 1
    BUTTON2 = 2
    BUTTON3 = 3
    BUTTON4 = 4
    BUTTON5 = 5
    BUTTON6 = 6
    SIDEL = 7
    SIDER = 8
    L1 = 9
    R1 = 10

    @classmethod
    def get_button_type(cls, track_index):
        return cls.BUTTON_TYPE_TO_TRACK_INDEX_MAPPING.get(track_index)

    def get_track_index(self):
        return self.TRACK_INDEX_TO_BUTTON_TYPE_MAPPING.get(self)


GameTrackButtonType.BUTTON_TYPE_TO_TRACK_INDEX_MAPPING = {
    2: GameTrackButtonType.SIDEL,
    3: GameTrackButtonType.BUTTON1,
    4: GameTrackButtonType.BUTTON2,
    5: GameTrackButtonType.BUTTON3,
    6: GameTrackButtonType.BUTTON4,
    7: GameTrackButtonType.BUTTON5,
    8: GameTrackButtonType.BUTTON6,
    9: GameTrackButtonType.SIDER,
    10: GameTrackButtonType.L1,
    11: GameTrackButtonType.R1,
}
GameTrackButtonType.TRACK_INDEX_TO_BUTTON_TYPE_MAPPING = {
    GameTrackButtonType.SIDEL: 2,
    GameTrackButtonType.BUTTON1: 3,
    GameTrackButtonType.BUTTON2: 4,
    GameTrackButtonType.BUTTON3: 5,
    GameTrackButtonType.BUTTON4: 6,
    GameTrackButtonType.BUTTON5: 7,
    GameTrackButtonType.BUTTON6: 8,
    GameTrackButtonType.SIDER: 9,
    GameTrackButtonType.L1: 10,
    GameTrackButtonType.R1: 11,
}


GAME_MODE_FOUR_BUTTONS = [
    GameTrackButtonType.SIDEL,
    GameTrackButtonType.BUTTON1,
    GameTrackButtonType.BUTTON2,
    GameTrackButtonType.BUTTON3,
    GameTrackButtonType.BUTTON4,
    GameTrackButtonType.SIDER,
]
GAME_MODE_FIVE_BUTTONS = [
    GameTrackButtonType.SIDEL,
    GameTrackButtonType.BUTTON1,
    GameTrackButtonType.BUTTON2,
    GameTrackButtonType.BUTTON3,
    GameTrackButtonType.BUTTON4,
    GameTrackButtonType.BUTTON5,
    GameTrackButtonType.SIDER,
]
GAME_MODE_SIX_BUTTONS = [
    GameTrackButtonType.SIDEL,
    GameTrackButtonType.BUTTON1,
    GameTrackButtonType.BUTTON2,
    GameTrackButtonType.BUTTON3,
    GameTrackButtonType.BUTTON4,
    GameTrackButtonType.BUTTON5,
    GameTrackButtonType.BUTTON6,
    GameTrackButtonType.SIDER,
]
GAME_MODE_EIGHT_BUTTONS = [
    GameTrackButtonType.L1,
    GameTrackButtonType.SIDEL,
    GameTrackButtonType.BUTTON1,
    GameTrackButtonType.BUTTON2,
    GameTrackButtonType.BUTTON3,
    GameTrackButtonType.BUTTON4,
    GameTrackButtonType.BUTTON5,
    GameTrackButtonType.BUTTON6,
    GameTrackButtonType.SIDER,
    GameTrackButtonType.R1,
]


BUTTON_COLOR_TRIGGER = Color(230, 0, 100)
BUTTON_COLOR_SIDE = Color(44, 196, 185)
BUTTON_COLOR_MAIN = Color(255, 200, 16)
BUTTON_COLOR_SUB = Color(72, 185, 255)

GAME_MODE_FOUR_BUTTON_COLORS = [
    BUTTON_COLOR_SIDE,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SIDE,
]
GAME_MODE_FIVE_BUTTON_COLORS = [
    BUTTON_COLOR_SIDE,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SIDE,
]
GAME_MODE_SIX_BUTTON_COLORS = [
    BUTTON_COLOR_SIDE,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SIDE,
]
GAME_MODE_EIGHT_BUTTON_COLORS = [
    BUTTON_COLOR_TRIGGER,
    BUTTON_COLOR_SIDE,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SUB,
    BUTTON_COLOR_MAIN,
    BUTTON_COLOR_SIDE,
    BUTTON_COLOR_TRIGGER,
]


GAME_MODE_FOUR_BUTTON_COLUMNS = [(0, 2), 0, 1, 2, 3, (2, 2)]
GAME_MODE_FIVE_BUTTON_COLUMNS = [(0, 2.5), 0, 1, 2, 3, 4, (2.5, 2.5)]
GAME_MODE_SIX_BUTTON_COLUMNS = [(0, 3), 0, 1, 2, 3, 4, 5, (3, 3)]
GAME_MODE_EIGHT_BUTTON_COLUMNS = [(0, 3), (0, 3), 0, 1, 2, 3, 4, 5, (3, 3), (3, 3)]

# pylint: disable=no-member
GAME_MODE_FOUR_BUTTON_MAPPING = {
    pygame.K_LSHIFT: GameTrackButtonType.SIDEL,
    pygame.K_a: GameTrackButtonType.BUTTON1,
    pygame.K_s: GameTrackButtonType.BUTTON2,
    pygame.K_SEMICOLON: GameTrackButtonType.BUTTON3,
    pygame.K_QUOTE: GameTrackButtonType.BUTTON4,
    pygame.K_RSHIFT: GameTrackButtonType.SIDER,
}
GAME_MODE_FIVE_BUTTON_MAPPING = {
    pygame.K_LSHIFT: GameTrackButtonType.SIDEL,
    pygame.K_a: GameTrackButtonType.BUTTON1,
    pygame.K_s: GameTrackButtonType.BUTTON2,
    pygame.K_d: GameTrackButtonType.BUTTON3,
    pygame.K_l: GameTrackButtonType.BUTTON3,
    pygame.K_SEMICOLON: GameTrackButtonType.BUTTON4,
    pygame.K_QUOTE: GameTrackButtonType.BUTTON5,
    pygame.K_RSHIFT: GameTrackButtonType.SIDER,
}
GAME_MODE_SIX_BUTTON_MAPPING = {
    pygame.K_LSHIFT: GameTrackButtonType.SIDEL,
    pygame.K_a: GameTrackButtonType.BUTTON1,
    pygame.K_s: GameTrackButtonType.BUTTON2,
    pygame.K_d: GameTrackButtonType.BUTTON3,
    pygame.K_l: GameTrackButtonType.BUTTON4,
    pygame.K_SEMICOLON: GameTrackButtonType.BUTTON5,
    pygame.K_QUOTE: GameTrackButtonType.BUTTON6,
    pygame.K_RSHIFT: GameTrackButtonType.SIDER,
}
GAME_MODE_EIGHT_BUTTON_MAPPING = {
    pygame.K_SPACE: GameTrackButtonType.L1,
    pygame.K_CAPSLOCK: GameTrackButtonType.SIDEL,
    pygame.K_q: GameTrackButtonType.BUTTON1,
    pygame.K_w: GameTrackButtonType.BUTTON2,
    pygame.K_e: GameTrackButtonType.BUTTON3,
    pygame.K_KP7: GameTrackButtonType.BUTTON4,
    pygame.K_KP8: GameTrackButtonType.BUTTON5,
    pygame.K_KP9: GameTrackButtonType.BUTTON6,
    pygame.K_KP_PLUS: GameTrackButtonType.SIDER,
    pygame.K_KP0: GameTrackButtonType.R1,
}

GAME_MODE_FOUR_BUTTONS_TO_MAP = list(GAME_MODE_FOUR_BUTTON_MAPPING.values())
GAME_MODE_FIVE_BUTTONS_TO_MAP = list(GAME_MODE_FIVE_BUTTON_MAPPING.values())
GAME_MODE_SIX_BUTTONS_TO_MAP = list(GAME_MODE_SIX_BUTTON_MAPPING.values())
GAME_MODE_EIGHT_BUTTONS_TO_MAP = list(GAME_MODE_EIGHT_BUTTON_MAPPING.values())


class GameMode(IntEnum):
    FOUR = 4
    FIVE = 5
    SIX = 6
    EIGHT = 8

    def get_total_buttons(self):
        return int(self) + 2

    def get_total_columns(self):
        return min(int(self), 6)

    def get_button_types(self):
        if self == self.FOUR:
            return GAME_MODE_FOUR_BUTTONS
        if self == self.FIVE:
            return GAME_MODE_FIVE_BUTTONS
        if self == self.SIX:
            return GAME_MODE_SIX_BUTTONS
        if self == self.EIGHT:
            return GAME_MODE_EIGHT_BUTTONS

    def get_button_colors(self):
        if self == self.FOUR:
            return GAME_MODE_FOUR_BUTTON_COLORS
        if self == self.FIVE:
            return GAME_MODE_FIVE_BUTTON_COLORS
        if self == self.SIX:
            return GAME_MODE_SIX_BUTTON_COLORS
        if self == self.EIGHT:
            return GAME_MODE_EIGHT_BUTTON_COLORS

    def get_button_columns(self):
        if self == self.FOUR:
            return GAME_MODE_FOUR_BUTTON_COLUMNS
        if self == self.FIVE:
            return GAME_MODE_FIVE_BUTTON_COLUMNS
        if self == self.SIX:
            return GAME_MODE_SIX_BUTTON_COLUMNS
        if self == self.EIGHT:
            return GAME_MODE_EIGHT_BUTTON_COLUMNS

    def get_button_mapping(self):
        if self == self.FOUR:
            return GAME_MODE_FOUR_BUTTON_MAPPING
        if self == self.FIVE:
            return GAME_MODE_FIVE_BUTTON_MAPPING
        if self == self.SIX:
            return GAME_MODE_SIX_BUTTON_MAPPING
        if self == self.EIGHT:
            return GAME_MODE_EIGHT_BUTTON_MAPPING

    def get_buttons_to_map(self):
        if self == self.FOUR:
            return GAME_MODE_FOUR_BUTTONS_TO_MAP
        if self == self.FIVE:
            return GAME_MODE_FIVE_BUTTONS_TO_MAP
        if self == self.SIX:
            return GAME_MODE_SIX_BUTTONS_TO_MAP
        if self == self.EIGHT:
            return GAME_MODE_EIGHT_BUTTONS_TO_MAP

    def get_track_indices(self):
        button_types = self.get_button_types()
        track_indices = [button_type.get_track_index() for button_type in button_types]
        return track_indices

    def is_playable_track(self, track_index):
        return track_index in self.get_track_indices()


class GameButtonActionType(IntEnum):
    KEYDOWN = 1
    KEYUP = 2


class GameNotePlayResultType(IntEnum):
    MAX100 = 100
    MAX90 = 90
    MAX1 = 1
    BREAK = 0


class GameNotePlayResultFailReason(IntEnum):
    TOO_LATE_TO_START = 1
    TOO_LATE_TO_FINISH = 2
    TOO_EARLY_TO_FINISH = 3


class GameNotePlayResult(GameObjectBase):
    def __init__(
        self,
        result_type: GameNotePlayResultType,
        timing_diff: Optional[float] = None,
        reason: Optional[GameNotePlayResultFailReason] = None,
    ):
        self.result_type = result_type
        self.timing_diff = timing_diff
        self.reason = reason


class GameNote:
    def __init__(
        self,
        note: PTFileNote,
        track: GameTrack,
        channel: GameTrackChannel,
        sound_table: GameSoundTable,
        sequence_player: GameSequencePlayer,
        pattern_player: Optional[GamePatternPlayer] = None,
    ):
        self._note = note
        self._track = track
        self._channel = channel
        self._sound_table = sound_table
        self._sequence_player = sequence_player
        self._pattern_player = pattern_player

        self._sound_filname = None
        self._sound = None
        self._sound_volume = None

        self._is_general = self._note.command_type == PTFileCommandType.GENERAL
        self._is_bpm_change = self._note.command_type == PTFileCommandType.BPM

        self._is_mr = (
            self._is_general and self._track.get_track_type() == GameTrackType.MR
        )
        self._is_long = self._is_general and self._note.params.duration > 6
        self._is_short = not self._is_long

        self._played_millis_per_tick = []
        self._on_process = None

        if self._note.command_type == PTFileCommandType.GENERAL:
            sound_index = self._note.params.sound_index
            sound_volume = self._note.params.volume / 127

            self._sound = self._sound_table.get_sound_by_index(sound_index)
            self._sound_filename = self._sound_table.get_sound_filename_by_index(
                sound_index
            )

            if self._note.params.pan == 64:
                self._sound_volume = sound_volume
            else:
                sound_volume_right = self._note.params.pan / 127
                sound_volume_left = 1 - sound_volume_right
                sound_volume_max = max(sound_volume_left, sound_volume_right)
                sound_volume_left = sound_volume_left / sound_volume_max
                sound_volume_right = sound_volume_right / sound_volume_max
                sound_volume_left = sound_volume_left * sound_volume
                sound_volume_right = sound_volume_right * sound_volume
                sound_volume = (sound_volume_left, sound_volume_right)
                self._sound_volume = sound_volume

            if self._is_mr:
                assert self._note.params.pan == 64
                pygame.mixer.music.load(self._sound_filename)
                pygame.mixer.music.set_volume(self._sound_volume)

            def on_process():
                self._channel.play_sound(self._sound, self._sound_volume)

            self._on_process = on_process
        elif self._note.command_type == PTFileCommandType.VOLUME:
            track_volume = self._note.params.volume / 127

            def on_process():
                self._channel.set_volume(track_volume)

            self._on_process = on_process
        elif self._note.command_type == PTFileCommandType.BPM:

            def on_process():
                self._sequence_player.set_tempo(self._note.params.tempo)

            self._on_process = on_process
        elif self._note.command_type == PTFileCommandType.BEAT:

            def on_process():
                self._sequence_player.set_beat(self._note.params.beat)

            self._on_process = on_process

        self._unit_judge_millis = 42

        self._is_playing = False
        self._is_played = False

        self._result_type = None
        self._play_result = None

    def set_channel(self, channel):
        self._channel = channel

    def set_pattern_player(self, pattern_player):
        self._pattern_player = pattern_player

    def set_played_millis_per_tick(self, played_millis_per_tick):
        self._played_millis_per_tick = played_millis_per_tick

    def set_unit_judge_millis(self, unit_judge_millis):
        self._unit_judge_millis = unit_judge_millis

    def get_position(self):
        return self._note.position

    def get_duration(self):
        return self._note.params.duration

    def get_end_position(self):
        return self.get_position() + self.get_duration()

    def get_position_millis(self):
        position = self.get_position()
        return self._played_millis_per_tick[position]

    def get_end_position_millis(self):
        end_position = self.get_end_position()
        return self._played_millis_per_tick[end_position]

    def get_sound_duration_millis(self):
        if self._sound:
            return self._sound.get_length() * 1000

    def is_general(self):
        return self._is_general

    def is_bpm_change(self):
        return self._is_bpm_change

    def is_mr(self):
        return self._is_mr

    def is_short(self):
        return self._is_short

    def is_long(self):
        return self._is_long

    def process(self):
        if self._on_process is not None:
            return self._on_process()

    def is_playing(self):
        return self._is_playing

    def is_played(self):
        return self._is_played

    def is_playable(self):
        return self.is_general() and not (self.is_played() or self.is_playing())

    def reset_play_status(self):
        self._is_playing = False
        self._is_played = False

        self._result_type = None
        self._play_result = None

    def start_play(self, current_millis):
        diff_millis = self.get_position_millis() - current_millis
        if diff_millis > 3 * self._unit_judge_millis:
            return

        abs_diff_millis = abs(diff_millis)
        if abs_diff_millis < self._unit_judge_millis:
            self._result_type = GameNotePlayResultType.MAX100
        elif abs_diff_millis < 2 * self._unit_judge_millis:
            self._result_type = GameNotePlayResultType.MAX90
        elif abs_diff_millis < 3 * self._unit_judge_millis:
            self._result_type = GameNotePlayResultType.MAX1

        if self.is_short():
            self._is_played = True
            self._play_result = GameNotePlayResult(
                self._result_type,
                timing_diff=current_millis - self.get_position_millis(),
            )
        elif self.is_long():
            self._is_playing = True

        return self._play_result

    def finish_play(self, current_millis):
        if self.is_long() and self.is_playing():
            self._is_played = True
            self._is_playing = False
            if self.is_too_early_to_finish(current_millis):
                self._result_type = GameNotePlayResultType.BREAK
                self._play_result = GameNotePlayResult(
                    self._result_type,
                    timing_diff=current_millis - self.get_end_position_millis(),
                    reason=GameNotePlayResultFailReason.TOO_EARLY_TO_FINISH,
                )
            else:
                self._play_result = GameNotePlayResult(
                    self._result_type,
                    timing_diff=current_millis - self.get_end_position_millis(),
                )

        return self._play_result

    def is_too_late_to_start(self, current_millis):
        is_too_late_to_start = not self.is_playing() and (
            current_millis - self.get_position_millis()
        ) > (3 * self._unit_judge_millis)
        return is_too_late_to_start

    def is_too_early_to_finish(self, current_millis):
        is_too_early_to_finish = (
            self.get_end_position_millis() - current_millis
            > 3 * self._unit_judge_millis
        )
        return is_too_early_to_finish

    def is_too_late_to_finish(self, current_millis):
        is_too_late_to_finish = (
            current_millis - self.get_end_position_millis()
            > 3 * self._unit_judge_millis
        )
        return is_too_late_to_finish

    def should_fail_to_play(self, current_millis):
        should_fail_to_play = self.is_too_late_to_start(current_millis) or (
            self.is_playing() and self.is_too_late_to_finish(current_millis)
        )
        return should_fail_to_play

    def fail(self, current_millis):
        if self.is_too_late_to_start(current_millis):
            self._play_result = GameNotePlayResult(
                GameNotePlayResultType.BREAK,
                timing_diff=current_millis - self.get_position_millis(),
                reason=GameNotePlayResultFailReason.TOO_LATE_TO_START,
            )
        elif self.is_too_late_to_finish(current_millis):
            self._play_result = GameNotePlayResult(
                GameNotePlayResultType.MAX1,
                timing_diff=current_millis - self.get_end_position_millis(),
                reason=GameNotePlayResultFailReason.TOO_LATE_TO_FINISH,
            )
        return self._play_result


class GameTrack:
    def __init__(
        self,
        track: PTFileTrack,
        track_type: GameTrackType,
        sound_table: GameSoundTable,
        sequence_player: GameSequencePlayer,
        channel: Optional[GameTrackChannel] = None,
        pattern_player: Optional[GamePatternPlayer] = None,
    ):
        self._track = track
        self._track_type = track_type
        self._sound_table = sound_table
        self._sequence_player = sequence_player
        self._channel = channel
        self._pattern_player = pattern_player

        self._notes = [
            GameNote(
                note,
                self,
                self._channel,
                self._sound_table,
                self._sequence_player,
                self._pattern_player,
            )
            for note in self._track.notes
        ]
        self._notes_len = len(self._notes)

        self._played_millis_per_tick = []
        self._unit_judge_millis = 42

        self._current_index = 0
        self._current_play_index = 0
        self._is_playing = False

    def set_channel(self, channel):
        self._channel = channel

        for note in self._notes:
            note.set_channel(channel)

    def set_played_millis_per_tick(self, played_millis_per_tick):
        self._played_millis_per_tick = played_millis_per_tick

        for note in self._notes:
            note.set_played_millis_per_tick(played_millis_per_tick)

    def set_unit_judge_millis(self, unit_judge_millis):
        self._unit_judge_millis = unit_judge_millis

        for note in self._notes:
            note.set_unit_judge_millis(unit_judge_millis)

    def set_pattern_player(self, pattern_player):
        self._pattern_player = pattern_player

        for note in self._notes:
            note.set_pattern_player(pattern_player)

    def reset_play_status(self):
        self._current_play_index = 0

        for note in self._notes:
            note.reset_play_status()

    def get_track_type(self):
        return self._track_type

    def get_index(self):
        return self._current_index

    def set_index(self, index):
        self._current_index = index

    def increment_index(self):
        self.set_index(self.get_index() + 1)

    def get_head_note(self):
        if self._current_index < self._notes_len:
            return self._notes[self._current_index]

    def find_note_index(self, predicate, default=None, start_index=None):
        if start_index is None:
            start_index = 0
        if default is None:
            default = self._notes_len
        return next(
            filter(
                lambda i: predicate(self._notes[i]),
                range(start_index, self._notes_len),
            ),
            default,
        )

    def set_index_for_tick(self, tick):
        index = self.find_note_index(lambda note: note.get_position() >= tick)
        self.set_index(index)

    def get_notes_between_ticks_for_display(
        self,
        start_tick,
        end_tick=None,
        start_index=None,
    ):
        if start_index is None:
            start_index = 0

        start_index = self.find_note_index(
            lambda note: note.is_general()
            and not note.is_played()
            and (
                note.get_position() >= start_tick
                or (note.is_long() and note.get_end_position() >= start_tick)
            ),
            start_index=start_index,
        )
        if end_tick is None:
            end_index = self._notes_len
        else:
            end_index = self.find_note_index(
                lambda note: note.is_general()
                and not note.is_played()
                and note.get_position() >= end_tick,
                start_index=start_index,
            )
        return self._notes[start_index:end_index]

    def get_play_index(self):
        return self._current_play_index

    def set_play_index(self, play_index):
        self._current_play_index = self.find_note_index(
            lambda note: note.is_playable(),
            start_index=play_index,
        )

    def increment_play_index(self):
        self.set_play_index(self.get_play_index() + 1)

    def set_play_index_for_tick(self, tick):
        index = self.find_note_index(lambda note: note.get_position() >= tick)
        self.set_play_index(index)

    def get_play_head_note(self):
        if self._current_play_index < self._notes_len:
            return self._notes[self._current_play_index]

    def start_play(self, current_millis):
        if self._is_playing:
            return
        self._is_playing = True
        note = self.get_play_head_note()
        if not note:
            return
        note.process()
        play_result = note.start_play(current_millis)
        if note.is_played():
            self.increment_play_index()
        return play_result

    def finish_play(self, current_millis):
        if not self._is_playing:
            return
        self._is_playing = False
        note = self.get_play_head_note()
        if not note:
            return
        play_result = note.finish_play(current_millis)
        if note.is_played():
            self.increment_play_index()
        return play_result

    def is_playing(self):
        return self._is_playing


class GameSequencePlayer:
    def open_ptfile(self, ptfile: PTFile, ptfile_dir: Optional[str] = None):
        self.stop_play()

        self._ptfile = ptfile
        self._ptfile_dir = ptfile_dir

        self._beats_per_minute = self._ptfile.header.master_bpm
        self._total_ticks = self._ptfile.header.total_ticks
        self._ticks_per_measure = self._ptfile.header.ticks_per_measure
        self._time_in_seconds = self._ptfile.header.time_in_seconds

        self._sound_table = GameSoundTable(self._ptfile.sounds, self._ptfile_dir)

        self._effective_tracks = {
            track_index: track
            for track_index, track in enumerate(self._ptfile.tracks)
            if track.notes
        }
        self._track_type_per_track = {
            track_index: GameTrackType.get_track_type(track_index)
            for track_index in self._effective_tracks.keys()
        }

        self._game_tracks_dict = {
            track_index: GameTrack(
                track,
                self._track_type_per_track[track_index],
                self._sound_table,
                self,
                pattern_player=self._pattern_player,
            )
            for track_index, track in self._effective_tracks.items()
        }

        self._game_tracks_list = list(self._game_tracks_dict.values())
        self._game_playable_tracks_list = [
            track
            for track_index, track in self._game_tracks_dict.items()
            if self._game_mode.is_playable_track(track_index)
        ]

        for track in self._game_tracks_list:
            track.set_unit_judge_millis(self._unit_judge_millis)

        self._tempos_per_tick = []
        self._played_millis_per_tick = []
        self._tick_interval_millis_per_tick = []

        tempo = 0
        played_millis = 0
        tick_interval_millis = 0

        self._track_has_any_overlap = {}
        self._track_has_any_general_note = {
            track_index: any(
                note.command_type == PTFileCommandType.GENERAL for note in track.notes
            )
            for track_index, track in self._effective_tracks.items()
        }
        last_general_note_per_track = {}

        for cursor_tick in range(self._total_ticks):
            played_millis += tick_interval_millis
            for track_index, track in self._game_tracks_dict.items():
                note = track.get_head_note()
                while note and note.get_position() <= cursor_tick:
                    if note.is_general():
                        if (
                            track_index not in self._track_has_any_overlap
                            and track_index in last_general_note_per_track
                        ):
                            prev_note = last_general_note_per_track[track_index]
                            if (
                                self._played_millis_per_tick[prev_note.get_position()]
                                + prev_note.get_sound_duration_millis()
                                > played_millis
                            ):
                                self._track_has_any_overlap[track_index] = True
                        last_general_note_per_track[track_index] = note
                    if note.is_bpm_change():
                        tempo = note._note.params.tempo
                        tick_interval_millis = 240000 / self._ticks_per_measure / tempo
                    track.increment_index()
                    note = track.get_head_note()
            self._tempos_per_tick.append(tempo)
            self._played_millis_per_tick.append(played_millis)
            self._tick_interval_millis_per_tick.append(tick_interval_millis)

        for track in self._game_tracks_list:
            track.set_index(0)
            track.set_played_millis_per_tick(self._played_millis_per_tick)

        self._number_of_channels_per_track = {
            track_index: 0
            if not self._track_has_any_general_note[track_index]
            else 2
            if self._track_has_any_overlap.get(track_index)
            or self._track_type_per_track[track_index] in [GameTrackType.FG1]
            else 1
            for track_index, track in self._effective_tracks.items()
        }
        self._total_number_of_channels = sum(
            self._number_of_channels_per_track.values()
        )

        pygame.mixer.set_num_channels(self._total_number_of_channels)

        def partition_list_by_size(lst, sizes):
            if isinstance(sizes, list):
                result = [[] for i in range(len(sizes))]

                def items(lst):
                    return enumerate(lst)

            elif isinstance(sizes, dict):
                result = {}

                def items(dct):
                    return dct.items()

            end = 0

            for key, size in items(sizes):
                start = end
                size = sizes[key]
                end = start + size
                item = lst[start:end]
                result[key] = item

            return result

        self._pygame_channels = [
            Channel(i) for i in range(self._total_number_of_channels)
        ]
        self._channel_per_track = {
            track_index: GameTrackChannel(channels)
            for track_index, channels in partition_list_by_size(
                self._pygame_channels, self._number_of_channels_per_track
            ).items()
        }

        for track_index, track in self._game_tracks_dict.items():
            channel = self._channel_per_track[track_index]
            track.set_channel(channel)

        self.set_tempo(self._beats_per_minute)
        self.set_beat(4)

        self._current_tick = 0

        self._current_millis = -1
        self._started_millis = -1
        self._elapsed_millis = -1
        self._played_millis = -1
        self._paused_millis = -1

        self._is_playable = True
        self._is_playing = False

        self._play_intermediate_mr_sound = None

    def __init__(
        self,
        ptfile: Optional[PTFile] = None,
        ptfile_dir: Optional[str] = None,
        pattern_player: Optional[GamePatterPlayer] = None,
    ):
        # ptfile dependent members
        self._ptfile = ptfile
        self._ptfile_dir = ptfile_dir

        self._current_millis = -1
        self._started_millis = -1
        self._elapsed_millis = -1
        self._played_millis = -1
        self._paused_millis = -1

        self._sound_table = None

        self._effective_tracks = {}
        self._track_type_per_track = {}

        self._game_tracks_dict = {}
        self._game_tracks_list = []
        self._game_playable_tracks_list = []

        self._tempos_per_tick = []
        self._played_millis_per_tick = []
        self._tick_interval_millis_per_tick = []

        self._track_has_any_overlap = {}
        self._track_has_any_general_note = {}

        self._number_of_channels_per_track = {}
        self._total_number_of_channels = 0

        self._pygame_channels = []
        self._channel_per_track = {}

        self._beats_per_minute = 0
        self._total_ticks = 0
        self._ticks_per_measure = 0
        self._time_in_seconds = 0

        self._tempo = 0
        self._beat = 0

        self._tick_interval_millis = 0

        self._current_tick = 0

        self._is_playable = False
        self._is_playing = False

        self._play_intermediate_mr_sound = None

        # ptfile independent members
        self._pattern_player = pattern_player
        self._is_auto_play = False
        self._game_mode = GameMode.FOUR
        self._unit_judge_millis = 42

        if self._ptfile is not None:
            self.open_ptfile(self._ptfile, self._ptfile_dir)

    def set_tempo(self, tempo):
        self._tempo = tempo
        self._tick_interval_millis = 240000 / self._ticks_per_measure / self._tempo

    def set_beat(self, beat):
        self._beat = beat

    def set_auto_play(self, auto_play):
        self._is_auto_play = auto_play

    def set_game_mode(self, game_mode):
        self._game_mode = game_mode

        self._game_playable_tracks_list = [
            track
            for track_index, track in self._game_tracks_dict.items()
            if self._game_mode.is_playable_track(track_index)
        ]

        for track in self._game_playable_tracks_list:
            track.set_play_index_for_tick(self._current_tick)

    def set_unit_judge_millis(self, unit_judge_millis):
        self._unit_judge_millis = unit_judge_millis

        for track in self._game_tracks_list:
            track.set_unit_judge_millis(unit_judge_millis)

    def get_auto_play(self):
        return self._is_auto_play

    def set_auto_play(self, auto_play):
        self._is_auto_play = auto_play

    def set_pattern_player(self, pattern_player):
        self._pattern_player = pattern_player

        for track in self._game_tracks_list:
            track.set_pattern_player(pattern_player)

    def get_tempo(self):
        return self._tempo

    def get_beat(self):
        return self._beat

    def is_playing(self):
        return self._is_playing

    def reset_progress(self):
        self._current_tick = 0

        self._current_millis = -1
        self._started_millis = -1
        self._elapsed_millis = -1
        self._played_millis = -1
        self._paused_millis = -1

        for track in self._game_tracks_list:
            track.set_index(0)

        self.reset_play_status()
        self._pattern_player.reset_play_stats()

    def start_play(self):
        if not self._is_playing:
            self.reset_progress()
            self._is_playing = self._is_playable

    def stop_play(self):
        if self._is_playing:
            self._is_playing = False
            pygame.mixer.stop()
        self.reset_progress()

    def pause_play(self):
        if self._is_playing:
            self._is_playing = False
            self._paused_millis = pygame.time.get_ticks()
            pygame.mixer.pause()

    def resume_play(self):
        if not self._is_playing:
            if self._paused_millis < 0:
                self.sync_with_current_tick()
            self._is_playing = self._is_playable

    def on_tick_start(self, current_millis=None):
        if not self._is_playing:
            return

        if current_millis is not None:
            self._current_millis = current_millis
        else:
            self._current_millis = pygame.time.get_ticks()

    def on_tick(self):
        if not self._is_playing:
            return

        if self._started_millis < 0:
            if self._played_millis < 0:
                self._started_millis = self._current_millis
            else:
                self._started_millis = self._current_millis - self._played_millis

        if self._played_millis < 0:
            self._played_millis = 0

        if self._paused_millis > 0:
            paused_millis = self._current_millis - self._paused_millis
            self._started_millis += paused_millis
            self._paused_millis = -1
            pygame.mixer.unpause()

        if self._play_intermediate_mr_sound is not None:
            self._play_intermediate_mr_sound()
            self._play_intermediate_mr_sound = None

        self._elapsed_millis = self._current_millis - self._started_millis
        incremental_millis = self._elapsed_millis - self._played_millis

        incremental_ticks = 0
        if self._tick_interval_millis > 0:
            incremental_ticks = int(incremental_millis / self._tick_interval_millis)

        if incremental_ticks > 0:
            self._current_tick += incremental_ticks
            self._played_millis += self._tick_interval_millis * incremental_ticks

        notes_to_process = []

        for track in self._game_tracks_list:
            note = track.get_head_note()
            while note and note.get_position() <= self._current_tick:
                if not note.is_general():
                    notes_to_process.append(note)
                elif track not in self._game_playable_tracks_list:
                    notes_to_process.append(note)
                elif self._is_auto_play:
                    notes_to_process.append(note)
                track.increment_index()
                note = track.get_head_note()

        for note in notes_to_process:
            note.process()

        for track in self._game_playable_tracks_list:
            note = track.get_play_head_note()
            while note and note.should_fail_to_play(self._elapsed_millis):
                if not self._is_auto_play:
                    play_result = note.fail(self._elapsed_millis)
                    if play_result is not None and play_result.result_type is not None:
                        self._pattern_player.on_play_result(play_result)
                track.increment_play_index()
                note = track.get_play_head_note()

        if self._current_tick > self._total_ticks:
            self._is_playing = False

    def get_tracks(self):
        return self._game_tracks_dict

    def get_tick_interval_millis(self):
        return self._tick_interval_millis

    def get_line_interval_ticks(self):
        return self._ticks_per_measure * self._beat / 4

    def get_current_tick(self):
        return self._current_tick

    def get_current_tick_precise(self):
        current_tick = self.get_current_tick()
        if (
            self._current_millis > 0
            and self._started_millis > 0
            and self._played_millis > 0
            and self._tick_interval_millis > 0
        ):
            started_millis = self._started_millis
            if self._paused_millis > 0:
                paused_millis = self._current_millis - self._paused_millis
                started_millis += paused_millis
            elapsed_millis = self._current_millis - started_millis
            incremental_millis = elapsed_millis - self._played_millis
            incremental_ticks = incremental_millis / self._tick_interval_millis
            current_tick += incremental_ticks
        return current_tick

    def get_current_millis(self):
        return self._current_millis

    def get_elapsed_millis(self):
        return self._elapsed_millis

    def set_current_tick(self, current_tick):
        if self._is_playing:
            self._is_playing = False
            pygame.mixer.stop()

        if self._paused_millis > 0:
            self._paused_millis = -1
            pygame.mixer.stop()

        self._current_tick = current_tick
        self.reset_play_status()

    def offset_current_tick(self, delta_tick):
        current_tick = self._current_tick + delta_tick
        current_tick = max(0, current_tick)
        self.set_current_tick(current_tick)

    def sync_with_current_tick(self):
        for track in self._game_playable_tracks_list:
            track.set_play_index_for_tick(self._current_tick)

        for track in self._game_tracks_list:
            track.set_index(0)

        mr_note = None
        mr_started_millis = -1

        tempo = 0
        played_millis = 0
        tick_interval_millis = 0

        for cursor_tick in range(self._current_tick):
            played_millis += tick_interval_millis
            for track in self._game_tracks_list:
                note = track.get_head_note()
                while note and note.get_position() <= cursor_tick:
                    if note.is_bpm_change():
                        tempo = note._note.params.tempo
                        tick_interval_millis = 240000 / self._ticks_per_measure / tempo
                    elif note.is_mr():
                        mr_note = note
                        mr_started_millis = played_millis
                    track.increment_index()
                    note = track.get_head_note()

        self._tempo = tempo
        self._tick_interval_millis = tick_interval_millis

        self._started_millis = -1
        self._played_millis = played_millis

        if mr_note is not None and mr_started_millis >= 0:
            frequency, format, channels = pygame.mixer.get_init()
            mr_played_millis = played_millis - mr_started_millis
            mr_offset = int(frequency * mr_played_millis / 1000)
            mr_array = pygame.sndarray.array(mr_note._sound)
            mr_array = mr_array[mr_offset:]
            mr_sound = pygame.sndarray.make_sound(mr_array)
            mr_sound.set_volume(mr_note._sound_volume)
            mr_channel = mr_note._channel

            def play_intermediate_mr_sound():
                mr_channel.play_sound(mr_sound)

            self._play_intermediate_mr_sound = play_intermediate_mr_sound

    def reset_play_status(self):
        for track in self._game_playable_tracks_list:
            track.reset_play_status()

    def on_event(self, event):
        if event.type == pygame.WINDOWMOVED:  # pylint: disable=no-member
            if self._is_playing:
                self.offset_current_tick(0)
                self.resume_play()


class GameScreenManager:
    def __init__(self):
        self._display_info = pygame.display.Info()

        self._screen_height = int(self._display_info.current_h * 0.9)
        self._screen_width = int(self._screen_height * (15.5 / 33.5))

        self._screen_size = (self._screen_width, self._screen_height)
        self._screen = pygame.display.set_mode(
            size=self._screen_size,
            flags=pygame.SCALED,  # pylint: disable=no-member
        )

        self._drawables = []

    def get_screen(self):
        return self._screen

    def get_screen_size(self):
        return self._screen_size

    def add_drawable(self, drawable):
        self._drawables.append(drawable)

    def on_tick(self):
        for drawable in self._drawables:
            drawable.on_draw()

    def on_tick_end(self):
        pygame.display.flip()


class GamePatternDrawer:
    def __init__(
        self,
        game_mode: GameMode,
        note_speed: float,
        screen_manager: GameScreenManager,
        sequence_player: GameSequencePlayer,
        actions: Optinonal[GameActions] = None,
    ):
        self._game_mode = game_mode
        self._note_speed = note_speed

        self._screen_manager = screen_manager
        self._sequence_player = sequence_player
        self._actions = actions

        self._screen = self._screen_manager.get_screen()
        self._screen_width, self._screen_height = self._screen_manager.get_screen_size()

        self.set_sequence_player(self._sequence_player)
        self.set_note_speed(self._note_speed)

        self._track_height = int(self._screen_height * (25 / 33.5))
        self._track_width = int(self._screen_height * (15.5 / 33.5))

        self._button_height = int(self._screen_height * (0.5 / 33.5))

        self._border_width = int(self._button_height * 0.15)
        self._border_gamma = 2
        self._border_radius = 0

        self._judge_line_height = int(self._screen_height * (0.5 / 33.5))
        self._judge_line_loc = int(self._screen_height * (1.5 / 33.5))
        self._judge_line_middle = int(self._track_height - self._judge_line_loc)
        self._judge_line_top = int(
            self._judge_line_middle - (self._judge_line_height / 2)
        )
        self._judge_line_color = Color(200, 200, 200)

        self._background_color = Color(20, 20, 20)
        self._line_color = (100, 100, 100)

    def set_actions(self, actions):
        self._actions = actions

    def get_game_mode(self):
        return self._game_mode

    def set_game_mode(self, game_mode: GameMode):
        self._game_mode = game_mode

        self._total_buttons = self._game_mode.get_total_buttons()
        self._total_columns = self._game_mode.get_total_columns()

        self._button_types = self._game_mode.get_button_types()
        self._button_colors = self._game_mode.get_button_colors()
        self._button_columns = self._game_mode.get_button_columns()

        self._column_width = self._screen_width / self._total_columns

        self._buttons_to_draw = []

        self._button_draw_order = [
            GameTrackButtonType.SIDEL,
            GameTrackButtonType.SIDER,
            GameTrackButtonType.L1,
            GameTrackButtonType.R1,
            GameTrackButtonType.BUTTON1,
            GameTrackButtonType.BUTTON2,
            GameTrackButtonType.BUTTON3,
            GameTrackButtonType.BUTTON4,
            GameTrackButtonType.BUTTON5,
            GameTrackButtonType.BUTTON6,
        ]

        for button_type in self._button_draw_order:
            if button_type in self._button_types:
                button_index = self._button_types.index(button_type)
                track_index = button_type.get_track_index()
                if track_index in self._tracks:
                    track = self._tracks[track_index]
                    button_color = self._button_colors[button_index]
                    button_column = self._button_columns[button_index]
                    if isinstance(button_column, tuple):
                        button_left = self._column_width * button_column[0]
                        button_width = self._column_width * button_column[1]
                    else:
                        button_left = self._column_width * button_column
                        button_width = self._column_width
                    button_args = (
                        track,
                        button_type,
                        button_color,
                        button_left,
                        button_width,
                    )
                    self._buttons_to_draw.append(button_args)

    def get_note_speed(self):
        return self._note_speed

    def set_note_speed(self, note_speed):
        self._note_speed = note_speed
        self._track_drop_duration_millis = 2800 / self._note_speed

    def get_ticks_in_height(self):
        ticks_in_height = 0
        tick_interval_millis = self._sequence_player.get_tick_interval_millis()
        if tick_interval_millis:
            ticks_in_height = self._track_drop_duration_millis / tick_interval_millis
        return ticks_in_height

    def get_current_tick(self):
        current_tick = self._sequence_player.get_current_tick_precise()
        return current_tick

    def set_sequence_player(self, sequence_player):
        self._sequence_player = sequence_player
        self._tracks = self._sequence_player.get_tracks()
        self.set_game_mode(self._game_mode)

    def draw_lines(self, current_tick, ticks_in_height):
        if ticks_in_height == 0:
            return

        line_interval_ticks = self._sequence_player.get_line_interval_ticks()
        num_lines = (current_tick + ticks_in_height) / line_interval_ticks
        num_lines = int(num_lines)
        line_tick = num_lines * line_interval_ticks
        line_middle = 1 - (line_tick - current_tick) / ticks_in_height
        line_middle = line_middle * self._judge_line_middle
        line_middle_int = int(line_middle)

        while line_middle < self._screen_height:
            pygame.draw.line(
                self._screen,
                color=self._line_color,
                start_pos=(0, line_middle_int),
                end_pos=(self._track_width, line_middle_int),
            )
            line_tick -= line_interval_ticks
            line_middle = 1 - (line_tick - current_tick) / ticks_in_height
            line_middle = line_middle * self._judge_line_middle
            line_middle_int = int(line_middle)

    def draw_tracks(self):
        for (
            track,
            button_type,
            button_color,
            button_left,
            button_width,
        ) in self._buttons_to_draw:
            if track.is_playing():
                track_color = self._background_color.correct_gamma(0.8)
                track_rect = (button_left, 0, button_width, self._screen_height)
                self._screen.fill(track_color, track_rect)

    def draw_button(
        self,
        button_color,
        button_left,
        button_top,
        button_width,
        button_height,
    ):
        button_rect = Rect(button_left, button_top, button_width, button_height)
        button_rect = button_rect.inflate(-1, 1)
        self._screen.fill(button_color, button_rect)
        pygame.draw.rect(
            self._screen,
            color=button_color.correct_gamma(self._border_gamma),
            rect=button_rect,
            width=self._border_width,
        )

    def draw_buttons(self, current_tick, ticks_in_height):
        start_tick = current_tick - ticks_in_height
        end_tick = current_tick + ticks_in_height + 1

        for (
            track,
            button_type,
            button_color,
            button_left,
            button_width,
        ) in self._buttons_to_draw:
            notes = track.get_notes_between_ticks_for_display(start_tick, end_tick)

            for note in notes:
                button_middle = (
                    1 - (note.get_position() - current_tick) / ticks_in_height
                )
                button_middle = button_middle * self._judge_line_middle
                button_color_inner = button_color

                if note.is_long():
                    note_duration = note.get_duration()
                    button_height = (
                        note_duration / ticks_in_height * self._judge_line_middle
                    )
                    button_top = button_middle - button_height + self._button_height / 2
                    if button_type <= 6:
                        button_color_inner = button_color.correct_gamma(
                            self._border_gamma
                        )
                else:
                    button_height = self._button_height
                    button_top = button_middle - self._button_height / 2

                if button_top < 0:
                    button_height += button_top
                    button_top = 0
                if button_top + button_height > self._screen_height:
                    button_height = self._screen_height - button_top

                if note.is_playing():
                    button_height = self._judge_line_middle - button_top

                if not note.is_played():
                    self.draw_button(
                        button_color_inner,
                        int(button_left),
                        int(button_top),
                        int(button_width),
                        int(button_height),
                    )

    def draw_judge_line(self):
        judge_line_rect = Rect(
            0,
            self._judge_line_top,
            self._track_width,
            self._judge_line_height,
        )
        self._screen.fill(
            self._judge_line_color,
            judge_line_rect,
        )
        pygame.draw.rect(
            self._screen,
            color=self._judge_line_color.correct_gamma(self._border_gamma),
            rect=judge_line_rect,
            width=self._border_width,
        )

    def draw_under_box(self):
        under_box_rect = Rect(
            0,
            self._track_height,
            self._track_width,
            self._screen_height - self._track_height,
        )
        under_box_color = self._background_color.correct_gamma(0.7)
        self._screen.fill(
            under_box_color,
            under_box_rect,
        )
        pygame.draw.rect(
            self._screen,
            color=under_box_color.correct_gamma(1.2),
            rect=under_box_rect,
            width=self._border_width,
        )

    def draw_track(self):
        current_tick = self.get_current_tick()
        ticks_in_height = self.get_ticks_in_height()

        self._screen.fill(self._background_color)

        self.draw_tracks()
        self.draw_lines(current_tick, ticks_in_height)
        self.draw_judge_line()
        self.draw_buttons(current_tick, ticks_in_height)
        self.draw_under_box()

    def on_draw(self):
        self.draw_track()


class GamePatternPlayer:
    def __init__(
        self,
        sequence_player: GameSequencePlayer,
        screen_manager: GameScreenManager,
        ui_manager: GameUIManager,
    ):
        self._sequence_player = sequence_player
        self._screen_manager = screen_manager
        self._ui_manager = ui_manager

        self._screen = self._screen_manager.get_screen()
        self._screen_width, self._screen_height = self._screen_manager.get_screen_size()

        self._font = self._ui_manager._manager.ui_theme.get_font([])
        self._font_antialias = True

        self._combo_size = 84
        self._accuracy_size = 21
        self._counts_size = 42

        self._combo_color = Color(150, 150, 150)
        self._accuracy_color = Color(150, 150, 150)
        self._counts_color = Color(150, 150, 150)

        self._combo_font = pygame.font.SysFont(self._font.name, self._combo_size)
        self._accuracy_font = pygame.font.SysFont(self._font.name, self._accuracy_size)
        self._counts_font = pygame.font.SysFont(self._font.name, self._accuracy_size)

        self._text_left = int(self._screen_width * 0.5)
        self._combo_top = int(self._screen_height * (5 / 33.5))
        self._accuracy_top = int(self._screen_height * (20 / 33.5))
        self._counts_top = int(self._screen_height * (16 / 33.5))

        self._combo_pos = (self._text_left, self._combo_top)
        self._accuracy_pos = (self._text_left, self._accuracy_top)
        self._counts_pos = (self._text_left, self._counts_top)

        self._unit_judge_millis = 42
        self._sequence_player.set_unit_judge_millis(self._unit_judge_millis)

        self._play_result_count = 0
        self._combo_count = 0
        self._average_accuracy = 0
        self._result_type_counts = {
            GameNotePlayResultType.MAX100: 0,
            GameNotePlayResultType.MAX90: 0,
            GameNotePlayResultType.MAX1: 0,
            GameNotePlayResultType.BREAK: 0,
        }

    def play_button(
        self,
        button: GameTrackButtonType,
        action_type: GameButtonActionType = GameButtonActionType.KEYDOWN,
    ):
        track_index = button.get_track_index()
        track = self._sequence_player.get_tracks().get(track_index)

        if track:
            current_millis = self._sequence_player.get_elapsed_millis()

            if action_type == GameButtonActionType.KEYDOWN:
                play_result = track.start_play(current_millis)
            elif action_type == GameButtonActionType.KEYUP:
                play_result = track.finish_play(current_millis)

            if play_result is not None and play_result.result_type is not None:
                self.on_play_result(play_result)

    def reset_play_stats(self):
        self._play_result_count = 0
        self._combo_count = 0
        self._average_accuracy = 0
        self._result_type_counts = {
            GameNotePlayResultType.MAX100: 0,
            GameNotePlayResultType.MAX90: 0,
            GameNotePlayResultType.MAX1: 0,
            GameNotePlayResultType.BREAK: 0,
        }

    def on_play_result(self, play_result: GameNotePlayResult):
        self._play_result_count += 1

        self._average_accuracy = self._average_accuracy * (
            self._play_result_count - 1
        ) / self._play_result_count + (
            play_result.result_type / self._play_result_count
        )

        if play_result.result_type == GameNotePlayResultType.BREAK:
            self._combo_count = 0
        else:
            self._combo_count += 1

        self._result_type_counts[play_result.result_type] = (
            self._result_type_counts.get(play_result.result_type, 0) + 1
        )

    def on_draw(self):
        if not self._sequence_player.get_auto_play():
            combo_text = self._combo_font.render(
                "%d" % self._combo_count,
                self._font_antialias,
                self._combo_color,
            )
            acc_text = self._accuracy_font.render(
                "%.2f%%" % self._average_accuracy,
                self._font_antialias,
                self._accuracy_color,
            )
            counts_text = self._accuracy_font.render(
                "%d / %d / %d / %d" % tuple(self._result_type_counts.values()),
                self._font_antialias,
                self._counts_color,
            )
            self._screen.blit(
                combo_text,
                combo_text.get_rect(center=self._combo_pos),
            )
            self._screen.blit(
                acc_text,
                acc_text.get_rect(center=self._accuracy_pos),
            )
            if not self._sequence_player._is_playing:
                self._screen.blit(
                    counts_text,
                    counts_text.get_rect(center=self._counts_pos),
                )


class GameActions:
    def __init__(
        self,
        sequence_player: GameSequencePlayer,
        pattern_drawer: GamePatternDrawer,
        ui_manager: GameUIManager,
        pattern_player: GamePatternPlayer,
        input_handler: GameInputHandler,
    ):
        self._sequence_player = sequence_player
        self._pattern_drawer = pattern_drawer
        self._ui_manager = ui_manager
        self._pattern_player = pattern_player
        self._input_handler = input_handler

        self._adding_button_mappings = False
        self._buttons_to_map = []
        self._button_index_to_map = 0
        self._showing_help = False

    def pause_or_stop_play(self):
        if self._sequence_player.is_playing():
            return self._sequence_player.pause_play()
        else:
            return self._sequence_player.stop_play()

    def pause_or_resume_play(self):
        if self._sequence_player.is_playing():
            return self._sequence_player.pause_play()
        else:
            return self._sequence_player.resume_play()

    def fast_forward_play(self, step=0.25):
        ticks_in_height = self._pattern_drawer.get_ticks_in_height()
        ticks_offset = int(ticks_in_height * step)
        return self._sequence_player.offset_current_tick(ticks_offset)

    def rewind_backward_play(self, step=0.25):
        ticks_in_height = self._pattern_drawer.get_ticks_in_height()
        ticks_offset = -int(ticks_in_height * step)
        return self._sequence_player.offset_current_tick(ticks_offset)

    def decrease_note_speed(self, step=0.1):
        note_speed = self._pattern_drawer.get_note_speed()
        if note_speed > 1.0:
            note_speed = max(1.0, note_speed - step)
            return self.set_note_speed(note_speed)

    def increase_note_speed(self, step=0.1):
        note_speed = self._pattern_drawer.get_note_speed()
        if note_speed < 9.0:
            note_speed = min(9.0, note_speed + step)
            return self.set_note_speed(note_speed)

    def set_game_mode(self, game_mode: Union[int, GameMode]):
        game_mode = GameMode(game_mode)
        self._sequence_player.set_game_mode(game_mode)
        self._pattern_drawer.set_game_mode(game_mode)
        self._ui_manager.set_game_mode(game_mode)
        self._input_handler.set_game_mode(game_mode)

    def set_note_speed(self, note_speed: float):
        self._pattern_drawer.set_note_speed(note_speed)
        self._ui_manager.set_note_speed(note_speed)

    def toggle_auto_play(self):
        auto_play = self._sequence_player.get_auto_play()
        auto_play = not auto_play
        self._sequence_player.set_auto_play(auto_play)
        self._input_handler.set_ignore_play_keys(auto_play)

    def setup_button_mapping(self):
        self._adding_button_mappings = True
        self._buttons_to_map = self._pattern_drawer.get_game_mode().get_buttons_to_map()
        self._button_index_to_map = 0

    def open_ptfile(
        self,
        ptfile: PTFile,
        ptfile_dir: Optional[str] = None,
    ):
        self._sequence_player.open_ptfile(ptfile, ptfile_dir)
        self._pattern_drawer.set_sequence_player(self._sequence_player)

    def start_play(self, filename: Optional[str] = None):
        if filename is not None:
            ptfile = PTFile.parse(filename)
            ptfile_dir = os.path.dirname(filename)
            self.open_ptfile(ptfile, ptfile_dir)
        return self._sequence_player.start_play()

    def play_button(
        self,
        button: GameTrackButtonType,
        action_type: GameButtonActionType = GameButtonActionType.KEYDOWN,
    ):
        return self._pattern_player.play_button(button, action_type)


class GameUIManager:
    def __init__(
        self,
        screen_manager: GameScreenManager,
        sequence_player: GameSequencePlayer,
        pattern_drawer: GamePatternDrawer,
        actions: Optional[GameActions] = None,
    ):
        self._screen_manager = screen_manager
        self._sequence_player = sequence_player
        self._pattern_drawer = pattern_drawer
        self._actions = actions

        self._screen = self._screen_manager.get_screen()
        self._screen_size = (
            self._screen_width,
            self._screen_height,
        ) = self._screen_manager.get_screen_size()

        self._underbox_top = self._pattern_drawer._track_height
        self._underbox_height = self._screen_height - self._underbox_top
        self._underbox_width = self._screen_width
        self._underbox_padding = self._pattern_drawer._button_height

        self._full_width = self._underbox_width - 2 * self._underbox_padding
        self._half_width = int((self._underbox_width - 3 * self._underbox_padding) / 2)
        self._triple_width = int(
            (self._underbox_width - 4 * self._underbox_padding) / 3
        )
        self._quarter_width = int(self._full_width / 4)
        self._line_height = int(
            (self._underbox_height - 4 * self._underbox_padding) / 3
        )

        self._manager = UIManager(self._screen_size)

        self._clock = Clock()
        self._time_delta = 0

        self._play_pause_button_pos = (
            self._underbox_padding,
            self._underbox_top + self._underbox_padding,
        )
        self._play_pause_button_size = (self._quarter_width, self._line_height)
        self._play_pause_button_rect = Rect(
            self._play_pause_button_pos, self._play_pause_button_size
        )
        self._play_pause_button = UIButton(
            relative_rect=self._play_pause_button_rect,
            text="Play/Pause",
            tool_tip_text="Enter",
            manager=self._manager,
        )

        self._stop_button_pos = (
            self._underbox_padding + self._quarter_width,
            self._underbox_top + self._underbox_padding,
        )
        self._stop_button_size = (self._quarter_width, self._line_height)
        self._stop_button_rect = Rect(self._stop_button_pos, self._stop_button_size)
        self._stop_button = UIButton(
            relative_rect=self._stop_button_rect,
            text="Stop",
            tool_tip_text="ESC",
            manager=self._manager,
        )

        self._backward_button_pos = (
            self._underbox_padding + 2 * self._quarter_width,
            self._underbox_top + self._underbox_padding,
        )
        self._backward_button_size = (self._quarter_width, self._line_height)
        self._backward_button_rect = Rect(
            self._backward_button_pos, self._backward_button_size
        )
        self._backward_button = UIButton(
            relative_rect=self._backward_button_rect,
            text="Backward",
            tool_tip_text="Left/Down",
            manager=self._manager,
        )

        self._forward_button_pos = (
            self._underbox_padding + 3 * self._quarter_width,
            self._underbox_top + self._underbox_padding,
        )
        self._forward_button_size = (self._quarter_width, self._line_height)
        self._forward_button_rect = Rect(
            self._forward_button_pos, self._forward_button_size
        )
        self._forward_button = UIButton(
            relative_rect=self._forward_button_rect,
            text="Forward",
            tool_tip_text="Right/Up",
            manager=self._manager,
        )

        self._num_button_menu_pos = (
            self._underbox_padding,
            self._underbox_top + self._line_height + 2 * self._underbox_padding,
        )
        self._num_button_menu_size = (self._triple_width, self._line_height)
        self._num_button_menu_rect = Rect(
            self._num_button_menu_pos, self._num_button_menu_size
        )
        self._num_button_options = ["4B", "5B", "6B", "8B"]

        game_mode = self._pattern_drawer.get_game_mode()
        option_index = [4, 5, 6, 8].index(game_mode)
        starting_option = self._num_button_options[option_index]

        self._num_button_menu = UpdateableUIDropDownMenu(
            options_list=self._num_button_options,
            starting_option=starting_option,
            relative_rect=self._num_button_menu_rect,
            manager=self._manager,
        )

        self._toggle_auto_play_pos = (
            2 * self._underbox_padding + self._triple_width,
            self._underbox_top + self._line_height + 2 * self._underbox_padding,
        )
        self._toggle_auto_play_size = (self._triple_width, self._line_height)
        self._toggle_auto_play_rect = Rect(
            self._toggle_auto_play_pos, self._toggle_auto_play_size
        )
        self._toggle_auto_play_button = UIButton(
            relative_rect=self._toggle_auto_play_rect,
            text="Toggle Auto",
            manager=self._manager,
        )

        self._change_speed_button_width = self._triple_width // 4
        self._slower_button_pos = (
            3 * self._underbox_padding + 2 * self._triple_width,
            self._underbox_top + self._line_height + 2 * self._underbox_padding,
        )
        self._slower_button_size = (self._change_speed_button_width, self._line_height)
        self._slower_button_rect = Rect(
            self._slower_button_pos, self._slower_button_size
        )
        self._slower_button = UIButton(
            relative_rect=self._slower_button_rect,
            text="-",
            tool_tip_text="F3",
            manager=self._manager,
        )

        self._speed_button_pos = (
            3 * self._underbox_padding
            + 2 * self._triple_width
            + self._change_speed_button_width,
            self._underbox_top + self._line_height + 2 * self._underbox_padding,
        )
        self._speed_button_size = (self._triple_width // 2, self._line_height)
        self._speed_button_rect = Rect(self._speed_button_pos, self._speed_button_size)
        self._speed_button = UIButton(
            relative_rect=self._speed_button_rect,
            text="Speed",
            manager=self._manager,
        )

        note_speed = self._pattern_drawer.get_note_speed()
        self.set_note_speed(note_speed)

        self._faster_button_pos = (
            3 * self._underbox_padding
            + 2 * self._triple_width
            + 3 * self._change_speed_button_width,
            self._underbox_top + self._line_height + 2 * self._underbox_padding,
        )
        self._faster_button_size = (self._change_speed_button_width, self._line_height)
        self._faster_button_rect = Rect(
            self._faster_button_pos, self._faster_button_size
        )
        self._faster_button = UIButton(
            relative_rect=self._faster_button_rect,
            text="+",
            tool_tip_text="F4",
            manager=self._manager,
        )

        self._open_button_pos = (
            0 + self._underbox_padding,
            self._underbox_top + 2 * self._line_height + 3 * self._underbox_padding,
        )
        self._open_button_size = (self._full_width, self._line_height)
        self._open_button_rect = Rect(self._open_button_pos, self._open_button_size)
        self._open_button = UIButton(
            relative_rect=self._open_button_rect,
            text="Open",
            manager=self._manager,
        )
        self._file_selection_dialog = None
        self._last_valid_directory_path = None

        self._help_text_box = UITextBox(
            html_text="""
# Basic Shortcuts

F1: Print this help message
F2: Change keymap of active game mode
F3,F4: Change note drop speed
1,2: Change note drop speed
4,5,6,8: Change game mode among 4B/5B/6B/8B
ESC: Stop/Reset
ENTER,F5: Pause/Resume
UP,DOWN,LEFT,RIGHT: FastForward/Rewind
PGUP,PGDN: FastForward/Rewind (full page)
F6: Toggle auto-play

# Default Keymap

    L1    SIDEL    B1   B2   B3   B4   B5   B6   SIDER    R1
4B:       LSHIFT   A    S              ;    '    RSHIFT
5B:       LSHIFT   A    S    D    L    ;    '    RSHIFT
6B:       LSHIFT   A    S    D    L    ;    '    RSHIFT
8B: SPACE CAPSLOCK Q    W    E    PAD7 PAD8 PAD9 PAD_PLUS PAD0
            """.strip().replace(
                "\n", "<br/>"
            ),
            relative_rect=Rect(
                10,
                10,
                self._screen_width - 20,
                int(self._screen_height / 2),
            ),
            manager=self._manager,
        )

    def set_actions(self, actions):
        self._actions = actions

    def set_game_mode(self, game_mode):
        selected_option = "%dB" % game_mode
        self._num_button_menu.set_selected_option(selected_option)

    def set_note_speed(self, note_speed):
        self._speed_button.set_text("%.1f" % note_speed)

    def draw_help(self):
        if self._actions._showing_help:
            self._help_text_box.show()
        else:
            self._help_text_box.hide()

    def draw_button_setting_help(self):
        if self._actions._adding_button_mappings:
            button = self._actions._buttons_to_map[self._actions._button_index_to_map]

            font = self._actions._ui_manager._manager.ui_theme.get_font([])
            font_antialias = True
            font_size = 20
            font_color = Color(150, 150, 150)
            font_pos = (int(self._screen_width / 2), int(self._screen_height / 3))

            font = pygame.font.SysFont(font.name, font_size)
            help_message = "Press Key for %s" % button

            help_text = font.render(
                help_message,
                font_antialias,
                font_color,
            )
            self._screen.blit(
                help_text,
                help_text.get_rect(center=font_pos),
            )

    def on_tick_start(self):
        self._time_delta = self._clock.tick() / 1000.0

    def on_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self._play_pause_button:
                self._actions.pause_or_resume_play()
            elif event.ui_element == self._stop_button:
                self._actions.pause_or_stop_play()
            elif event.ui_element == self._backward_button:
                self._actions.rewind_backward_play()
            elif event.ui_element == self._forward_button:
                self._actions.fast_forward_play()
            elif event.ui_element == self._slower_button:
                self._actions.decrease_note_speed()
            elif event.ui_element == self._faster_button:
                self._actions.increase_note_speed()
            elif event.ui_element == self._toggle_auto_play_button:
                self._actions.toggle_auto_play()
            elif event.ui_element == self._open_button:
                if self._file_selection_dialog is None:
                    self._file_selection_dialog = FilteredUIFileDialog(
                        rect=Rect(0, 0, 300, 300),
                        allow_existing_files_only=True,
                        allow_picking_directories=False,
                        manager=self._manager,
                        initial_file_path=self._last_valid_directory_path,
                        predicate=lambda item: item.name.endswith(".pt"),
                    )
                elif self._file_selection_dialog.visible:
                    self._file_selection_dialog.hide()
                else:
                    self._file_selection_dialog.show()

            if self._file_selection_dialog is not None:
                if event.ui_element == self._file_selection_dialog.ok_button:
                    filename = self._file_selection_dialog.current_file_path
                    self._last_valid_directory_path = (
                        self._file_selection_dialog.last_valid_directory_path
                    )
                    self._file_selection_dialog = None
                    ptfile = PTFile.parse(filename)
                    ptfile_dir = os.path.dirname(filename)
                    self._actions.open_ptfile(ptfile, ptfile_dir)
                    self._actions.start_play()

        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self._num_button_menu:
                num_buttons = int(self._num_button_menu.selected_option[0])
                game_mode = GameMode(num_buttons)
                self._actions.set_game_mode(game_mode)

        elif event.type == pygame_gui.UI_WINDOW_CLOSE:
            if event.ui_element == self._file_selection_dialog:
                self._last_valid_directory_path = (
                    self._file_selection_dialog.last_valid_directory_path
                )
                self._file_selection_dialog = None

        self._manager.process_events(event)

    def on_tick(self):
        self._manager.update(self._time_delta)

    def on_draw(self):
        self._manager.draw_ui(self._screen)

        self.draw_help()
        self.draw_button_setting_help()


class GameInputHandler:
    def __init__(
        self,
        game_mode: GameMode,
        actions: Optional[GameActions] = None,
    ):
        self._game_mode = game_mode
        self._play_button_mapping = self._game_mode.get_button_mapping()
        self._ignore_play_keys = False

        self._actions = actions

    def set_game_mode(self, game_mode: GameMode):
        self._game_mode = game_mode
        self._play_button_mapping = self._game_mode.get_button_mapping()

    def set_ignore_play_keys(self, ignore):
        self._ignore_play_keys = ignore

    def set_actions(self, actions: GameAction):
        self._actions = actions

    def on_event(self, event):
        if not self._actions:
            return
        if event.type == pygame.KEYDOWN:
            if self._actions._adding_button_mappings:
                button_mapping = self._game_mode.get_button_mapping()
                button = self._actions._buttons_to_map[
                    self._actions._button_index_to_map
                ]
                button_mapping[event.key] = button
                self._actions._button_index_to_map += 1
                if self._actions._button_index_to_map == len(
                    self._actions._buttons_to_map
                ):
                    self._actions._adding_button_mappings = False
            elif event.key in [pygame.K_ESCAPE]:
                self._actions.pause_or_stop_play()
            elif event.key in [pygame.K_RETURN, pygame.K_F5]:
                self._actions.pause_or_resume_play()
            elif event.key in [pygame.K_UP, pygame.K_RIGHT, pygame.K_PAGEUP]:
                step = {pygame.K_UP: 0.5, pygame.K_RIGHT: 0.25, pygame.K_PAGEUP: 1.0}[
                    event.key
                ]
                self._actions.fast_forward_play(step)
            elif event.key in [pygame.K_DOWN, pygame.K_LEFT, pygame.K_PAGEDOWN]:
                step = {
                    pygame.K_DOWN: 0.5,
                    pygame.K_LEFT: 0.25,
                    pygame.K_PAGEDOWN: 1.0,
                }[event.key]
                self._actions.rewind_backward_play(step)
            elif event.key in [pygame.K_1, pygame.K_F3]:
                self._actions.decrease_note_speed()
            elif event.key in [pygame.K_2, pygame.K_F4]:
                self._actions.increase_note_speed()
            elif event.key in [pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_8]:
                game_mode = {
                    pygame.K_4: GameMode.FOUR,
                    pygame.K_5: GameMode.FIVE,
                    pygame.K_6: GameMode.SIX,
                    pygame.K_8: GameMode.EIGHT,
                }[event.key]
                self._actions.set_game_mode(game_mode)
            elif event.key in [pygame.K_F1]:
                self._actions._showing_help = True
            elif event.key in [pygame.K_F2]:
                self._actions.setup_button_mapping()
            elif event.key in [pygame.K_F6]:
                self._actions.toggle_auto_play()
            elif event.key in self._play_button_mapping:
                if not self._ignore_play_keys:
                    self._actions.play_button(
                        self._play_button_mapping[event.key],
                        GameButtonActionType.KEYDOWN,
                    )
        elif event.type == pygame.KEYUP:
            if event.key in self._play_button_mapping:
                if not self._ignore_play_keys:
                    self._actions.play_button(
                        self._play_button_mapping[event.key],
                        GameButtonActionType.KEYUP,
                    )
            elif event.key in [pygame.K_F1]:
                self._actions._showing_help = False


class Game:
    def __init__(self):
        pygame.mixer.pre_init(
            frequency=44100,
            size=-16,
            channels=2,
            buffer=512,
            allowedchanges=5,
        )
        pygame.init()
        pygame.display.set_caption("DirtJWax")

        self._game_mode = GameMode.FOUR
        self._note_speed = 5.0

        self._screen_manager = GameScreenManager()
        self._sequence_player = GameSequencePlayer()

        self._pattern_drawer = GamePatternDrawer(
            self._game_mode,
            self._note_speed,
            self._screen_manager,
            self._sequence_player,
        )
        self._ui_manager = GameUIManager(
            self._screen_manager,
            self._sequence_player,
            self._pattern_drawer,
        )

        self._pattern_player = GamePatternPlayer(
            self._sequence_player,
            self._screen_manager,
            self._ui_manager,
        )
        self._sequence_player.set_pattern_player(self._pattern_player)

        self._screen_manager.add_drawable(self._pattern_drawer)
        self._screen_manager.add_drawable(self._pattern_player)
        self._screen_manager.add_drawable(self._ui_manager)

        self._input_handler = GameInputHandler(
            self._game_mode,
        )

        self._actions = GameActions(
            self._sequence_player,
            self._pattern_drawer,
            self._ui_manager,
            self._pattern_player,
            self._input_handler,
        )

        self._ui_manager.set_actions(self._actions)
        self._input_handler.set_actions(self._actions)
        self._pattern_drawer.set_actions(self._actions)

        self._should_stop = False

    def set_game_mode(self, game_mode):
        self._actions.set_game_mode(game_mode)

    def set_note_speed(self, speed):
        self._actions.set_note_speed(speed)

    def start_play(self, filename):
        self._actions.start_play(filename)

    def on_tick(self):
        current_millis = pygame.time.get_ticks()

        self._sequence_player.on_tick_start(current_millis)
        self._ui_manager.on_tick_start()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._should_stop = True
                return

            self._input_handler.on_event(event)
            self._sequence_player.on_event(event)
            self._ui_manager.on_event(event)

        self._sequence_player.on_tick()
        self._ui_manager.on_tick()

        self._screen_manager.on_tick()
        self._screen_manager.on_tick_end()

    def main(self):
        while not self._should_stop:
            self.on_tick()

    def main_async(self):
        async def main():
            loop = asyncio.get_running_loop()

            async def handle_events(events):
                for event in events:
                    if event.type == pygame.QUIT:
                        self._should_stop = True

                    self._input_handler.on_event(event)
                    self._sequence_player.on_event(event)
                    self._ui_manager.on_event(event)

            async def tick_screen():
                self._ui_manager.on_tick()
                self._screen_manager.on_tick()

            async def tick_sequence_player():
                self._sequence_player.on_tick()

            while not self._should_stop:
                current_millis = pygame.time.get_ticks()

                self._sequence_player.on_tick_start(current_millis)
                self._ui_manager.on_tick_start()

                screen_drawed = loop.create_task(tick_screen())
                sequence_player_ticked = loop.create_task(tick_sequence_player())

                events = pygame.event.get()
                events = list(events)
                events_handled = loop.create_task(handle_events(events))

                await screen_drawed
                await loop.run_in_executor(None, self._screen_manager.on_tick_end)

                await sequence_player_ticked
                await events_handled

        asyncio.run(main())


@click.command(short_help="Play pt file.")
@click.argument(
    "filename",
    type=click.Path(),
    required=False,
)
def main(filename):
    game = Game()

    if filename:
        game.start_play(filename)

    game.main_async()


if __name__ == "__main__":
    main()
