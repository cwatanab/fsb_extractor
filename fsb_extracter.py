#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path
import hashlib
import argparse
import gzip
import tempfile
import collections
import io
import mmap


class Cli(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description='fsb file extracter')
        parser.add_argument('file', type=argparse.FileType('rb'))
        parser.add_argument('-v', '--verbose', action='store_true', help="verbose message")
        self.args = parser.parse_args()


HASH_SIZE = 16  # md5hash
Base = collections.namedtuple('Base', ('type', 'name', 'category'))
Table = collections.namedtuple('Table', Base._fields )
File = collections.namedtuple('File', Base._fields + ('size', 'perm', 'atime', 'mtime', 'user', 'group'))

if __name__ == '__main__':

    cli = Cli()

    with cli.args.file as f:
        contents = f.read()
        headers, buf = contents.split(b"End_of_header\n")
        meta, contents = contents.split(b"End_of_elem\n")
        if headers.find(b"ForeScout backup volume") != 0:
            raise
        if cli.args.verbose:
            print(headers.decode('utf-8'))

    with tempfile.TemporaryFile(mode='w+b') as tmpfile:
        with gzip.GzipFile(mode='rb', fileobj=io.BytesIO(contents)) as f:
            tmpfile.write(f.read())
            tmpfile.seek(0)

        data = mmap.mmap(tmpfile.fileno(), 0)

        i = 0
        while i < data.size():
            j = data.find(b'\n', i)
            headers = data[i:j].split(b'\00')
            headers = [int(h) if h.isdigit() else h.decode('utf-8') for h in headers]
            i = j + 1

            if cli.args.verbose:
                print(headers)

            if headers[0] == 'file':
                meta = File(*headers)
                j = i + meta.size
                content = data[i:j]
            elif headers[0] == 'table':
                meta = Table(*headers)
                j = data.find(b'\00\n', i)
                content = data[i:j]
                j = j + len(b'\00\n')
            else:
                raise Exception("unknown data type")

            i, j = j, j + HASH_SIZE
            hash = data[i:j]
            if hash != hashlib.md5(content).digest():
                raise Exception("checksum error")
            i = j

            dst = '/'.join([meta.type, meta.name])
            dst_dir = os.path.dirname(dst)
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
            with open(dst, 'wb') as f:
                f.write(content)

            #if meta[0] == 'file':
            #    os.chmod(dst, meta.perm)
            #    os.utime(dst, meta.atime, meta.mtime)
            #    os.chown(dst, meta.user, meta.group)
