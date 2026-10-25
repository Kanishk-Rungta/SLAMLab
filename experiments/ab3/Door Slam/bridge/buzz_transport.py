"""Lossless padding removal for the official fixed-size Buzz TCP frames."""
import struct


def compact(frame):
    if len(frame) < 4:
        raise ValueError('Short Buzz frame')
    offset = 2  # native uint16 robot ID; x86 runtime is little endian
    while offset+2 <= len(frame):
        size = struct.unpack_from('<H', frame, offset)[0]
        offset += 2
        if size == 0:
            return frame[:offset]
        if offset+size > len(frame):
            raise ValueError('Invalid Buzz message length')
        offset += size
    return frame[:offset]


def expand(packet, size):
    if len(packet) > size or len(packet) < 4:
        raise ValueError('Invalid compact Buzz frame')
    return packet + b'\0'*(size-len(packet))
