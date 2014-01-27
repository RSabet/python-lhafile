# -*- coding:utf-8 -*-
# Copyright (c) 2010 Hidekazu Ohnishi.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#
#    * Neither the name of the author nor the names of its contributors
#      may be used to endorse or promote products derived from this
#      software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""Lhafile, extension extract lzh file.

Its interface is likey zipfile module is include in regular python environment.
"""

import cStringIO
import datetime
import os
import os.path
import struct
import sys

import lzhlib
crc16 = lzhlib.crc16

def is_lhafile(filename):
    try:
        Lhafile(filename)
    except:
        return False
    return True

class BadLhafile(Exception):
    pass

class LhaInfo(object):
    __slots__ = (
        'orig_filename',
        'filename',
        'directory',
        'date_time',
        'compress_type',
        'comment',
        'extra',
        'create_system',
        'create_version',
        'extract_version',
        'reserved',
        'flag_bits',
        'volume',
        'internal_attr',
        'external_attr',
        'header_offset',
        'file_offset',
        'CRC',
        'compress_size',
        'file_size',
        )

    def __init__(self):
        self.orig_filename = None
        self.filename = None
        self.directory = None
        self.date_time = None
        self.compress_type = None
        self.comment = None
        self.extra = None
        self.create_system = None
        self.create_version = None
        self.extract_version = None
        self.reserved = None
        self.flag_bits = None
        self.volume = None
        self.internal_attr = None
        self.external_attr = None
        self.header_offset = None
        self.file_offset = None
        self.CRC = None
        self.compress_size = None
        self.file_size = None
    
    def __str__(self):
        return '%s %s %08X %d %04X' % (self.filename, self.file_size, 
                                       self.file_offset, self.compress_size, self.CRC)
    
    def __getstate__(self):
        return (self.orig_filename, self.filename, self.directory, self.date_time,
                self.compress_type, self.comment, self.extra, self.create_system,
                self.create_version, self.extract_version, self.reserved,
                self.flag_bits, self.volume, self.internal_attr, self.external_attr,
                self.header_offset, self.file_offset, self.CRC, self.compress_size,
                self.file_size)

    def __setstate__(self, state):
        (self.orig_filename, self.filename, self.directory, self.date_time,
         self.compress_type, self.comment, self.extra, self.create_system,
         self.create_version, self.extract_version, self.reserved,
         self.flag_bits, self.volume, self.internal_attr, self.external_attr,
         self.header_offset, self.file_offset, self.CRC, self.compress_size,
         self.file_size) = state


class Lhafile:
    """
    """

    SUPPORTED_COMPRESS_TYPE = ('-lhd-', '-lh0-', '-lh5-', '-lh6-', '-lh7-');

    def __init__(self, file, mode="r", compression=None, callback=None, args=None):
        """ Open the LZH file """
        self.filelist = []
        self.NameToInfo = {}
        self.mode = key = mode.replace('b', '')[0]
        
        if isinstance(file, basestring):
            self._fileParsed = 0
            self.filename = file
            modeDict = {'r' : 'rb'}
            self.fp = open(file, modeDict[mode])
        else:
            self._fileParsed = 1
            self.fp = file
            self.filename = getattr(file, 'name', None)

        # Get file size
        initial_pos = self.fp.tell()
        self.fp.seek(0, 2)
        self.filesize = self.fp.tell()
        self.fp.seek(initial_pos, 0)
    
        if key == 'r':
            self._GetContents(callback=callback,args=args)
        else:
            if not self._fileParsed:
                self.fp.close()
                self.fp = None
            raise RuntimeError, 'Mode must be "r"'

    def _GetContents(self, callback=None, args=None):
        try:
            info = self._RealGetContent()
            while info:
                if not info.compress_type in Lhafile.SUPPORTED_COMPRESS_TYPE:
                    raise RuntimeError, "Unsupported file is contained %s" % (info.compress_type,)
                if callback:
                    callback(args, self.fp.tell(), self.filesize, info)
                self.filelist.append(info)
                self.NameToInfo[info.filename] = info
                info = self._RealGetContent()
        except BadLhafile, e:
            raise
            if not self._fileParsed:
                self.fp.close()
                self.fp = None

    def _RealGetContent(self):
        fp = self.fp
        filesize = self.filesize
        initial_pos = fp.tell()
        is_read = lambda x: fp.tell() + (x) < filesize
        if fp.tell() == filesize - 1:
            return None
        if not is_read(26):
            raise BadLhafile, "Header is broken"
        # Check OS level
        os_level = ord(fp.read(21)[20])
        fp.seek(-21, 1)
        if not os_level in (0, 1, 2):
            raise BadLhafile, "this file level is out of support range %d" % os_level
        if os_level in (0, 1):
            header_size, checksum, signature, skip_size, \
            file_size, modify_time, reserved , os_level, \
            filename_length = struct.unpack('<BB5sII4sBBB', fp.read(22))
            if is_read(filename_length + 2):
                filename, crc = struct.unpack('<%dsH' % filename_length, fp.read(filename_length + 2))
            if os_level == 0:
                ext_header_size = 0
                pass
            elif os_level == 1:
                extra_data_size = header_size - (5+4+4+2+2+1+1+1+filename_length+2+1+2)
                os_identifier, extra_data, ext_header_size \
                = struct.unpack('<c%dsH' % extra_data_size, fp.read(1 + extra_data_size + 2))
            sum_ext_header_size = 0
            directory = None
            comment = None
            compress_size = skip_size - sum_ext_header_size
        elif os_level == 2:
            header = fp.read(26)
            all_header_size, signature, compress_size, file_size, \
            modify_time, reserved, os_level, crc, os_identifier, \
            ext_header_size = struct.unpack('<H5sIIIBBHBH', header)
            sum_ext_header_size = 0
            directory = None
            comment = None
        while ext_header_size != 0:
            sum_ext_header_size += ext_header_size
            if not is_read(ext_header_size):
                raise BadLhafile, "File is broken"
            (ext,) = struct.unpack('<B', fp.read(1))
            if ext == 0x00:
                # Common header
                dummy, ext_header_size \
                       = struct.unpack('<%dsH' % (ext_header_size - 3), fp.read(ext_header_size-1))
            elif ext == 0x01:
                # Filename header
                filename, ext_header_size \
                          = struct.unpack('<%dsH' % (ext_header_size - 3), fp.read(ext_header_size-1))
            elif ext == 0x02:
                # Directory name header
                directory, ext_header_size \
                           = struct.unpack('<%dsH' % (ext_header_size - 3), fp.read(ext_header_size-1))
            elif ext == 0x3F:
                # Comment header
                comment, ext_header_size \
                         = struct.unpack('<%dsH' % (ext_header_size - 3), fp.read(ext_header_size-1))
            elif ext == 0x40:
                # Attribute Header
                if not ext_header_size == 5:
                    raise BadLhafile, "file is broken"
                attr, ext_header_size \
                    = struct.unpack('<HH', fp.read(4))
            else:
                # Skip the other
                dummy, ext_header_size \
                       = struct.unpack('<%dsH' % (ext_header_size - 3), fp.read(ext_header_size-1))
        # skip to next header
        file_offset = fp.tell()
        if os_level in (0, 1):
            compress_size = skip_size - sum_ext_header_size
        if not is_read(compress_size):
            raise BadLhafile, "Compress data is too short"
        fp.seek(compress_size, 1)
        # modify_time
        if os_level in (0, 1):
            year = (ord(modify_time[3]) >> 1) + 1980
            month = ((ord(modify_time[3]) << 8 | ord(modify_time[2])) >> 5) & 0x0F
            day  = ord(modify_time[2]) & 0x1F
            hour = ord(modify_time[1]) >> 3
            minute = ((ord(modify_time[1]) << 8 | ord(modify_time[0])) >> 5) & 0x2F
            second = (ord(modify_time[0]) & 0x1F) * 2
            date_time = datetime.datetime(year, month, day, hour, minute, second)
            create_time = date_time
        elif os_level in (2,):
            dummy_date = datetime.datetime(1970,1,1)
            date_time = dummy_date.fromtimestamp(modify_time)
            create_time = date_time
        info = LhaInfo()
        if directory is None:
            # for lhaplus archive
            sjisname = unicode(filename, 'cp932')
            if '\\' in sjisname:
                sjispath = [s.encode('cp932') for s in sjisname.split(u'\\')]
                filename = os.sep.join(sjispath)
                directory = os.sep.join(sjispath[:-1])
        else:
            directory = os.sep.join(directory.split('\xff'))
            filename = os.path.join(directory, filename)
        info.directory = directory
        info.filename = filename
        info.compress_size = compress_size
        info.file_size = file_size
        info.CRC = crc
        info.header_offset = initial_pos
        info.file_offset = file_offset
        info.external_attr = None
        info.internal_attr = None
        info.reserved = 0
        info.comment = comment
        info.compress_type = signature
        info.date_time = date_time
        return info

    def lhaname(self):
        return self.filename
    
    def namelist(self):
        if self.filelist: 
            return [d.filename for d in self.filelist \
                    if d.compress_type in Lhafile.SUPPORTED_COMPRESS_TYPE]
        return None

    def infolist(self):
        return self.filelist

    def read(self, name):
        """Return file bytes (as a string) for 'name'. """
        if not self.fp:
            raise RuntimeError, \
                  "Attempt to read LZH archive that was already closed"
        info = self.NameToInfo[name]
        if info.compress_type in Lhafile.SUPPORTED_COMPRESS_TYPE:
            self.fp.seek(info.file_offset)
            fin = cStringIO.StringIO(self.fp.read(info.compress_size))
            fout = cStringIO.StringIO()
            try:
                session = lzhlib.LZHDecodeSession(fin, fout, info)
                while session.do_next() == False:
                    pass
                outsize = session.output_pos
                crc = session.crc16
            except Exception, e:
                raise e
            if outsize != info.file_size:
                raise BadLhafile, "%s output_size is not matched %d/%d %s" % \
                    (name, outsize, info.file_size, info.compress_type)
            if crc != info.CRC:
                raise BadLhafile, "crc is not matched"

            fout.seek(0)
            bytes = fout.read()
        elif info.commpress_type == '-lhd-':
            raise RuntimeError, \
                  "name is directory"
        else:
            raise RuntimeError, \
                  "Unsupport format"
        return bytes
   
