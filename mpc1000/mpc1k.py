#!/usr/bin/env python3
"""
load, edit, and export Akai MPC 1000 program file data
"""

__version__ = '0.2'
__author__ = 'Stephen Norum <stephen@mybunnyhug.org>'
# http://www.mybunnyhug.org/


import sys
import struct
import bz2
import base64
import re

__all__ = ('Program', 'Pad', 'Sample', 'DEFAULT_PGM_DATA')

attr_value_sep = ' = '
attr_value_fmt = attr_value_sep.join(('{0}', '{1}'))

def indent(string, amount=4):
    line_start = re.compile(r'^', re.MULTILINE)
    return re.sub(line_start, ' ' * amount, string)

DEFAULT_PGM_DATA_BZ2_B64 = '''
QlpoOTFBWSZTWdr3EiAABa3/xH////////////////QAAECAQAABMAE4RBpSTNpQ
wIaGCbQmj0BHk0NNCMBoEG1PRAMCZMcADQGgaABppkABo0yADRkwQGIAACqSRNMg
CaZkTCYjIaNGNCYAjIyGCYjE8oaep6aWAFkDLmgEwEaM6IiInoAUgMaZACqBnzQC
jIBSAkBKUQERMpOEAoLaiBo26dpTAYsgKnomgCnUqYVPBoVJYtX1Y88D3SgEZNX0
+aH2c1tNGYrOdERESqKEv0SPAAA7pSmRV7R71HlLEq0txUluNahUoKS0Ha/JALtQ
bN15uFu5qgAAf4NJXs+Cfi2sA1k9K0a2Lgui8GD74TBYNp2XGcaC9mAAAEkRERHe
bJvJyyzkUaqtZc0SVmYzPz19nb+q1f9/z+93+sf+zTArgS2QJRWAtJkAWZWngLuS
KcKEhte4kQA=
'''

DEFAULT_PGM_DATA = bz2.decompress(base64.b64decode(DEFAULT_PGM_DATA_BZ2_B64))

def indented_byte_list_string(byte_list, indent_amount=0, items_per_row=8):
    """
    Return an indented multi-line string representation of a byte list.
    """
    str_list = []
    sub_str_list = []

    indent_amount = int(indent_amount)

    if indent_amount > 0:
        indent_spaces = ' ' * indent_amount
    else:
        indent_spaces = ''

    indent_string = ''.join(('\n', indent_spaces))

    for byte in byte_list:
        sub_str_list.append('{0:02X}'.format(byte))
        if len(sub_str_list) == items_per_row:
            str_list.append(' '.join(sub_str_list))
            sub_str_list = []

    if sub_str_list:
        str_list.append(' '.join(sub_str_list))

    return ''.join((indent_spaces, indent_string.join(str_list)))

def pass_validator(value):
    return value

def int_in_range_validator(lower, upper):
    def f(value):
        value = int(value)
        if value < lower or value > upper:
            raise ValueError('out of range ({0} to {1}): {2!r}'.format(lower, upper, value))
        return value
    return f

def sample_name_validator(value):
    valid_name_characters = (
        b"abcdefghijklmnopqrstuvwxyz"
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        b"1234567890"
        b"!#$%&'()-@_{} \x00"
    )
    try:
        value = value.encode("utf-8")
    except AttributeError:
        pass
    if len(value) > 16:
        raise ValueError(f'string too long {value!r}')
    for c in value:
        if c not in valid_name_characters:
            raise ValueError('invalid character: {0!r}'.format(c))
    return value

def setter_factory(name, validator):
    def f(self, val):
        val = validator(val)
        setattr(self, '_' + name, val)
    return f

def getter_factory(name):
    def f(self):
        return getattr(self, '_' + name)
    return f

