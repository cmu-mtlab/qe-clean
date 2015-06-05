#!/usr/bin/env python

import sys
import subprocess
import threading


# Run aligner on dev and test data
def align(fast_align, corpus, dev, test, out_dev, out_test, reverse=False, log=sys.stderr):

    cmd_align = [fast_align, '-i', corpus, '-d', '-v', '-H', '-x', '-']
    if reverse:
        cmd_align.append('-r')

    try:
        len_dev = lc(dev)
        p = subprocess.Popen(cmd_align, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        t = threading.Thread(target=split_out, args=(p.stdout, len_dev, out_dev, out_test))
        t.start()
        for line in open(dev):
            p.stdin.write(line)
        for line in open(test):
            p.stdin.write(line)
        p.stdin.close()
        ret = p.wait()
        t.join()
        if ret != 0:
            raise Exception('Non-zero return code for {b}\n'.format(b=fast_align))
    except Exception as ex:
        sys.stderr.write('Error aligning data.  Check `{b}\', `{c}\', and `{t}\'.\n'.format(b=fast_align, c=corpus, t=test))
        raise ex


# Split output for dev and test data into two files
def split_out(stream, len_dev, dev, test):
    with open(dev, 'w') as out:
        for _ in range(len_dev):
            out.write(stream.readline())
    with open(test, 'w') as out:
        while True:
            line = stream.readline()
            if not line:
                break
            out.write(line)


# Simple line counter
def lc(f):
    i = 0
    for _ in open(f):
        i += 1
    return i


def main():

    if len(sys.argv) < 7:
        sys.stderr.write('usage: {0} fast_align corpus.f-e dev.f-e test.f-e dev.out test.out [-r]\n'.format(sys.argv[0]))
        sys.exit(2)

    reverse = True if len(sys.argv) > 7 and sys.argv[7] == '-r' else False

    align(*sys.argv[1:7], reverse=reverse)


if __name__ == '__main__':
    main()
