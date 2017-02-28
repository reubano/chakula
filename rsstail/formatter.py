# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

import time
from re import findall
from datetime import datetime as dt
from functools import reduce

DEF_TIME_FMT = '%Y/%m/%d %H:%M:%S'


def attrgetter(item, default=''):
    """operator.attrgetter with a default value."""
    reducer = lambda obj, name: getattr(obj, name, default)
    return lambda obj: reduce(reducer, item.split('.'), obj)


PLACEHOLDERS = {
    'author': attrgetter('author'),
    'id': attrgetter('id'),
    'title': attrgetter('title'),
    'link': attrgetter('link'),
    'url': attrgetter('link'),
    'description': attrgetter('description'),
    'desc': attrgetter('description'),
    'pubdate': attrgetter('published_parsed'),
    'updated': attrgetter('updated_parsed'),
    'created': attrgetter('created_parsed'),
    'timestamp': lambda _: None,
    'expired': lambda _: None,
    'comments': lambda _: None,
}


class Formatter(object):
    """I interpolate a format string with feedparser values."""
    def __init__(self, fmt, time_fmt=DEF_TIME_FMT):
        self.fmt = fmt
        self.time_fmt = time_fmt

    @classmethod
    def from_fields(cls, fields, time_fmt=DEF_TIME_FMT, show_heading=False):
        fmt = []

        for field in fields:
            new_line = '\n' if field in {'desc', 'description'} else ''

            if show_heading and field != 'timestamp':
                entry = '{new_line}{tc_field}: %({field})s'
            else:
                entry = '{new_line}%({field})s'

            opts = {
                'field': field, 'tc_field': field.title(),
                'new_line': new_line}

            fmt.append(entry.format(**opts))

        fmt = '{}\n'.format('  '.join(fmt))
        return cls(fmt, time_fmt=time_fmt)

    @property
    def is_newstyle(self):
        """Check if we're dealing with {} or %()s placeholders."""
        new_style = len(findall(r'{[^}]*}', self.fmt))
        old_style = len(findall(r'%\([^\(]*\)[^ ]*s', self.fmt))
        return new_style > old_style

    def __call__(self, entry):
        opts = {field: self.get_value(field, entry) for field in PLACEHOLDERS}
        return self.fmt.format(**opts) if self.is_newstyle else self.fmt % opts

    def get_value(self, field, entry):
        value = PLACEHOLDERS[field](entry)

        if field in {'pubdate', 'updated'}:
            value = time.strftime(self.time_fmt, value)
        elif field == 'timestamp':
            value = dt.now().strftime(self.time_fmt)

        return value
