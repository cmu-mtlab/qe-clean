#!/usr/bin/env python

import itertools
import sys


def main():

    if len(sys.argv[1:]) != 1:
        sys.stderr.write('Usage: {0} N\n'.format(sys.argv[0]))
        sys.exit(2)

    N = int(sys.argv[1])

    for line in sys.stdin:
        sys.stdout.write(line.split('|||')[N].strip() + '\n')


if __name__ == '__main__':
    main()