def class_factory(class_name='', format='', doc='', format_attrs=None, additional_attrs=None, **kwarg):
    dct = {}
    dct['format'] = format
    dct['__doc__'] = doc
    dct['size'] = struct.calcsize(format)
    dct['format_attrs'] = format_attrs or []
    dct['additional_attrs'] = additional_attrs or []

    def unpack(self, data_str=None):
        unpacked_data = struct.unpack(self.format, data_str[0:struct.calcsize(self.format)])
        for i, val in enumerate(unpacked_data):
            setattr(self, self.format_attrs[i][0], val)
    dct['unpack'] = unpack

    def format_str(self):
        out = []
        for name, unused_validator in self.format_attrs:
            out.append(attr_value_fmt.format(name, getattr(self, name)))
        return '\n'.join(out)
    dct['format_str'] = format_str

    def pack(self):
        vals = [getattr(self, a[0]) for a in self.format_attrs]
        return struct.pack(self.format, *vals)
    dct['pack'] = pack

    for attr_name, validator in dct['format_attrs']:
        g = getter_factory(attr_name)
        s = setter_factory(attr_name, validator)
        dct[attr_name] = property(g, s)

    for attr_name, validator in dct['additional_attrs']:
        g = getter_factory(attr_name)
        s = setter_factory(attr_name, validator)
        dct[attr_name] = property(g, s)

    dct['__init__'] = unpack
    dct['__str__'] = format_str
    dct['data'] = property(pack)

    dct.update(kwarg)
    return type(class_name, (object,), dct)

Sample = class_factory(
    class_name = 'Sample',
    doc = 'MPC 1000 Sample',
    format = (
        '<'   # Little-endian
        '16s' # Sample Name
        'x'   # Padding
        'B'   # Level
        'B'   # Range Upper
        'B'   # Range Lower
        'h'   # Tuning
        'B'   # Play Mode       0="One Shot", 1="Note On"
        'x'   # Padding
    ),
    format_attrs = (
        ('sample_name', sample_name_validator),
        ('level',       int_in_range_validator(0, 100)),
        ('range_upper', int_in_range_validator(0, 127)),
        ('range_lower', int_in_range_validator(0, 127)),
        ('tuning',      int_in_range_validator(-3600, 3600)),
        ('play_mode',   int_in_range_validator(0, 1)),
    ),
)

pad_format = (
    '<'     #  Little-endian
    '2x'    #  Padding
    'b'     #  Voice Overlap    0="Poly", 1="Mono"
    'b'     #  Mute Group       0="Off", 1 to 32
    'x'     #  Padding
    'B'     #  Unknown
    'B'     #  Attack
    'B'     #  Decay
    'B'     #  Decay Mode       0="End", 1="Start"
    '2x'    #  Padding
    'B'     #  Velocity to Level
    '5x'    #  Padding
    'b'     #  Filter 1 Type    0="Off", 1="Lowpass", 2="Bandpass", 3="Highpass"
    'B'     #  Filter 1 Freq
    'B'     #  Filter 1 Res
    '4x'    #  Padding
    'B'     #  Filter 1 Velocity to Frequency
    'B'     #  Filter 2 Type    0="Off", 1="Lowpass", 2="Bandpass", 3="Highpass", 4="Link"
    'B'     #  Filter 2 Freq
    'B'     #  Filter 2 Res
    '4x'    #  Padding
    'B'     #  Filter 2 Velocity to Frequency
    '14x'   #  Padding
    'B'     #  Mixer Level
    'B'     #  Mixer Pan    0 to 49=Left, 50=Center, 51 to 100=Right
    'B'     #  Output       0="Stereo", 1="1-2", 2="3-4"
    'B'     #  FX Send      0="Off", 1="1", 2="2"
    'B'     #  FX Send Level
    'B'     #  Filter Attenuation   0="0dB", 1="-6dB", 2="-12dB"
    '15x'   #  Padding
)

pad_format_attrs = (
    ("voice_overlap",           int_in_range_validator(0, 1)),
    ("mute_group",              int_in_range_validator(0, 32)),
    ("unknown",                 int_in_range_validator(0, 255)),
    ("attack",                  int_in_range_validator(0, 100)),
    ("decay",                   int_in_range_validator(0, 100)),
    ("decay_mode",              int_in_range_validator(0, 1)),
    ("vel_to_level",            int_in_range_validator(0, 100)),
    ("filter_1_type",           int_in_range_validator(0, 3)),
    ("filter_1_freq",           int_in_range_validator(0, 100)),
    ("filter_1_res",            int_in_range_validator(0, 100)),
    ("filter_1_vel_to_freq",    int_in_range_validator(0, 100)),
    ("filter_2_type",           int_in_range_validator(0, 4)),
    ("filter_2_freq",           int_in_range_validator(0, 100)),
    ("filter_2_res",            int_in_range_validator(0, 100)),
    ("filter_2_vel_to_freq",    int_in_range_validator(0, 100)),
    ("mixer_level",             int_in_range_validator(0, 100)),
    ("mixer_pan",               int_in_range_validator(0, 100)),
    ("output",                  int_in_range_validator(0, 2)),
    ("fx_send",                 int_in_range_validator(0, 2)),
    ("fx_send_level",           int_in_range_validator(0, 100)),
    ("filter_attenuation",      int_in_range_validator(0, 2)),
)

