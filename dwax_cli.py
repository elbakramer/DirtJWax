import sys
import json
import logging
import itertools

import click

from ptfile import PTFile, CachedPTFileDecryptor
from dwax_game import Game, GameMode

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)-8s: %(message)s",
)


@click.group()
def cli():
    pass


@cli.command(short_help="Play pt file.")
@click.argument(
    "filename",
    type=click.Path(),
    required=True,
)
@click.option(
    "--button",
    type=click.Choice(["4", "5", "6", "8"]),
    required=True,
)
@click.option(
    "--speed",
    metavar="SPEED",
    type=click.FloatRange(1.0, 9.0, clamp=True),
    default=5.0,
)
@click.option(
    "--unpack-cache-dir",
    type=click.Path(),
    default="unpack-cache",
    help="Directory for saving decrypted pt files.",
)
def play(filename, button, speed, unpack_cache_dir):
    if unpack_cache_dir:
        CachedPTFileDecryptor.set_cache_dir(unpack_cache_dir)

    num_button = int(button)
    game_mode = GameMode(num_button)
    game = Game()
    game.set_game_mode(game_mode)
    game.set_note_speed(speed)
    game.start_play(filename)
    game.main_async()


@cli.command(short_help="Dump pt file to json.")
@click.argument("src-filename", type=click.Path(), required=True)
@click.argument("dst-filename", type=click.Path(), required=True)
@click.option(
    "--unpack-cache-dir",
    type=click.Path(),
    default="unpack-cache",
    help="Directory for saving decrypted pt files.",
)
def dump(src_filename, dst_filename, unpack_cache_dir):
    if unpack_cache_dir:
        CachedPTFileDecryptor.set_cache_dir(unpack_cache_dir)

    if not dst_filename.endswith(".json"):
        dst_filename += ".json"

    def recursive_dict(value):
        if hasattr(value, "__dict__"):
            result = value.__dict__
            result = {k: recursive_dict(v) for k, v in result.items()}
            return result
        if isinstance(value, list):
            result = [recursive_dict(v) for v in value]
            return result
        return value

    ptfile = PTFile.parse(src_filename)
    ptfile_dict = recursive_dict(ptfile)

    with open(dst_filename, "w", encoding="utf-8") as f:
        json.dump(ptfile_dict, f, indent=2)


