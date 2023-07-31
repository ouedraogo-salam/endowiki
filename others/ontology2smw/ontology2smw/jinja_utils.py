from jinja2 import (FileSystemLoader,
                    Environment,
                    environment)
from typing import Dict, List, Union, Optional
from pathlib import Path
from urllib.parse import urlsplit


def url_termination(value):
    '''returns either http://...#foo -> foo
    or http://.../foo/bar -> bar'''
    split_url = urlsplit(value)
    if split_url.fragment:
        subject = split_url.fragment  # after hash
    else:
        subject = split_url.path.split('/')[-1]
    return subject


def load_template(template: str):
    f_loader = FileSystemLoader(Path(__file__).parent / 'templates')
    env = Environment(loader=f_loader)
    template_obj = env.get_template(template)
    return template_obj


def render_template(template: str,
                    ns_prefix: str,
                    term_dict: Union[Dict, List],
                    term_name: Optional[str],
                    page_info: Optional[Dict],
                    prop_datatype=None) -> str:
    environment.DEFAULT_FILTERS['url_termination'] = url_termination
    template_obj = load_template(template=template)
    wiki_item = template_obj.render(
        ns_prefix=ns_prefix,
        term_dict=term_dict,
        term_name=term_name,
        page_info=page_info,
        prop_datatype=prop_datatype
    )
    return wiki_item
