#!/usr/bin/env python3

import gi
import os
import re
import math
import cairo
import pathlib
import argparse
import requests
import subprocess
import pypandoc
import uuid

from PIL import Image, UnidentifiedImageError
from urllib.parse import urlparse, unquote
from requests.exceptions import HTTPError
from gi.repository.GLib import Error

gi.require_version('Rsvg', '2.0')

from gi.repository import Rsvg  # noqa: E402


def readfile(p):
    with open(p, 'r') as f:
        return f.read()


def write_file(p, t, i):
    with open(p, t) as f:
        f.write(i)


def download(p):
    res = requests.get(p)

    try:
        res.raise_for_status()
    except HTTPError:
        return None

    return res.content


def file_exists(p):
    if os.path.isfile(p):
        return True

    return False


def pixeltomm(p):
    value = math.floor(p * 25.4) / 96

    return value


def workingdir():
    dir = pathlib.Path().absolute()

    return dir


def makedir(p):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)


def file_name(p):
    name = os.path.splitext(os.path.basename(p))[0]

    return name


def file_extension(p):
    name = os.path.splitext(os.path.basename(p))[1]

    return name


def file_path(p):
    dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(dir, *p.split('/'))

    return path


def image_open(p):
    try:
        image = Image.open(p)
    except FileNotFoundError:
        return None
    except UnidentifiedImageError:
        return None

    return image


def image_dimensions(p):
    image = image_open(p)

    if not image:
        return None

    width, height = image.size
    dimensions = [width, height]

    return dimensions


def convert_gif_image(p, o):
    image = image_open(p)

    if not image:
        return None

    image.save(o)

    image = image_open(o)

    if not image:
        return None

    width, height = image.size
    dimensions = [width, height]

    return dimensions


def convert_svg_image(p, o):
    handle = Rsvg.Handle()

    try:
        svg = handle.new_from_file(p)
    except Error:
        return

    unscaled_width = svg.props.width
    unscaled_height = svg.props.height

    svg_surface = cairo.SVGSurface(None, unscaled_width, unscaled_height)
    svg_context = cairo.Context(svg_surface)
    svg_context.save()
    svg.render_cairo(svg_context)
    svg_context.restore()
    svg_surface.write_to_png(o)

    dimensions = [unscaled_width, unscaled_height]

    return dimensions


def argparser():
    parser = argparse.ArgumentParser(description='Process a markdown file.')

    parser.add_argument('--input', dest='input',
                        required=True, help='define input file')
    parser.add_argument('--output', dest='output',
                        required=True, help='define output file_name')
    parser.add_argument('--format', dest='format',
                        required=True, help='define input format')

    args = parser.parse_args()

    return args


def convert_html(i, f):
    html = pypandoc.convert_file(i, 'html', format=f)

    return html


def convert_markdown(i, f):
    if f == 'gfm':
        f = 'html'

    latex_body = pypandoc.convert_file(i, 'latex', format=f)
    latex_header = readfile('header.tex')
    latex_doc = '{document}'

    latex = '{0}\n\\begin{2}\n\n{1}\n\\end{2}'.format(
        latex_header, latex_body, latex_doc
    )

    return latex


def replace_rule(document):
    rule_pattern = re.compile(r'\\rule\{0.5\\linewidth\}')
    rule_replace = r'\\par\\noindent\\rule{\\textwidth}'
    latex = re.sub(rule_pattern, rule_replace, document)

    return latex


def replace_verbatim(document):
    verbatim_pattern = re.compile(r'\\begin{Verbatim}')
    verbatim_replace = r'\\begin{Verbatim}[breaklines=true]'
    latex = re.sub(verbatim_pattern, verbatim_replace, document)

    return latex


def replace_quote(document):
    quote_begin_replace = r'\\begin{quoting}'
    quote_end_replace = r'\\end{quoting}'

    quote_begin_pattern = re.compile(r'\\begin\{quote\}')
    quote_end_pattern = re.compile(r'\\end\{quote\}')

    latex = re.sub(quote_begin_pattern, quote_begin_replace, document)
    latex = re.sub(quote_end_pattern, quote_end_replace, latex)

    return latex