def pad_init(self, data):
    self.samples = []
    offset = 0
    for i in range(0, 4):
        s = Sample(data[offset:])
        self.samples.append(s)
        offset += Sample.size
    self.unpack(data[offset:])

def pad_str(self):
    out = [self.format_str()]
    for i, s in enumerate(self.samples):
        out.append(f'Sample {i}:')
        out.append(indent(str(s)))
    return '\n'.join(out)

def pad_data(self):
    data_str_list = [s.data for s in self.samples]
    data_str_list.append(self.pack())
    return b''.join(data_str_list)

Pad = class_factory(
    class_name = 'Pad',
    doc = 'MPC 1000 Pad',
    format = pad_format,
    format_attrs = pad_format_attrs,
    additional_attrs = (
        ("midi_note", int_in_range_validator(0, 127)),
        ("samples", pass_validator),
    ),
    size = struct.calcsize(pad_format) + 4 * Sample.size,
    __init__ = pad_init,
    __str__ = pad_str,
    data = property(pad_data),
)

program_format = (
    '<'   #  Little-endian
    'B'   #  MIDI Program Change   0="Off", 1 to 128
    'B'   #  Slider 1 Pad
    'B'   #  Unknown
    'B'   #  Slider 1 Parameter    0="Tune", 1="Filter", 2="Layer", 3="Attack", 4="Decay"
    'b'   #  Slider 1 Tune Low
    'b'   #  Slider 1 Tune High
    'b'   #  Slider 1 Filter Low
    'b'   #  Slider 1 Filter High
    'B'   #  Slider 1 Layer Low
    'B'   #  Slider 1 Layer High
    'B'   #  Slider 1 Attack Low
    'B'   #  Slider 1 Attack High
    'B'   #  Slider 1 Decay Low
    'B'   #  Slider 1 Decay High
    'B'   #  Slider 2 Pad
    'B'   #  Unknown
    'B'   #  Slider 2 Parameter    0="Tune", 1="Filter", 2="Layer", 3="Attack", 4="Decay"
    'b'   #  Slider 2 Tune Low
    'b'   #  Slider 2 Tune High
    'b'   #  Slider 2 Filter Low
    'b'   #  Slider 2 Filter High
    'B'   #  Slider 2 Layer Low
    'B'   #  Slider 2 Layer High
    'B'   #  Slider 2 Attack Low
    'B'   #  Slider 2 Attack High
    'B'   #  Slider 2 Decay Low
    'B'   #  Slider 2 Decay High
    '17x' #  Padding
)

program_format_attrs = (
    ('midi_program_change'  , int_in_range_validator(0, 128)),
    ('slider_1_pad'         , int_in_range_validator(0, 63)),
    ('slider_1_unknown'     , int_in_range_validator(0, 255)),
    ('slider_1_parameter'   , int_in_range_validator(0, 4)),
    ('slider_1_tune_low'    , int_in_range_validator(-120, 120)),
    ('slider_1_tune_high'   , int_in_range_validator(-120, 120)),
    ('slider_1_filter_low'  , int_in_range_validator(-50, 50)),
    ('slider_1_filter_high' , int_in_range_validator(-50, 50)),
    ('slider_1_layer_low'   , int_in_range_validator(0, 127)),
    ('slider_1_layer_high'  , int_in_range_validator(0, 127)),
    ('slider_1_attack_low'  , int_in_range_validator(0, 100)),
    ('slider_1_attack_high' , int_in_range_validator(0, 100)),
    ('slider_1_decay_low'   , int_in_range_validator(0, 100)),
    ('slider_1_decay_high'  , int_in_range_validator(0, 100)),
    ('slider_2_pad'         , int_in_range_validator(0, 63)),
    ('slider_2_unknown'     , int_in_range_validator(0, 255)),
    ('slider_2_parameter'   , int_in_range_validator(0, 4)),
    ('slider_2_tune_low'    , int_in_range_validator(-120, 120)),
    ('slider_2_tune_high'   , int_in_range_validator(-120, 120)),
    ('slider_2_filter_low'  , int_in_range_validator(-50, 50)),
    ('slider_2_filter_high' , int_in_range_validator(-50, 50)),
    ('slider_2_layer_low'   , int_in_range_validator(0, 127)),
    ('slider_2_layer_high'  , int_in_range_validator(0, 127)),
    ('slider_2_attack_low'  , int_in_range_validator(0, 100)),
    ('slider_2_attack_high' , int_in_range_validator(0, 100)),
    ('slider_2_decay_low'   , int_in_range_validator(0, 100)),
    ('slider_2_decay_high'  , int_in_range_validator(0, 100)),
)

