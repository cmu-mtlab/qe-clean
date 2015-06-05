#!/usr/bin/env python

'''Quality estimation-based data selection'''

import argparse
import itertools
import math
import os
import subprocess
import sys

from tools import align
from tools import pipecut
from tools import select

# Change as needed to avoid need for --cdec arg
CDEC = '/home/m/workspace/cdec'

fast_align = None
klm_builder = None
klm_build_binary = None
klm_ngram_query = None
command_only = False


def build_lm(text, arpa, lm, tmp, log):

    cmd_build = [klm_builder, '-o', '4', '-T', tmp, '-S', '80%']
    cmd_binary = [klm_build_binary, 'trie', arpa, lm]

    if command_only:
        sys.stdout.write('$ ' + ' '.join(cmd_build) + ' <' + text + ' >' + arpa + '\n')
        sys.stdout.write('$ ' + ' '.join(cmd_binary) + '\n')
        return

    if os.path.exists(arpa):
        sys.stderr.write(' Found existing arpa file `{f}\'\n'.format(f=arpa))
    else:
        sys.stderr.write(' Running klm builder\n')
        try:
            with open(text) as inp, open(arpa, 'w') as out, open(log, 'w') as err:
                ret = subprocess.Popen(cmd_build, stdin=inp, stdout=out, stderr=err).wait()
                if ret != 0:
                    raise Exception('Non-zero return code for {b}\n'.format(b=klm_builder))
        except Exception as ex:
            sys.stderr.write('Error estimating language model.  Check `{b}\' and `{f}\'.\n'.format(b=klm_builder, f=text))
            raise ex

    if os.path.exists(lm):
        sys.stderr.write(' Found existing klm file `{f}\'\n'.format(f=lm))
    else:
        sys.stderr.write(' Running klm binary builder\n')
        try:
            with open(log, 'a') as err:
                ret = subprocess.Popen(cmd_binary, stderr=err).wait()
                if ret != 0:
                    raise Exception('Non-zero return code for {b}\n'.format(b=klm_build_binary))
        except Exception as ex:
            sys.stderr.write('Error building klm binary.  Make sure that `{a}\' is a valid arpa file or delete and re-run.\n'.format(a=arpa))
            raise ex


def score_lm(lm, bitext, lmscr, log, side=0):

    cmd_score = [klm_ngram_query, lm]

    if command_only:
        pipecut_script = pipecut.__file__
        if pipecut_script.endswith('.pyc'):
            pipecut_script = pipecut_script[:-1]
        cmd_pipecut = [pipecut_script, str(side)]
        sys.stdout.write('$ ' + ' '.join(cmd_pipecut) + ' <' + bitext + '| ' + ' '.join(cmd_score) + ' >' + lmscr + '\n')
        return

    if os.path.exists(lmscr):
        sys.stderr.write(' Found existing lm score file `{f}\'\n'.format(f=lmscr))
    else:
        sys.stderr.write(' Scoring `{f}\'\n'.format(f=bitext))
        try:
            with open(bitext) as inp, open(lmscr, 'w') as out, open(log, 'a') as err:
                p = subprocess.Popen(cmd_score, stdin=subprocess.PIPE, stdout=out, stderr=err)
                for line in inp:
                    text = line.split('|||')[side].strip()
                    p.stdin.write(text + '\n')
                p.stdin.close()
                ret = p.wait()
                if ret != 0:
                    raise Exception('Non-zero return code for {b}\n'.format(b=klm_ngram_query))
        except Exception as ex:
            sys.stderr.write('Error lm scoring data.  Check `{b}\', `{t}\'.\n'.format(b=klm_ngram_query, m=lm, t=bitext))
            raise ex


