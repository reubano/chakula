#!/usr/bin/env python
# encoding: utf-8

from chakula.formatter import Formatter


def test_placeholder_style_detect():
    f = Formatter('{asdf} {zxcv} {qwerty}')
    assert f.is_newstyle

    f = Formatter('%(asdf)s %(zxcv)s %(qwerty)-20s')
    assert not f.is_newstyle

    f = Formatter('{asdf} %(zxcv)s %(qwerty)s')
    assert not f.is_newstyle

    f = Formatter('{asdf} {zxcv} %(qwerty)s')
    assert f.is_newstyle

    f = Formatter('{asdf} {zxcv} %(qwerty)s %(azerty)s')
    assert not f.is_newstyle
