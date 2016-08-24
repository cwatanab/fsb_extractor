#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import hashlib
import argparse
import gzip
import tempfile
import io
import mmap

if sys.version_info.major < 3:
    sys.stderr.write('Please use python 3.x. Your python version is as following:\n')
    sys.stderr.write('{}\n'.format(sys.version))
    sys.exit()


class Cli(object):

    def __init__(self):
        parser = argparse.ArgumentParser(description='fsb file extracter')
        parser.add_argument('file', type=argparse.FileType('rb'))
        parser.add_argument('-v', '--verbose', action='store_true', help="verbose message")
        parser.add_argument('-t', '--type', help="specific data type (file or table)")
        parser.add_argument('-c', '--category', help="specific category (os, plugin or config)")
        parser.add_argument('-o', '--overwrite', action='store_true', help="overwrite if file exists")
        self.args = parser.parse_args()


class FsbRecord(object):

    def __init__(self, headers):
        self.type = headers[0].decode('utf-8')
        self.name = headers[1].decode('utf-8')
        self.category = headers[2].decode('utf-8')
        self.size = int(headers[3]) if self.type == "file" else None
        self.perm = int(headers[4]) if self.type == "file" else None
        self.atime = int(headers[5]) if self.type == "file" else None
        self.mtime = int(headers[6]) if self.type == "file" else None
        self.user = int(headers[7]) if self.type == "file" else None
        self.group = int(headers[8]) if self.type == "file" else None
        self.data = None

    def __str__(self):
        return "{} {} {}".format(self.type, self.name, self.category)

    def save(self, overwrite=True):
        dst = '/'.join([self.type, self.name])
        dst_dir = os.path.dirname(dst)

        if (os.path.exists(dst) and not overwrite):
            return

        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)

        with open(dst, 'wb') as f:
            f.write(self.data)

        if self.type == "file" and os.name == 'posix':
            os.chmod(dst, self.perm)
            os.utime(dst, self.atime, self.mtime)
            os.chown(dst, self.user, self.group)

    def checksum(self):
        md5 = hashlib.md5()
        md5.update(self.data)
        return md5.digest()


class FsbRecordSet(object):

    def __init__(self, file, verbose=False):
        self.begin = 0
        with file as f:
            contents = f.read()
            headers, buf = contents.split(b"End_of_header\n")
            filelist, contents = contents.split(b"End_of_elem\n")
            if headers.find(b"ForeScout backup volume") != 0:
                raise
            if verbose:
                print(headers.decode('utf-8'))

        with tempfile.TemporaryFile(mode='w+b') as tmpfile:
            with gzip.GzipFile(mode='rb', fileobj=io.BytesIO(contents)) as f:
                tmpfile.write(f.read())
                tmpfile.seek(0)

            self.data = mmap.mmap(tmpfile.fileno(), 0)

    def __iter__(self):
        return self

    def __next__(self):
        if self.begin >= self.data.size():
            raise StopIteration()

        self.end = self.data.find(b'\n', self.begin)
        headers = self.data[self.begin:self.end].split(b'\00')
        record = FsbRecord(headers)
        self.begin = self.end + len(b'\n')

        if record.type == 'file':
            self.end = self.begin + record.size
            record.data = self.data[self.begin:self.end]
        elif record.type == 'table':
            self.end = self.data.find(b'\00\n', self.begin)
            record.data = self.data[self.begin:self.end]
            self.end = self.end + len(b'\00\n')
        else:
            raise Exception("unknown data type")

        self.begin, self.end = self.end, self.end + hashlib.md5().digest_size
        if self.data[self.begin:self.end] != record.checksum():
            raise Exception("checksum error")

        self.begin = self.end

        return record

if __name__ == '__main__':

    args = Cli().args
    fsb = FsbRecordSet(args.file, args.verbose)

    for f in fsb:
        if args.type is not None and args.type.lower() != f.type:
            continue
        if args.category is not None and args.category.lower() != f.category:
            continue
        if args.verbose:
            print(f)
        f.save(args.overwrite)

    sys.exit()



