#!/usr/bin/python

# -*- coding: utf-8 -*-

# make_svg() comes from https://github.com/Bekt/invatar/

from random import randint, seed
import hashlib

from bottle import redirect

from ui_user import User

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen
except ImportError:
    from urllib import urlencode
    from urllib2 import urlopen

# Will be populated by the UI with it's own value
app = None


defaults = {
    'size': 100,
    'font_size': 60,
    'font_family': 'Arial',
    'bg': 'black',
    'color': 'white',
    'text': 'KB'
}


def make_svg(**options):
    """
        Builds a simple SVG text square with a centered text.
        options: size, font_size, font_family, bg, color, text
        :return (str)
    """
    if options is not None and not isinstance(options, dict):
        raise ValueError('options should be None or a type of dict.')

    if 'size' in options and 'font_size' not in options:
        options['font_size'] = int(options['size'] * 0.6)

    default_value = defaults.copy()
    default_value.update(options)
    options = default_value

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="{size}px" height="{size}px">
      <g>
        <rect x="0" y="0" fill="{bg}" width="{size}px" height="{size}px">
        </rect>
        <text y="50%" x="50%" fill="{color}"
              text-anchor="middle" dominant-baseline="central"
              style="font-family: {font_family}; font-size: {font_size}px">
          {text}
        </text>
      </g>
    </svg>
    """.format(**options)

    return svg


def _background_color(name):
    """
        Generate a random background color.
        Brighter colors are dropped because text is white.

        :param seed: Seed used by the random generator
        (same seed will produce same color every time)
    """
    seed(name)
    red = green = blue = 255
    while red + green + blue > 255 * 2:
        red = randint(0, 255)
        green = randint(0, 255)
        blue = randint(0, 255)
    return '#{:02x}{:02x}{:02x}'.format(red, green, blue)


def get_svg_avatar(name, size=256):
    # Default to SVG generated avatar
    app.response.content_type = 'image/svg+xml'

    options = dict()
    options['text'] = name[0].upper()
    options['bg'] = _background_color(name)
    options['size'] = size

    return make_svg(**options)


def get_gravatar_url(email, size=256, default='404'):
    try:
        # import urllib.request, urllib.error, urllib.parse
        # import urllib.request, urllib.parse, urllib.error
        #
        parameters = {'s': size, 'd': default}
        url = "https://secure.gravatar.com/avatar/%s?%s" % (
            hashlib.md5(email.lower()).hexdigest(), urlencode(parameters)
        )
        ret = urlopen(url)
        if ret.code == 200:
            return url
    except Exception:
        pass

    return None


def get_avatar(name):
    user = app.get_user()
    contact = User.from_contact(app.datamgr.get_contact(name=name, user=user) or app.redirect404())

    app.response.set_header("Cache-Control", "public, max-age=3200")

    size = int(app.request.GET.get('s', 256))

    # :TODO:maethor:170917: Make this possible again ?
    # '/static/photos/%s' % user.get_username()

    # :COMMENT:maethor:170917: Sadly gravatar doesn't allow to default to SVG picture
    # So we need to check if gravatar is returning a result, or return the SVG ourselves.
    if app.gravatar and contact.email != 'none':
        gravatar = get_gravatar_url(contact.email, size=size)
        if gravatar is not None:
            redirect(gravatar)

    return get_svg_avatar(contact.get_username(), size)


pages = {
    get_avatar: {
        'name': 'GetAvatar', 'route': '/avatar/:name'
    },
    get_svg_avatar: {
        'name': 'GetSvgAvatar', 'route': '/avatar/svg/:name.svg'
    }
}