def program_init(self, data=None):
    if data is None:
        data = DEFAULT_PGM_DATA

    offset = 0

    # Header
    fmt = self.addl_formats['header']
    size = struct.calcsize(fmt)
    unpacked_data = struct.unpack(fmt, data[offset:offset+size])
    self.file_size = unpacked_data[0]
    self.file_type = unpacked_data[1]
    offset += size

    # Pads and samples
    size = Pad.size
    self.pads = []
    for i in range(0, 64):
        p = Pad(data[offset:offset+size])
        self.pads.append(p)
        offset += size

    # Pad MIDI Note data
    fmt = self.addl_formats['pad_midi_note']
    size = struct.calcsize(fmt)
    pad_midi_notes = struct.unpack(fmt, data[offset:offset+size])
    for i, p in enumerate(pad_midi_notes):
        self.pads[i].midi_note = p
    offset += size

    # MIDI Note Pad data
    fmt = self.addl_formats['midi_note_pad']
    size = struct.calcsize(fmt)
    midi_note_pads = struct.unpack(fmt, data[offset:offset+size])
    # Ignore MIDI Note Pad data -- already have data from Pad MIDI Note data
    offset += size

    self.unpack(data[offset:])

def program_str(self):
    out = []
    for a in ('file_size', 'file_type'):
        print(attr_value_fmt.format(a, getattr(self, a)))

    for a in ('pad_midi_notes', 'midi_note_pads'):
        val = indented_byte_list_string(getattr(self, a), len(a) + len(attr_value_sep)).strip()
        print(attr_value_fmt.format(a, val))

    out.append(self.format_str())
    for i, s in enumerate(self.pads):
        out.append('Pad {0}:'.format(i))
        out.append(indent(str(s)))
    return '\n'.join(out)

def program_data(self):
    header_str = struct.pack(self.addl_formats['header'], self.file_size, self.file_type)
    pad_midi_note_str = struct.pack(self.addl_formats['pad_midi_note'], *(self.pad_midi_notes))
    midi_note_pad_str = struct.pack(self.addl_formats['midi_note_pad'], *(self.midi_note_pads))
    midi_and_sliders_str = self.pack()

    pad_data_str_list = [p.data for p in self.pads]

    data_str_list = [header_str]
    data_str_list.extend(pad_data_str_list)
    data_str_list.extend([pad_midi_note_str, midi_note_pad_str, midi_and_sliders_str])

    return b''.join(data_str_list)

def program_pad_midi_notes(self):
    """
    List of MIDI note numbers (Range: 0 to 127) associated with pads
    """
    return [p.midi_note for p in self.pads]

def program_midi_note_pads(self):
    """
    List of pad numbers (Range: 0 to 63, no pad=64) associated with MIDI notes
    """
    mnpl = [64,] * 128
    for i, p in enumerate(self.pads):
        mnpl[p.midi_note] = i
    return mnpl

Program = class_factory(
    class_name = 'Program',
    doc = 'MPC 1000 Program',
    format = program_format,
    format_attrs = program_format_attrs,
    addl_formats = {
        'header': '<Hxx16s4x',
        'pad_midi_note': '<64B',
        'midi_note_pad': '<128B',
    },
    __init__ = program_init,
    __str__ = program_str,
    data = property(program_data),
    pad_midi_notes = property(program_pad_midi_notes),
    midi_note_pads = property(program_midi_note_pads),
)

def main():
    pgm_data_str = DEFAULT_PGM_DATA

    pgm = Program(pgm_data_str)

    if pgm:
        print('Program loaded')
    else:
        print('Program failed to load')
        return 1

    pgm_data = pgm.data

    if pgm_data == pgm_data_str:
        print('Program data matches original')
        print(repr(pgm_data))
    else:
        print('Program data differs from original')
        print(repr(pgm_data))
        return 2

    return 0

if __name__ == '__main__':
    status = main()
    sys.exit(status)