def word_align(corpus, dev, test, al_dev, al_test, log, reverse=False):

    if command_only:
        align_script = align.__file__
        if align_script.endswith('.pyc'):
            align_script = align_script[:-1]
        cmd_align = [align_script, fast_align, corpus, dev, test, al_dev, al_test]
        if reverse:
            cmd_align.append('-r')
        sys.stdout.write('$ ' + ' '.join(cmd_align) + '\n')
        return

    if os.path.exists(al_dev) and os.path.exists(al_test):
        sys.stderr.write(' Found existing alignment files `{f1}\' and `{f2}\'\n'.format(f1=al_dev, f2=al_test))
    else:
        sys.stderr.write(' Running fast_align\n')
        try:
            with open(log, 'w') as err:
                align.align(fast_align, corpus, dev, test, al_dev, al_test, reverse=reverse, log=err)
        except Exception as ex:
            sys.stderr.write('Error aligning data.  Check `{b}\', `{c}\', `{d}\', and `{t}\'.\n'.format(b=fast_align, c=corpus, d=dev, t=test))
            raise ex


def score_stdev(text, lmscr_f, lmscr_e, al_fe, al_ef, scr_out, stats_in=None, stats_out=None):

    sys.stderr.write(' Calculating stats for `{f}\'\n'.format(f=text))

    try:
        # Features
        in_scores = []
        in_scores.append(get_lm_scorer(lmscr_f))
        in_scores.append(get_lm_scorer(lmscr_e))
        in_scores.append(get_al_scorer(al_fe))
        in_scores.append(get_al_scorer(al_ef))
        in_scores.append(get_al_aligned(al_fe))
        in_scores.append(get_al_aligned(al_ef))

        with open(text) as inp, open(scr_out, 'w') as out:

            # No calculated stats this is the devset, so calculate mean, stdev before writing
            if not stats_in and stats_out:
                scores = zip(*in_scores)
                (dev_mean, dev_stdev) = zip(*(calc_mean_stdev(s) for s in zip(*scores)))
                with open(stats_out, 'w') as out_stats:
                    out_stats.write(' '.join(str(s) for s in dev_mean) + '\n')
                    out_stats.write(' '.join(str(s) for s in dev_stdev) + '\n')
            # Otherwise read in stats
            elif stats_in and not stats_out:
                scores = itertools.izip(*in_scores)
                with open(stats_in) as in_stats:
                    dev_mean = [float(s) for s in in_stats.readline().split()]
                    dev_stdev = [float(s) for s in in_stats.readline().split()]
            else:
                raise Exception('Error: specify either stats_in or stats_out and not both')

            for (line, scores) in itertools.izip(inp, scores):
                str_scores = ' '.join(str(i) for i in scores)
                str_stdev = ' '.join(str(get_stdev(i, m, d)) for (i, m, d) in zip(scores, dev_mean, dev_stdev))
                out.write(line.strip() + ' ||| '  + str_scores + ' ||| ' + str_stdev + '\n')

    except Exception as ex:
        sys.stderr.write('Error calculating mean and stdev from score files.  Check all of:\n')
        sys.stderr.write(text + '\n')
        sys.stderr.write(lmscr_f + '\n')
        sys.stderr.write(lmscr_e + '\n')
        sys.stderr.write(al_fe + '\n')
        sys.stderr.write(al_ef + '\n')
        if stats_in:
            sys.stderr.write(stats_in + '\n')
        if stats_out:
            sys.stderr.write(stats_out + '\n')
        raise ex


# Score generator for lm score file
def get_lm_scorer(f):

    with open(f) as inp:
        for line in inp:
            tok = line.split()
            # w_1=word n prob w_2=word n prob ... Total: prob OOV: n
            # +0 since we start with p(w_1 | <s>)
            # +1 since we end with p(</s> | w_n)
            ng_count = ((len(tok) - 4) / 3) + 1
            prob = float(tok[-3])
            yield (prob / ng_count)


# Score generator for alignment file
def get_al_scorer(f, rev=False):

    with open(f) as inp:
        for line in inp:
            # f words ||| e words ||| 0-0 1-1 ||| score
            (f_words, e_words, _, score) = line.split('|||')
            words = len(f_words.split()) if rev else len(e_words.split())
            yield float(score) / words


