#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os.path
import hashlib
import argparse
import zlib
import collections

class Cli(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description='fsb file extracter')
        parser.add_argument('file', type=argparse.FileType('rb'))
        self.args = parser.parse_args()
    def args_file(self):
        return self.args.file

HASH_SIZE = 16 # md5
Table = collections.namedtuple('Table', ('type', 'name', 'category', 'size'))
File = collections.namedtuple('File', Table._fields + ('perm', 'atime', 'mtime', 'user', 'group'))

if __name__ == '__main__':

    cli = Cli()
    with cli.args_file() as f:
        contents = f.read()
    info, gz = contents.split('End_of_elem\n', 1)
    contents = zlib.decompress(gz, zlib.MAX_WBITS|16) # gzip

    while len(contents) > 0:
        headers, contents = contents.split('\n', 1)
        h = [int(h) if h.isdigit() else h for h in headers.split('\00')]
        if len(h) == 9:
            meta = File(*h)
            data = contents[:meta.size]
            contents = contents[meta.size:]
        else:
            meta = Table(*h)
            data, contents = contents.split('\00\n', 1)
        print meta

        hash = contents[:HASH_SIZE]
        contents = contents[HASH_SIZE:]
        if hash != hashlib.md5(data).digest():
            raise Exception("checksum error")

        dst = '/'.join([meta.type, meta.name])
        dst_dir = os.path.dirname(dst)
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        with open(dst, 'wb') as f:
            f.write(data)

        #if meta[0] == 'file':
        #    os.chmod(dst, meta.perm)
        #    os.utime(dst, meta.atime, meta.mtime)
        #    os.chown(dst, meta.user, meta.group)
