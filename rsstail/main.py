#!/usr/bin/env python
# encoding: utf-8

from __future__ import print_function

import os
import sys
import copy
import time
import signal
import logging
import textwrap
import optparse
from datetime import datetime as dt

import feedparser


from rsstail.formatter import placeholders
from rsstail.formatter import Formatter, hasformat


logging.basicConfig(format='! %(message)s', level=logging.INFO)
log = logging.getLogger(__file__)


def parseopt(args=None):
    opts = RsstailOption

    gen_opts = [
        opts('-v', '--verbose', action='count', help='increase verbosity'),
        opts('-V', '--version', action='store_true', help='show version and exit'),
        opts('-h', '--help', action='store_true', help='show this help message and exit'),
        opts('-x', '--help-format', action='store_true', help='show formatting help and exit'),
    ]

    feed_opts = [
        opts('-i', '--interval', action='store', help='poll every <arg> seconds', type='timespec', default='300'),
        opts('-e', '--iterations', action='store', help='poll <arg> times and quit', type='int'),
        opts('-n', '--initial', action='store', help='initially show <arg> items', type='int'),
        opts('-w', '--newer', action='store', help='show items newer than <arg>'),
        opts('-b', '--bytes', action='store', help='show only <arg> description/comment bytes', type='int'),
        opts('-r', '--reverse', action='store_true', help='show in reverse order'),
        opts('-s', '--striphtml', action='store_true', help='strip html tags'),
        opts('-o', '--nofail', action='store_true', help='do not exit on error'),
    ]

    fmt_opts = [
        opts('-t', '--timestamp', action='store_true', help='show timestamp'),
        opts('-l', '--title', action='store_true', help='show title'),
        opts('-u', '--url', action='store_true', help='show url'),
        opts('-d', '--desc', action='store_true', help='show description'),
        opts('-p', '--pubdate', action='store_true', help='show publication date'),
        opts('-U', '--updated', action='store_true', help='show last update date'),
        opts('-a', '--author', action='store_true', help='show author'),
        opts('-c', '--comments', action='store_true', help='show comments'),
        opts('-g', '--no-heading', action='store_true', help='do not show headings'),
        opts('-m', '--time-format', action='store', help='date/time format'),
        opts('-f', '--format', action='store', help='output format (overrides other format options)'),
    ]

    prog = os.path.basename(sys.argv[0])
    prog = prog if prog != '__main__.py' else 'rsstail'

    epilog = r'''
    Examples:
      %(prog)s --timestamp --pubdate --title --author <url1> <url2> <url3>
      %(prog)s --reverse --title <url> <username:password@url>
      %(prog)s --interval 60|60s|5m|1h --newer "2011/12/20 23:50:12" <url>
      %(prog)s --format '%%(timestamp)-30s %%(title)s %%(author)s\n' <url>
      %(prog)s --format '{timestamp:<30} {title} {author}\n' <url>
    ''' % {'prog': prog}

    if not hasformat:
        epilog = epilog.splitlines()[:-3]
        epilog.append(os.linesep)
        epilog = os.linesep.join(epilog)

    # Readability is better than de-duplication in this case, imho.
    if hasformat:
        format_help = '''\
        Format specifiers must have one the following forms:
          %(placeholder)[flags]s
          {placeholder:flags}

        Examples:
          --format '%(timestamp)s %(pubdate)-30s %(author)s\\n'
          --format '%(title)s was written by %(author)s on %(pubdate)s\\n'
          --format '{timestamp:<20} {pubdate:^30} {author:>30}\\n'

        Time format takes standard 'sprftime' specifiers:
          --time-format '%Y/%m/%d %H:%M:%S'
          --time-format 'Day of the year: %j Month: %b'

        Useful flags in this context are:
          %(placeholder)-10s - left align and pad
          %(placeholder)10s  - right align and pad
          {placeholder:<10}  - left align and pad
          {placeholder:>10}  - right align and pad
          {placeholder:^10}  - center align and pad
        '''

    else:
        format_help = '''\
        Format specifiers have the following form:
          %(placeholder)[flags]s

        Examples:
          --format '%(timestamp)s %(pubdate)-30s %(author)s\\n'
          --format '%(title)s was written by %(author)s on %(pubdate)s\\n'

        Time format takes standard 'sprftime' specifiers:
          --time-format '%Y/%m/%d %H:%M:%S'
          --time-format 'Day of the year: %j Month: %b'

        Useful flags in this context are:
          %(placeholder)-10s - left align and pad
          %(placeholder)10s  - right align and pad
        '''

    res = [textwrap.dedent(format_help), 'Available placeholders:']
    res += sorted(map(lambda x: 2*' ' + x, placeholders))
    format_help = os.linesep.join(res)

    description = None

    def _format_option_strings(option):
        '''
        >>> _format_option_strings(('-f', '--format'))
        -f --format arg
        '''

        opts = []

        if option._short_opts:
            opts.append(option._short_opts[0])
        if option._long_opts:
            opts.append(option._long_opts[0])
        if len(opts) > 1:
            opts.insert(1, ' ')
        if option.takes_value():
            opts.append(' <arg>')

        return ''.join(opts)

    def _format_heading(heading):
        return '' if heading == 'Options' else heading + ':\n'

    # A more compact option formatter
    fmt = optparse.IndentedHelpFormatter(max_help_position=40, indent_increment=1)
    fmt.format_option_strings = _format_option_strings
    fmt.format_heading = _format_heading
    fmt.format_epilog = lambda x: x if x else ''

    kw = {
        'usage': '%prog [options] <url> [<url> ...]',
        'prog': prog,
        'epilog': textwrap.dedent(epilog),
        'formatter': fmt,
        'description': description,
        'add_help_option': False,
    }

    parser = optparse.OptionParser(**kw)
    parser.print_help_format = lambda: print(format_help)

    gen_group  = optparse.OptionGroup(parser, 'General Options')
    feed_group = optparse.OptionGroup(parser, 'Feed Options')
    fmt_group  = optparse.OptionGroup(parser, 'Format Options')

    gen_group.add_options(gen_opts)
    feed_group.add_options(feed_opts)
    fmt_group.add_options(fmt_opts)

    parser.add_option_group(gen_group)
    parser.add_option_group(feed_group)
    parser.add_option_group(fmt_group)

    if not args:
        opts, args = parser.parse_args()
    else:
        opts, args = parser.parse_args(args)

    return parser, opts, args


