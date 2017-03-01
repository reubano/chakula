#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

"""
tests.test
~~~~~~~~~~

Provides scripttests pygogo CLI functionality.
"""

import sys

sys.path.append('../chakula')
import chakula                              # noqa

from difflib import unified_diff            # noqa
from os import path as p                    # noqa
from io import StringIO                     # noqa
from timeit import default_timer as timer   # noqa

from scripttest import TestFileEnvironment  # noqa
import pygogo as gogo                       # noqa

CUR_DIR = p.abspath(p.dirname(__file__))
PARENT_DIR = p.abspath(p.dirname(CUR_DIR))


def main(script, tests, verbose=False, stop=True):
    """ Main method

    Returns 0 on success, 1 on failure
    """
    failures = 0
    logger = gogo.Gogo(__name__, verbose=verbose).logger
    short_script = p.basename(script)
    env = TestFileEnvironment('.scripttest')

    start = timer()

    for pos, test in enumerate(tests):
        num = pos + 1
        opts, arguments, expected = test

        if opts or arguments:
            joined_opts = ' '.join(opts) if opts else ''
            joined_args = '"%s"' % '" "'.join(arguments) if arguments else ''
            command = "%s %s %s" % (script, joined_opts, joined_args)
            args = (short_script, joined_opts, joined_args)
            short_command = "%s %s %s" % args
        else:
            command, short_command = script, short_script

        expect_error = not expected if isinstance(expected, bool) else False
        result = env.run(command, cwd=PARENT_DIR, expect_error=expect_error)
        output = result.stdout

        if isinstance(expected, bool):
            outlines = [str(expected)]
            checklines = [str(result.returncode == 0)]
        elif callable(expected):
            outlines = [str(expected(output))]
            checklines = ['True']
        elif p.isfile(expected):
            outlines = StringIO(output).readlines()

            with open(expected, encoding='utf-8') as f:
                checklines = f.readlines()
        else:
            outlines = StringIO(output).readlines()
            checklines = StringIO(expected).readlines()

        args = [checklines, outlines]
        kwargs = {'fromfile': 'expected', 'tofile': 'got'}
        diffs = ''.join(unified_diff(*args, **kwargs))
        passed = not diffs

        if not passed:
            failures += 1
            msg = "ERROR! Output from test #%i:\n  %s\n" % (num, short_command)
            msg += "doesn't match:\n  %s\n" % expected
            msg += diffs if diffs else ''
        else:
            logger.debug(output)
            msg = 'Scripttest #%i: %s ... ok' % (num, short_command)

        logger.info(msg)

        if stop and failures:
            break

    time = timer() - start
    logger.info('%s' % '-' * 70)
    end = 'FAILED (failures=%i)' % failures if failures else 'OK'
    logger.info('Ran %i scripttests in %0.3fs\n\n%s' % (num, time, end))
    sys.exit(failures)


if __name__ == '__main__':
    script = p.join(PARENT_DIR, 'bin', 'chakula')
    feed = p.join(CUR_DIR, 'feeds', 'jenkins.rss')
    cache_path = p.join(PARENT_DIR, '.scripttest', 'cache')
    cache = '--cache {}'.format(cache_path)

    exp = [
        'pip_python2.6 #1006 (FAILURE)\n',
        'pip_python2.6 #1005 (SUCCESS)\n',
        'pip_python2.6 #1004 (SUCCESS)\n',
        'pip_python2.6 #1003 (SUCCESS)\n',
        'pip_python2.6 #1002 (SUCCESS)\n'
    ]

    args = ['--heading', '--iterations 1', '--initial 1', '-s title', '-s url']
    hfunc = lambda stdout: ('Title' in stdout) and ('Url' in stdout)

    tests = [
        (['--help'], [], True),
        (['--version'], [], 'chakula v%s\n' % chakula.__version__),
        (['--iterations 1', '--initial 3'], [feed], ''.join(exp[:3])),
        (['--iterations 1', '-s title'], [feed], ''.join(exp)),
        (
            ['--reverse', '--iterations 1', '-s title'],
            [feed], ''.join(reversed(exp))),
        (args, [feed], hfunc),
        (['--iterations 1', '--newer "2012/01/04 11:00:00"'], [feed], exp[0]),
        (['--iterations 1', '--newer "2012/01/04 11:00"'], [feed], exp[0]),
        (['--iterations 1', '--newer "2012/01/04"'], [feed], ''.join(exp[:2])),
        (['--iterations 1', '--newer "$#@!@#"'], [feed], False),
        ([cache, '--iterations 1', '-s title'], [feed], ''.join(exp)),
        ([cache, '--iterations 1', '-s title'], [feed], ''),
    ]

    main(script, tests)
