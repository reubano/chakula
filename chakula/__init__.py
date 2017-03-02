# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

import sys
import time

from datetime import datetime as dt
from functools import reduce, lru_cache
from traceback import format_exception
from bisect import bisect

import feedparser
import pygogo as gogo

__version__ = '0.7.4'
__title__ = 'chakula'
__package_name__ = 'chakula'
__author__ = 'Reuben Cummings'
__description__ = 'An RSS feed monitor mimicking tail -f'
__email__ = 'reubano@gmail.com'
__license__ = 'BSD'
__copyright__ = 'Copyright 2017 Reuben Cummings'

LOGGER = gogo.Gogo(__name__, monolog=True).logger


@lru_cache(maxsize=32)
def last_update(entry_dates):
    return max(entry_dates) if entry_dates else time.strptime('1900', '%Y')


def write_entries(entries, **kwargs):
    logger = kwargs.get('logger', LOGGER)
    stream = kwargs.get('stream', sys.stdout)
    seen = kwargs.get('seen')
    formatter = kwargs.get('formatter')

    if kwargs.get('reverse'):
        entries.reverse()

    if seen is not None:
        to_add = [entry for entry in entries if entry.id not in seen]
        seen.update(entry.id for entry in to_add)
    else:
        to_add = entries

    logger.debug('Writing {} new entries'.format(len(to_add)))

    for entry in to_add:
        if formatter:
            content = formatter(entry)
        else:
            content = '{}\n'.format(entry['title'])

        try:
            stream.write(content)
        except TypeError:
            stream.write(content.encode('utf-8'))

    try:
        stream.flush()
    except AttributeError:
        pass

    if kwargs.get('write_handler'):
        kwargs['write_handler'](to_add)


def parse_url(url, iteration, initial=None, **kwargs):
    logger = kwargs.get('logger', LOGGER)
    updated = kwargs.get('updated')
    newer = kwargs.get('newer')
    pkwargs = {k: v for k, v in kwargs.items() if k in {'etag', 'modified'}}
    feed = feedparser.parse(url, **pkwargs)

    if feed.bozo == 1:
        safeexc = (feedparser.CharacterEncodingOverride,)

        if not isinstance(feed.bozo_exception, safeexc):
            msg = 'feed error %r:\n%s' % (url, feed.bozo_exception)
            raise ValueError(msg)

    entries = feed.entries if iteration else feed.entries[:initial]

    if updated and newer:
        newer_than = max([updated, newer])
    else:
        newer_than = updated or newer

    if newer_than:
        formatted = time.strftime('%Y/%m/%d %H:%M:%S', newer_than)
        logger.debug('selecting entries newer than %s', formatted)
        entries = [
            entry for entry in entries if entry.published_parsed > newer_than]

    if not feed.get('updated_parsed') and entries:
        dates = (e.updated_parsed for e in entries if e.get('updated_parsed'))
        def_updated = last_update(tuple(dates))
    else:
        def_updated = updated

    info = {
        'etag': feed.get('etag', kwargs.get('etag')),
        'modified': feed.get('modified_parsed'),
        'updated': feed.get('updated_parsed') or def_updated}

    return entries, info


def parse_interval(interval):
    pairs = [('secs', 0), ('minutes', 60), ('hours', 3600), ('days', 86400)]
    grades = [pair[0] for pair in pairs]
    breakpoints = [pair[1] for pair in pairs][1:]

    def get_grade(score):
        i = bisect(breakpoints, score)
        return grades[i]

    grade = get_grade(interval)
    divisor = dict(pairs)[grade]
    return round(interval / divisor, 2), grade


def tail(urls, iteration=0, interval=300, extra=None, **kwargs):
    logger = kwargs.get('logger', LOGGER)
    extra = extra or {}

    if kwargs.get('iterations') and iteration >= kwargs['iterations']:
        msg = 'maximum number of iterations reached: %d'
        logger.info(msg, kwargs['iterations'])
        return extra
    elif iteration:
        # sleep first so that we don't have to wait an interval before checking
        # iteration count
        parsed = parse_interval(interval)
        logger.info('sleeping for {} {}'.format(*parsed))
        time.sleep(interval)

    for url in urls:
        kwargs.update(extra.get(url, {}))

        try:
            entries, extra[url] = parse_url(url, iteration, **kwargs)
            kwargs.update(extra[url])
            write_entries(entries, **kwargs)
        except Exception:
            if kwargs.get('fail'):
                raise
            else:
                traceback_strings = format_exception(*sys.exc_info())
                logger.error(''.join(traceback_strings))

    if kwargs.get('tail_handler'):
        kwargs['tail_handler'](extra)

    return tail(urls, iteration + 1, interval=interval, extra=extra, **kwargs)