# Score generator for aligned word fraction
def get_al_aligned(f, rev=False):

    with open(f) as inp:
        for line in inp:
            try:
                # f words ||| e words ||| 0-0 1-1 ||| score
                (f_words, e_words, links, _) = line.split('|||')
                words = len(f_words.split()) if rev else len(e_words.split())
                aligned = len(set(link.split('-')[0] for link in links.split()))
                yield float(aligned) / words
            except Exception as ex:
                sys.stderr.write(str(ex) + '\n')
                sys.stderr.write('Bad line, assigning zero score: {l}\n'.format(l=line.strip()))
                yield 0.0


def calc_mean_stdev(x):
    mean = float(sum(x)) / len(x)
    stdev = math.sqrt(sum((i - mean) ** 2 for i in x) / len(x))
    return (mean, stdev)


def get_stdev(x, mean, stdev):
    return (float(mean - x) / stdev)


def main():

    global fast_align, klm_builder, klm_build_binary, klm_ngram_query, command_only

    # Args
    parser = argparse.ArgumentParser(description='Quality estimation-based data selection')
    parser.add_argument('--cdec', help='location of cdec base directory (if not default)')
    parser.add_argument('-f', '--fmono', help='clean monolingual training data (f) (model estimation)', required=True)
    parser.add_argument('-e', '--emono', help='clean monolingual training data (e) (model estimation)', required=True)
    parser.add_argument('-b', '--bitext', help='clean bilingual training data (model estimation)', required=True)
    parser.add_argument('-d', '--dev', help='clean bilingual development data (threshold calculation)', required=True)
    parser.add_argument('-i', '--input', help='input bilingual data (data to be cleaned)', required=True)
    parser.add_argument('-o', '--output', help='output directory', required=True)
    parser.add_argument('-c', '--command', help='print commands for model estimation', action='store_true')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.stderr.write('\n')
        sys.stderr.write('For more information, including instructions for running without clean data\n')
        sys.stderr.write('or manually running commands in parallel, see README.md\n')
        sys.stderr.write('\n')
        sys.stderr.write('If you publish work that uses qe-clean, please cite the papers listed in\n')
        sys.stderr.write('README.md.\n')
        sys.exit()
    args = parser.parse_args()

    # Check binaries
    cdec = args.cdec if args.cdec else CDEC
    fast_align = os.path.join(cdec, 'word-aligner', 'fast_align')
    klm_builder = os.path.join(cdec, 'klm', 'lm', 'builder', 'builder')
    klm_build_binary = os.path.join(cdec, 'klm', 'lm', 'build_binary')
    klm_ngram_query = os.path.join(cdec, 'klm', 'lm', 'ngram_query')
    for f in (fast_align, klm_builder, klm_build_binary, klm_ngram_query):
        if not os.path.exists(f):
            sys.stderr.write('Error: Binary `{f}\' does not exist.\n'.format(f=f))
            sys.stderr.write('Use --cdec to pass the location of the cdec base directory (or update CDEC in {f}).\n'.format(f=__file__))
            sys.exit(1)

    # Check for clean bitext
    if args.bitext == args.input:
        sys.stderr.write('Warning: Using input data for model estimation.\n')
        sys.stderr.write('Warning: Make sure this is intentional (no clean bitext available).\n')

    # Check required input files
    for f in (args.fmono, args.emono, args.bitext, args.dev, args.input):
        if not os.path.exists(f):
            sys.stderr.write('Error: File `{f}\' does not exist.\n'.format(f=f))
            sys.exit(1)

    # Only print commands?
    if args.command:
        command_only = True
        sys.stderr.write('Printing commands to run manually.\n')
        sys.stderr.write('Commands within each step must be run sequentially.\n')
        sys.stderr.write('Steps 1-4 may be run in parallel.\n')
        sys.stderr.write('Step 5 is always run last by this script and requires insignificant resources.\n')

    ### Step 0: directories

    sys.stderr.write('Step 0: Create output directories\n')
    d_files = os.path.join(args.output, 'files')
    d_log = os.path.join(args.output, 'log')
    if not os.path.exists(args.output):
        os.mkdir(args.output)
    if not os.path.exists(d_files):
        os.mkdir(d_files)
    if not os.path.exists(d_log):
        os.mkdir(d_log)

    ### Step 1: source language model

    sys.stderr.write('Step 1: Build source language model and score data\n')
    arpa_f = os.path.join(d_files, 'f.4.arpa')
    lm_f = os.path.join(d_files, 'f.4.klm')
    lmscr_dev_f = os.path.join(d_files, 'dev.f.lmscr')
    lmscr_f = os.path.join(d_files, 'input.f.lmscr')
    lmlog_f = os.path.join(d_log, 'lm.f.log')
    build_lm(args.fmono, arpa_f, lm_f, os.path.join(d_files, 'lm.f.tmp'), lmlog_f)
    score_lm(lm_f, args.dev, lmscr_dev_f, lmlog_f, side=0)
    score_lm(lm_f, args.input, lmscr_f, lmlog_f, side=0)

    ### Step 2: target language model

    sys.stderr.write('Step 2: Build target language model and score data\n')
    arpa_e = os.path.join(d_files, 'e.4.arpa')
    lm_e = os.path.join(d_files, 'e.4.klm')
    lmscr_dev_e = os.path.join(d_files, 'dev.e.lmscr')
    lmscr_e = os.path.join(d_files, 'input.e.lmscr')
    lmlog_e = os.path.join(d_log, 'lm.e.log')
    build_lm(args.emono, arpa_e, lm_e, os.path.join(d_files, 'lm.e.tmp'), lmlog_e)
    score_lm(lm_e, args.dev, lmscr_dev_e, lmlog_e, side=1)
    score_lm(lm_e, args.input, lmscr_e, lmlog_e, side=1)

    ### Step 3: align source-target

    sys.stderr.write('Step 3: Source-target word alignment\n')
    al_dev_fe = os.path.join(d_files, 'dev.fe.al')
    al_fe = os.path.join(d_files, 'input.fe.al')
    word_align(args.bitext, args.dev, args.input, al_dev_fe, al_fe, os.path.join(d_log, 'al.fe.log'), reverse=False)

    ### Step 4: align target-source

    sys.stderr.write('Step 4: Target-source word alignment\n')
    al_dev_ef = os.path.join(d_files, 'dev.ef.al')
    al_ef = os.path.join(d_files, 'input.ef.al')
    word_align(args.bitext, args.dev, args.input, al_dev_ef, al_ef, os.path.join(d_log, 'al.ef.log'), reverse=True)

    ### End here if just printing commands

    if command_only:
        return

    ### Step 5: final scores

    sys.stderr.write('Step 5: Calculate scores and standard deviations\n')
    scr_dev = os.path.join(args.output, 'dev.scored')
    scr_input = os.path.join(args.output, 'input.scored')
    scr_stats = os.path.join(d_files, 'dev.stats')
    score_stdev(args.dev, lmscr_dev_f, lmscr_dev_e, al_dev_fe, al_dev_ef, scr_dev, stats_out=scr_stats)
    score_stdev(args.input, lmscr_f, lmscr_e, al_fe, al_ef, scr_input, stats_in=scr_stats)

    ### Done

    sys.stderr.write('Finished.  Scored input text written to `{f}\'\n'.format(f=scr_input))
    sys.stderr.write('All other files in `{d}\' may be deleted.\n'.format(d=args.output))
    select_script = select.__file__
    if select_script.endswith('.pyc'):
        select_script = select_script[:-1]
    sys.stderr.write('Use `{s}\' to select subsets of input text by standard deviation.\n'.format(s=select_script))


if __name__ == '__main__':
    main()
