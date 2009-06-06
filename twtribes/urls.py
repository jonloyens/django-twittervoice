from django.conf.urls.defaults import *

urlpatterns = patterns('twtribes.views',
    url(r'^(?P<tribe_slug>\w+)/$', 'tribe', {}, name='show_tribe'),
    url(r'^(?P<tribe_slug>\w+)/search/$', 'tribe_search', {}, name='show_tribe_terms'),
)