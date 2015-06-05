#!/usr/bin/env python

import sys

def main():

    if len(sys.argv[1:]) != 1:
        sys.stderr.write('usage: {f} N < in.scored > out.bitext\n'.format(f=sys.argv[0]))
        sys.exit(2)

    N = float(sys.argv[1])

    for line in sys.stdin:
        try:
            (f, e, _, str_stdev) = line.split('|||')
            stdev = [float(i) for i in str_stdev.split()]
            if len([i for i in stdev if i <= N]) == len(stdev):
                sys.stdout.write(f.strip() + ' ||| ' + e.strip() + '\n')
        except Exception as ex:
            sys.stderr.write(str(ex) + '\n')
            sys.stderr.write('Bad line, excluding: {l}\n'.format(l=line.strip()))

if __name__ == '__main__':
    main()