def check_timespec(option, opt, value):
    '''Parse and validate the 'timespec' option:

    >>> check_timespec(1)
    1
    >>> check_timespec('5m')
    300
    >>> check_timespec('1h')
    3600
    '''

    try:
        return int(value)
    except ValueError:
        multiply = {'s': 1, 'm': 60, 'h': 3600}
        suffix = value[-1]

        msg = 'option %s: invalid timespec value %s - hint: 60, 60s, 1m, 1h'
        if suffix in multiply:
            try:
                v = int(value[:-1])
                return v * multiply[suffix]
            except ValueError:
                raise optparse.OptionValueError(msg % (option, value))

        raise optparse.OptionValueError(msg % (option, value))


class RsstailOption(optparse.Option):
    TYPES = optparse.Option.TYPES + ('timespec',)
    TYPE_CHECKER = copy.copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER['timespec'] = check_timespec


def die(msg, flunk=False, *args):
    log.error(msg, *args)
    if not flunk:
        sys.exit(1)


def sigint_handler(num=None, frame=None):
    print('... quitting\n', file=sys.stderr)
    sys.exit(0)


def parse_date(dt_str):
    formats = (
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    )

    def _try_parse(f):
        try:
            return time.strptime(dt_str, f)
        except ValueError:
            return None

    res = [_try_parse(i) for i in formats]
    if not any(res):
        raise ValueError('date "%s" could not be parsed' % dt_str)

    return [i for i in res if i][0]


def date_fmt(date):
    if date:
        d = dt(*date[:6]).strftime('%Y/%m/%d %H:%M:%S')
        return d


def get_last_mtime(entries):
    try:
        last = max(entries, key=lambda e: e.updated_parsed)
        return last.updated_parsed
    except (ValueError, AttributeError):
        return None