def find_all_images(latex):
    img_url_pattern = re.compile(
        r'\\(includegraphics){([a-zA-Z0-9$-_@.&+!*\(\), ]+)}')

    images = re.findall(img_url_pattern, latex)

    return images


def extract_image_path(raw_image_url):
    image_file = urlparse(raw_image_url).path

    image_source_path = file_path('/assets/{}{}'.format(
        str(uuid.uuid4()), file_extension(image_file)))

    return image_source_path


def image_relative_path(image_source_path, image_target_path):
    if file_extension(image_source_path) != '.gif' and file_extension(image_source_path) != '.svg':  # noqa: E501
        image_relative_path = './assets/{}{}'.format(
            file_name(image_source_path),
            file_extension(image_source_path))

        image_relative_string = '{{./assets/{}{}}}'.format(
            file_name(image_target_path),
            file_extension(image_target_path))
    else:
        image_relative_path = './assets/{}.png'.format(
            file_name(image_target_path))

        image_relative_string = '{{./assets/{}.png}}'.format(
            file_name(image_target_path))

    return image_relative_path, image_relative_string


def check_convert_image(image_source_path, image_target_path):
    dimensions = None

    image_target_path = file_path('/assets/{}.png'.format(
        file_name(image_target_path)))

    if file_extension(image_source_path) == '.svg':
        dimensions = convert_svg_image(
            image_source_path, image_target_path)

    elif file_extension(image_source_path) == '.gif':
        dimensions = convert_gif_image(
            image_source_path, image_target_path)

    return dimensions


def check_convert_pixel(dimensions):
    width = pixeltomm(dimensions[0])

    if width <= 170:
        return True

    return False


def iterate_images(images, latex):
    for image in images:
        raw_image_url = unquote(image[1])
        print('raw_image_url', raw_image_url)

        # TODO: need to prepend base url
        if not raw_image_url.startswith('http'):
            raw_image_url = raw_image_url

        image_source_path = extract_image_path(raw_image_url)
        print('image_source_path', image_source_path)

        image_target_path = file_path('/assets/{}{}'.format(
            file_name(image_source_path),
            file_extension(image_source_path)))
        print('image_target_path', image_target_path)

        resource = download(raw_image_url)

        if resource:
            write_file(image_source_path, 'wb', resource)

        dimensions = check_convert_image(image_source_path, image_target_path)
        image_path, image_relative_string = image_relative_path(
            image_source_path, image_target_path)
        print('image_path', image_path)
        print('image_relative_string', image_relative_string)

        latex = latex.replace(raw_image_url, image_path)

        img_pattern = re.compile(
            r'\\(includegraphics{})'.format(image_relative_string))

        if not dimensions:
            dimensions = image_dimensions(image_path)

        print('dimensions', dimensions)

        # when image width less or equal 170
        if dimensions and check_convert_pixel(dimensions):
            img_replace = r'\\includegraphics[width={0}mm, height={1}mm]{2}'.format(
                pixeltomm(dimensions[0]), pixeltomm(dimensions[1]),
                image_relative_string)
        else:
            img_replace = r'\\includegraphics[width=0.95\\textwidth]{}'.format(
                image_relative_string)

        latex = re.sub(img_pattern, img_replace, latex)
        print('\n')

    return latex


def convert_latex(target):
    subprocess.call('xelatex -interaction nonstopmode -output-directory {} {}'.format(
        file_path('/output'), file_path('/output/{}.tex'.format(target))),
        shell=True)


def main():
    args = argparser()

    source = args.input
    format = args.format

    makedir(file_path('/output'))
    makedir(file_path('/assets'))

    if args.format == 'gfm':
        html = convert_html(source, format)
        source = file_path('/output/{}.html'.format(args.output))
        write_file(source, 'w', html)

    latex = convert_markdown(source, format)
    latex = replace_rule(latex)
    latex = replace_quote(latex)
    latex = replace_verbatim(latex)
    images = find_all_images(latex)

    latex = iterate_images(images, latex)
    write_file(file_path('/output/{}.tex'.format(args.output)), 'w', latex)
    convert_latex(args.output)


if __name__ == '__main__':
    main()
