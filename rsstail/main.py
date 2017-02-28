# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

""" A Python logging library with super powers """

import sys
import signal
import textwrap

from os import getcwd, path as p
from argparse import RawTextHelpFormatter, ArgumentParser

import pygogo as gogo
from dateutil.parser import parse as parse_date
from rsstail import tail, __version__
from rsstail.formatter import PLACEHOLDERS, Formatter

DEF_TIME_FMT = '%Y/%m/%d %H:%M:%S'
DEF_INTERVAL = '300s'
CURDIR = p.basename(getcwd())
LOGFILE = '%s.log' % CURDIR
FIELDS = sorted(PLACEHOLDERS)

logger = gogo.Gogo(__name__, monolog=True).logger

examples = r'''
Format specifiers must have one the following forms:
  %%(placeholder)[flags]s
  {placeholder:flags}

Examples:
  %(prog)s <url>
  echo '<url>' | %(prog)s --reverse
  %(prog)s -s pubdate -s title -s author <url1> <url2> <url3>
  %(prog)s --interval 60s --newer "2011/12/20 23:50:12" <url>
  %(prog)s --format '%%(timestamp)-30s %%(title)s\n' <url>
  %(prog)s --format '%%(title)s was written on %%(pubdate)s\n' <url>
  %(prog)s --format '{timestamp:<30} {title} {author}\n' <url>
  %(prog)s --format '{timestamp:<20} {pubdate:^30} {author:>30}\n' <url>
  %(prog)s --time-format '%%Y/%%m/%%d %%H:%%M:%%S' <url>
  %(prog)s --time-format 'Day of the year: %%j Month: %%b' <url>

Useful flags in this context are:
  %%(placeholder)-10s - left align and pad
  %%(placeholder)10s  - right align and pad
  {placeholder:<10}  - left align and pad
  {placeholder:>10}  - right align and pad
  {placeholder:^10}  - center align and pad
'''

available = textwrap.wrap('Available fields: {}'.format(', '.join(FIELDS)))
epilog = [textwrap.dedent(examples)] + available


def timespec(value):
    """Parse the 'timespec' option:

    >>> timespec(1)
    1
    >>> timespec('5m')
    300
    >>> timespec('1h')
    3600
    """

    try:
        return int(value)
    except ValueError:
        multiply = {'s': 1, 'm': 60, 'h': 3600}
        suffix = value[-1]

        msg = 'invalid timespec value {} - hint: 60, 60s, 1m, 1h'

        if suffix in multiply:
            try:
                v = int(value[:-1])
                return v * multiply[suffix]
            except ValueError:
                ValueError(msg.format(value))
        else:
            raise ValueError(msg.format(value))


parser = ArgumentParser(
    description='description: Tails 1 or more rss feeds',
    prog='rsstail',
    usage='%(prog)s [options] <url> [<url> ...]',
    formatter_class=RawTextHelpFormatter,
    epilog='\n'.join(epilog),
)

parser.add_argument(
    dest='urls', nargs='*', default=[sys.stdin],
    help='The urls to tail (default: reads from stdin).')

i_help = 'Number of seconds between polling (default: {}).'

parser.add_argument(
    '-i', '--interval', action='store', help=i_help.format(DEF_INTERVAL),
    type=timespec, default=DEF_INTERVAL)

parser.add_argument(
    '-N', '--iterations', action='store', type=int,
    help='Number of times to poll before quiting (default: inf).')

parser.add_argument(
    '-I', '--initial', action='store', type=int,
    help='Number of entries to show (default: all)')

parser.add_argument(
    '-n', '--newer', metavar='DATE', action='store',
    help='Date by which entries should be newer than')

parser.add_argument(
    '-s', '--show', metavar='FIELD', choices=FIELDS, action='append',
    help='Entry field to display (default: title).', default=[])

t_help = "The date/time format (default: 'YYYY/MM/DD HH:MM:SS')."

parser.add_argument(
    '-t', '--time-format', metavar='FORMAT', action='store',
    default=DEF_TIME_FMT, help=t_help)

parser.add_argument(
    '-F', '--format', action='store',
    help='The output format (overrides other format options).')

parser.add_argument(
    '-r', '--reverse', action='store_true',
    help='Show entries in reverse order.')

parser.add_argument(
    '-f', '--fail', action='store_true', help='Exit on error.')

parser.add_argument(
    '-u', '--unique', action='store_true', help='Skip duplicate entries.')

parser.add_argument(
    '-H', '--heading', action='store_true', help='Show field headings.')

parser.add_argument(
    '-v', '--version', help="Show version and exit.", action='store_true',
    default=False)

parser.add_argument(
    '-V', '--verbose', help='Increase output verbosity.', action='store_true',
    default=False)


def die(msg, fail=False, *args):
    sys.exit(msg) if fail else logger.error(msg, *args)


def sigint_handler(num=None, frame=None):
    logger.info('... quitting\n', file=sys.stderr)
    sys.exit(0)


def run():
    """CLI runner"""
    args = parser.parse_args()
    kwargs = {'monolog': True, 'verbose': args.verbose}
    logger = gogo.Gogo(__name__, **kwargs).get_logger('run')

    if args.version:
        logger.info('rsstail v%s' % __version__)
        exit(0)

    if args.newer:
        try:
            newer = parse_date(args.newer).timetuple()
        except ValueError as err:
            die(err, True)

        logger.debug('showing entries newer than %s', newer)
    else:
        newer = None

    signal.signal(signal.SIGINT, sigint_handler)

    if args.format:
        fmt = args.format.replace('\\n', '\n')
        formatter = Formatter(fmt, args.time_format)
    else:
        show = args.show or ['title']
        pargs = (show, args.time_format, args.heading)
        formatter = Formatter.from_fields(*pargs)

    logger.debug('using format: %r', formatter.fmt)
    logger.debug('using time format: %r', formatter.time_fmt)

    info = {
        'seen': set() if args.unique else None, 'newer': newer,
        'reverse': args.reverse, 'iterations': args.iterations,
        'interval': args.interval, 'formatter': formatter,
        'initial': args.initial, 'logger': logger}

    first = args.urls[0]

    if hasattr(first, 'isatty') and first.isatty():  # called with no args
        # This doesn't work for scripttest though
        parser.print_help()
        sys.exit(0)
    elif hasattr(first, 'read'):  # piped into sdtin
        urls = first.read().splitlines()
    else:
        urls = args.urls

    tail(urls, **info)
    # try:
    #     tail(args.urls, **info)
    # except Exception as err:
    #     die(err, args.fail)
    # else:
    #     sys.exit(0)


if __name__ == '__main__':
    run()
