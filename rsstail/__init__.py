# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

import sys
import time

from datetime import datetime as dt
from functools import reduce, lru_cache

import feedparser
import pygogo as gogo

__version__ = '0.4.0'
__title__ = 'RSS tail'
__package_name__ = 'rsstail'
__author__ = 'Reuben Cummings'
__description__ = 'An RSS feed monitor mimicking tail -f'
__email__ = 'reubano@gmail.com'
__license__ = 'BSD'
__copyright__ = 'Copyright 2017 Reuben Cummings'

LOGGER = gogo.Gogo(__name__, monolog=True).logger


@lru_cache(maxsize=32)
def last_update(entry_dates):
    return max(entry_dates) if entry_dates else time.strptime('1900', '%Y')


def write_entries(entries=None, **kwargs):
    stream = kwargs.get('stream', sys.stdout)
    seen = kwargs.get('seen')
    formatter = kwargs.get('formatter')

    if kwargs.get('reverse'):
        entries = reversed(entries)

    if seen is not None:
        to_add = [entry for entry in entries if entry.id not in seen]
        seen.update(entry.id for entry in to_add)
    else:
        to_add = entries

    for entry in to_add:
        if formatter:
            content = formatter(entry)
        else:
            content = '{}\n'.format(entry['title'])

        stream.write(content)

    stream.flush()


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

    if not {'modified_parsed', 'updated_parsed'}.issubset(feed):
        _dates = (e.updated_parsed for e in entries if e.get('updated_parsed'))
        dates = tuple(_dates)

    return {
        'entries': entries,
        'etag': feed.get('etag', kwargs.get('etag')),
        'modified': feed.get('modified_parsed') or last_update(dates),
        'updated': feed.get('updated_parsed') or last_update(dates)}


def tail(urls, iteration=0, interval=300, extra=None, **kwargs):
    logger = kwargs.get('logger', LOGGER)

    if kwargs.get('iterations') and iteration >= kwargs['iterations']:
        msg = 'maximum number of iterations reached: %d'
        logger.debug(msg, kwargs['iterations'])
        return kwargs
    elif iteration:
        # sleep first so that we don't have to wait an interval before checking
        # iteration count
        logger.debug('sleeping for %d seconds', interval)
        time.sleep(interval)

    extra = extra or {}

    for url in urls:
        kwargs.update(extra.get(url, {}))
        extra[url] = parse_url(url, iteration, **kwargs)
        kwargs.update(extra[url])
        write_entries(**kwargs)

    return tail(urls, iteration + 1, interval=interval, extra=extra, **kwargs)