def setup_formatter(opts):
    fmt = []
    wh = not opts.no_heading

    if opts.timestamp:
        fmt.append('%(timestamp)s')

    if opts.pubdate:
        fmt.append('Pubdate: %(pubdate)s' if wh else '%(pubdate)s')

    if opts.updated:
        fmt.append('Updated: %(updated)s' if wh else '%(updated)s')

    if opts.title:
        fmt.append('Title: %(title)-50s' if wh else '%(title)-50s')

    if opts.author:
        fmt.append('Author: %(author)s' if wh else '%(author)s')

    if opts.url:
        fmt.append('Link: %(link)s' if wh else '%(link)s')

    if opts.desc:
        fmt.append('\nDescription: %(desc)s\n' if wh else '\n%(desc)s\n')

    if opts.comments:
        fmt.append('Comments: %(comments)s' if wh else '%(comments)s')

    time_fmt = '%Y/%m/%d %H:%M:%S' if not opts.time_format else opts.time_format

    if opts.format:
        fmt = opts.format.replace('\\n', '\n')
    elif not fmt:
        # default formatter
        fmt = 'Title: %(title)s\n'
    else:
        fmt.append('\n')
        fmt = '  '.join(fmt)

    formatter = Formatter(fmt, time_fmt, opts.striphtml)

    log.debug('using format: %r', formatter.fmt)
    log.debug('using time format: %r', formatter.time_fmt)
    return formatter


def tick(feeds, opts, formatter, iteration, stream=sys.stdout):
    for url, el in feeds.items():
        etag, last_mtime, last_update = el

        log.debug('parsing: %r', url)
        log.debug('etag:  %s', etag)
        log.debug('mtime: %s', date_fmt(last_mtime))

        feed = feedparser.parse(url, etag=etag, modified=last_mtime)

        if feed.bozo == 1:
            safeexc = (feedparser.CharacterEncodingOverride,)
            if not isinstance(feed.bozo_exception, safeexc):
                msg = 'feed error %r:\n%s'
                die(msg, opts.nofail, url, feed.bozo_exception)

        if iteration == 1 and isinstance(opts.initial, int):
            entries = feed.entries[:opts.initial]
        else:
            entries = feed.entries

        if opts.newer:
            log.debug('showing entries older than %s', date_fmt(last_update))
            entries = [entry for entry in entries if entry.date_parsed > opts.newer]

        if last_update:
            log.debug('showing entries older than %s', date_fmt(last_update))
            entries = [entry for entry in entries if entry.updated_parsed > last_update]

        new_last_update = get_last_mtime(entries)
        if not new_last_update and not entries:
            new_last_update = last_update

        if opts.reverse:
            entries = reversed(entries)

        for entry in entries:
            out = formatter(entry)
            stream.write(out)
        stream.flush()

        # needed for fetching/showing only new entries on next run
        etag = getattr(feed, 'etag', None)
        last_mtime = getattr(feed.feed, 'modified_parsed', None)

        feeds[url] = (etag, last_mtime, new_last_update)


def main():
    parser, opts, args = parseopt()

    if opts.help or len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if opts.help_format:
        parser.print_help_format()
        sys.exit(0)

    if opts.version:
        from rsstail import __version__
        print('rsstail version %s' % __version__)
        sys.exit(0)

    if len(args) == 0:
        parser.print_help()
        sys.exit(0)

    if opts.verbose:
        log.setLevel(logging.DEBUG)

    if opts.newer:
        try:
            opts.newer = parse_date(opts.newer)
        except ValueError as e:
            die(e)
        log.debug('showing entries newer than %s', opts.newer)
    else:
        opts.newer = None

    signal.signal(signal.SIGINT, sigint_handler)

    formatter = setup_formatter(opts)

    # { url1 : (None,  # etag
    #           None,  # last modified (time tuple)
    #           None)} # last update time (time tuple)
    feeds = dict.fromkeys(args, (None, None, None))

    # global iteration count
    iteration = 1

    # handle stdout encoding on Python 2.x
    if sys.version_info.major == 2 and not sys.stdout.isatty():
        import locale, codecs
        encoding = locale.getpreferredencoding()
        sys.stdout = codecs.getwriter(encoding)(sys.stdout)
        # todo: does this break PYTHONENCODING?

    while True:
        try:
            tick(feeds, opts, formatter, iteration)

            if isinstance(opts.iterations, int) and iteration >= opts.iterations:
                log.debug('maximum number of iterations reached: %d', opts.iterations)
                sigint_handler()

            iteration += 1

            log.debug('sleeping for %d seconds', opts.interval)
            time.sleep(opts.interval)
        except Exception:
            if not opts.nofail:
                log.exception('')
                sys.exit(1)


if __name__ == '__main__':
    main()
