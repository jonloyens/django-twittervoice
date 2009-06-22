from django import template
from django.utils.safestring import mark_safe

import re

register = template.Library()

def create_link(match):
    s = match.group(0)
    return "<a href='"+s+"'>"+s+"</a>"

def create_at(match):
    s = match.group(0)
    return "<a href='http://www.twitter.com/"+s[1:]+"'>"+s+"</a>"

def convert_to_links(update):
    """ Template filter that converts @username and hyperlinks into actual links """
    
    # replace links with actual hyperlinks
    update = re.sub(r"(?i)\b(http(s?)://|www\.)[-a-z0-9_/+&amp;=#;%?.!~*'(|)]*(\w\b|[/+&amp;=])",
        create_link,
        update)
        
    #replace @username with hyperlinks
    update = re.sub(r"@\w+",
        create_at,
        update)    
    
    return mark_safe(update)
    
convert_to_links.is_safe = True
register.filter('convert_to_links', convert_to_links)