@cli.command(short_help="Compare two pt files.")
@click.argument("src-filename", type=click.Path(), required=True)
@click.argument("dst-filename", type=click.Path(), required=True)
@click.option(
    "--log-level",
    type=click.Choice(
        [
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
            "NOTSET",
        ],
        case_sensitive=False,
    ),
    default="WARNING",
    help="Loglevel of diffs.",
)
@click.option(
    "--unpack-cache-dir",
    type=click.Path(),
    default="unpack-cache",
    help="Directory for saving decrypted pt files.",
)
def diff(src_filename, dst_filename, log_level, unpack_cache_dir):
    if unpack_cache_dir:
        CachedPTFileDecryptor.set_cache_dir(unpack_cache_dir)

    logging.getLogger().setLevel(getattr(logging, log_level))

    src_ptfile = PTFile.parse(src_filename)
    dst_ptfile = PTFile.parse(dst_filename)

    src_header = src_ptfile.header
    dst_header = dst_ptfile.header

    if src_header.version_major != dst_header.version_major:
        logging.warning(
            "HEADER  UPDATE MAJOR_VERSION     %r => %r",
            src_header.version_major,
            dst_header.version_major,
        )

    if src_header.version_minor != dst_header.version_minor:
        logging.warning(
            "HEADER  UPDATE MINOR_VERSION     %r => %r",
            src_header.version_minor,
            dst_header.version_minor,
        )

    if src_header.ticks_per_measure != dst_header.ticks_per_measure:
        logging.warning(
            "HEADER  UPDATE TICKS_PER_MEASURE %r => %r",
            src_header.ticks_per_measure,
            dst_header.ticks_per_measure,
        )

    if src_header.master_bpm != dst_header.master_bpm:
        logging.warning(
            "HEADER  UPDATE MASTER_BPM        %r => %r",
            src_header.master_bpm,
            dst_header.master_bpm,
        )

    if src_header.number_of_tracks != dst_header.number_of_tracks:
        logging.warning(
            "HEADER  UPDATE NUMBER_OF_TRACKS  %r =>%r",
            src_header.number_of_tracks,
            dst_header.number_of_tracks,
        )

    if src_header.total_ticks != dst_header.total_ticks:
        logging.info(
            "HEADER  UPDATE TOTAL_TICKS       %r => %r",
            src_header.total_ticks,
            dst_header.total_ticks,
        )

    if src_header.time_in_seconds != dst_header.time_in_seconds:
        logging.info(
            "HEADER  UPDATE TIME_IN_SECONDS   %r => %r",
            src_header.time_in_seconds,
            dst_header.time_in_seconds,
        )

    if src_header.number_of_sounds != dst_header.number_of_sounds:
        logging.warning(
            "HEADER  UPDATE NUMBER_OF_SOUNDS  %r => %r",
            src_header.number_of_sounds,
            dst_header.number_of_sounds,
        )

    src_sounds = {sound.index: sound for sound in src_ptfile.sounds}
    dst_sounds = {sound.index: sound for sound in dst_ptfile.sounds}

    if src_header.number_of_sounds != dst_header.number_of_sounds:
        src_sounds_by_filename = {
            sound.filename: sound for sound in src_sounds.values()
        }
        dst_sounds_by_filename = {
            sound.filename: sound for sound in dst_sounds.values()
        }

        for src_sound_filename, src_sound in src_sounds_by_filename.items():
            if src_sound_filename not in dst_sounds_by_filename:
                logging.warning("SOUND   DELETE SOUND %r", src_sound)
            else:
                dst_sound = dst_sounds_by_filename[src_sound_filename]
                if src_sound != dst_sound:
                    logging.warning(
                        "SOUND   UPDATE SOUND %r => %r",
                        src_sound,
                        dst_sound,
                    )

    def parse_notes(ptfile):
        num_tracks = ptfile.header.number_of_tracks
        total_ticks = ptfile.header.total_ticks

        current_track_indices = [0 for i in range(num_tracks)]
        end_track_indices = [len(track.notes) for track in ptfile.tracks]

        notes = {}

        for tick_index in range(total_ticks):
            notes_at_tick = {}
            for track_index, track in enumerate(ptfile.tracks):
                current_track_index = current_track_indices[track_index]
                end_track_index = end_track_indices[track_index]
                while current_track_index < end_track_index:
                    note = track.notes[current_track_index]
                    if note.position == tick_index:
                        notes_at_tick.setdefault(track_index, []).append(note)
                        current_track_indices[track_index] += 1
                        current_track_index = current_track_indices[track_index]
                    else:
                        break
            if notes_at_tick:
                notes[tick_index] = notes_at_tick

        return notes

    src_notes_per_tick = parse_notes(src_ptfile)
    dst_notes_per_tick = parse_notes(dst_ptfile)

    src_beat = src_notes_per_tick[0][0][-1].params.beat
    dst_beat = dst_notes_per_tick[0][0][-1].params.beat

    max_total_ticks = max(src_header.total_ticks, dst_header.total_ticks)

    for tick_index in range(max_total_ticks):
        src_has_notes = tick_index in src_notes_per_tick
        dst_has_notes = tick_index in dst_notes_per_tick

        if not src_has_notes and not dst_has_notes:
            continue

        if src_has_notes and not dst_has_notes:
            src_notes_in_tick = src_notes_per_tick[tick_index]
            src_note_position = tick_index / (
                src_header.ticks_per_measure * src_beat / 4
            )
            logging.warning(
                "TRACK   TICK %d (%-3.3f)  DELETE TICK",
                tick_index,
                src_note_position,
            )
            for src_track_index, src_notes_in_track in src_notes_in_tick.items():
                for src_note in src_notes_in_track:
                    src_note_filename = "N/A"
                    if src_note.is_general():
                        src_note_filename = src_sounds[
                            src_note.params.sound_index
                        ].filename
                    logging.warning(
                        "TRACK   TICK %d (%-3.3f)  DELETE NOTE  DELETE TRACK INDEX %r (%s)",
                        tick_index,
                        src_note_position,
                        src_track_index,
                        src_note_filename,
                    )

        if not src_has_notes and dst_has_notes:
            dst_notes_in_tick = dst_notes_per_tick[tick_index]
            dst_note_position = tick_index / (
                dst_header.ticks_per_measure * dst_beat / 4
            )
            logging.warning(
                "TRACK   TICK %d (%-3.3f)  CREATE TICK",
                tick_index,
                dst_note_position,
            )
            for dst_track_index, dst_notes_in_track in dst_notes_in_tick.items():
                for dst_note in dst_notes_in_track:
                    dst_note_filename = "N/A"
                    if dst_note.is_general():
                        dst_note_filename = dst_sounds[
                            dst_note.params.sound_index
                        ].filename
                    logging.warning(
                        "TRACK   TICK %d (%-3.3f)  CREATE NOTE  CREATE TRACK INDEX %r (%s)",
                        tick_index,
                        dst_note_position,
                        dst_track_index,
                        dst_note_filename,
                    )

        if src_has_notes and dst_has_notes:
            src_notes_in_tick = src_notes_per_tick[tick_index]
            dst_notes_in_tick = dst_notes_per_tick[tick_index]

            src_note_set = set(
                itertools.chain.from_iterable(src_notes_in_tick.values())
            )
            dst_note_set = set(
                itertools.chain.from_iterable(dst_notes_in_tick.values())
            )

            track_per_src_note = {
                note: index
                for index, notes in src_notes_in_tick.items()
                for note in notes
            }
            track_per_dst_note = {
                note: index
                for index, notes in dst_notes_in_tick.items()
                for note in notes
            }

            if src_note_set == dst_note_set:
                pass

            src_only_notes = src_note_set - dst_note_set
            dst_only_notes = dst_note_set - src_note_set
            both_notes = src_note_set & dst_note_set
            all_notes = src_note_set | dst_note_set

            src_similar_notes = {}
            dst_similar_notes = {}

            similar_note_pairs = []

            for src_note in src_note_set:
                for dst_note in dst_note_set:
                    if src_note.is_equal_except_duration(dst_note):
                        src_similar_notes.setdefault(src_note, []).append(dst_note)
                        dst_similar_notes.setdefault(dst_note, []).append(src_note)
                        similar_note_pair = (src_note, dst_note)
                        similar_note_pairs.append(similar_note_pair)

            for note in all_notes:
                src_has_note = note in src_note_set
                dst_has_note = note in dst_note_set

                if not dst_has_note:
                    src_note = note
                    src_note_position = tick_index / (
                        src_header.ticks_per_measure * src_beat / 4
                    )
                    src_note_filename = "N/A"
                    if src_note.is_general():
                        src_note_filename = src_sounds[
                            src_note.params.sound_index
                        ].filename

                    src_track_index = track_per_src_note[src_note]
                    src_duration = src_note.params.duration

                    similar_notes_to_dst = src_similar_notes.get(note)
                    if similar_notes_to_dst:
                        for dst_note in similar_notes_to_dst:
                            dst_track_index = track_per_dst_note[dst_note]
                            if src_track_index != dst_track_index:
                                logging.info(
                                    "TRACK   TICK %d (%-3.3f)  UPDATE NOTE  UPDATE TRACK INDEX %r => %r (%s)",
                                    tick_index,
                                    src_note_position,
                                    src_track_index,
                                    dst_track_index,
                                    src_note_filename,
                                )
                            if note.is_general():
                                dst_duration = dst_note.params.duration
                                if src_duration != dst_duration:
                                    logging.info(
                                        "TRACK   TICK %d (%-3.3f)  UPDATE NOTE  UPDATE NOTE DURATION %r => %r (%s)",
                                        tick_index,
                                        src_note_position,
                                        src_duration,
                                        dst_duration,
                                        src_note_filename,
                                    )
                    else:
                        logging.warning(
                            "TRACK   TICK %d (%-3.3f)  DELETE NOTE  DELETE TRACK INDEX %r (%s)",
                            tick_index,
                            src_note_position,
                            src_track_index,
                            src_note_filename,
                        )
                elif not src_has_note:
                    dst_note = note
                    dst_note_position = tick_index / (
                        dst_header.ticks_per_measure * dst_beat / 4
                    )
                    dst_note_filename = "N/A"
                    if dst_note.is_general():
                        dst_note_filename = dst_sounds[
                            dst_note.params.sound_index
                        ].filename

                    dst_track_index = track_per_dst_note[dst_note]
                    dst_duration = dst_note.params.duration

                    similar_notes_from_src = dst_similar_notes.get(note)
                    if similar_notes_from_src:
                        for src_note in similar_notes_from_src:
                            src_track_index = track_per_src_note[src_note]
                            if src_track_index != dst_track_index:
                                logging.info(
                                    "TRACK   TICK %d (%-3.3f)  UPDATE NOTE  UPDATE TRACK INDEX %r => %r (%s)",
                                    tick_index,
                                    dst_note_position,
                                    src_track_index,
                                    dst_track_index,
                                    dst_note_filename,
                                )
                            if note.is_general():
                                src_duration = src_note.params.duration
                                if src_duration != dst_duration:
                                    logging.info(
                                        "TRACK   TICK %d (%-3.3f)  UPDATE NOTE  UPDATE NOTE DURATION %r => %r (%s)",
                                        tick_index,
                                        dst_note_position,
                                        src_duration,
                                        dst_duration,
                                        dst_note_filename,
                                    )
                    else:
                        logging.warning(
                            "TRACK   TICK %d (%-3.3f)  CREATE NOTE  CREATE TRACK INDEX %r (%s)",
                            tick_index,
                            dst_note_position,
                            dst_track_index,
                            dst_note_filename,
                        )
                else:
                    src_note_position = tick_index / (
                        src_header.ticks_per_measure * src_beat / 4
                    )
                    dst_note_position = tick_index / (
                        dst_header.ticks_per_measure * dst_beat / 4
                    )

                    src_note_filename = "N/A"
                    dst_note_filename = "N/A"

                    if note.is_general():
                        src_note_filename = src_sounds[note.params.sound_index].filename
                        dst_note_filename = dst_sounds[note.params.sound_index].filename

                    src_track_index = track_per_src_note[note]
                    dst_track_index = track_per_dst_note[note]

                    if src_track_index != dst_track_index:
                        logging.info(
                            "TRACK   TICK %d (%-3.3f)  UPDATE NOTE  UPDATE TRACK INDEX %r => %r (%s)",
                            tick_index,
                            src_note_position,
                            src_track_index,
                            dst_track_index,
                            src_note_filename,
                        )


if __name__ == "__main__":
    cli()
