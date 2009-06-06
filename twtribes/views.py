from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.cache import cache
from django.conf import settings

from datetime import datetime

from urllib2 import HTTPError
import twitterext
import pytz

from models import *

def status_sorter(s1, s2):
    if s1.created_at_in_seconds < s2.created_at_in_seconds:
        return 1
    elif s1.created_at_in_seconds > s2.created_at_in_seconds:
        return -1
    return 0

def parse_twitter_http_error(e):
    if e.code == 401:
        error = "Unknown Username/Password"
    elif e.code == 400:
        error = "Twitter API Rate Limit Exceeded - Please try back later"
    elif e.code == 404:
        error = "Unknown User"
    else:
        error = str(e)
    return error

def get_api(tribe):
    acc, pwd = tribe.master_account, tribe.master_password
    if acc and pwd:
        api = twitterext.SearchApi(username=acc, password=pwd)
    else:
        api = twitterext.SearchApi()
    return api
    
def tribe(request, tribe_slug, tribe_template='twtribes/tribe.html', error_template='twtribes/tribe_error.html'):

    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')
    
    # initialize the API, using the master tribe username and password
    # using the username and password for a tribe allows for API rate limit lifting at Twitter    
    try:
        status_list = cache.get(tribe.slug+'_status')
        if not status_list:
            # if the status list isn't in the cache, generate it from the API
            api = get_api(tribe)
            status_list = []
            for m in members:
                try:
                    status_list.extend(api.GetUserTimeline(user=m.twitter_account, count=tribe.max_status))
                except HTTPError, e:
                    # watch for unknown user exceptions as we retrieve the status list
                    if e.code != 404:
                        raise # reraise the exception if it's not an unknown user
                        
            # sort the statuses 
            status_list.sort(status_sorter)
            
            # add a datetime to each status (better done on creation)
            for s in status_list:
                s.created_at_as_datetime = pytz.utc.localize(datetime.fromtimestamp(s.created_at_in_seconds)).astimezone(pytz.timezone('US/Central'))
            
            cache.set(tribe.slug+'_status', status_list, tribe.update_interval)
                        
    except HTTPError, e:
        # an HTTPError means that the Twitter api returned an error, parse it and return it to an error template
        error = parse_twitter_http_error(e)
         
        return render_to_response(error_template,
            { 'error' : error, 'exception' : e }, 
            context_instance=RequestContext(request))
    
    return render_to_response(tribe_template,
        { 'tribe' : tribe, 'members' : members, 'status_list' : status_list }, 
        context_instance=RequestContext(request))
        
def tribe_search(request, tribe_slug, tribe_template='twtribes/tribe_search.html', error_template='twtribes/tribe_error.html'):

    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')

    # initialize the API, using the master tribe username and password
    # using the username and password for a tribe allows for API rate limit lifting at Twitter
    try:
        search_results = cache.get(tribe.slug+'_search')
        if not search_results:
            api=get_api(tribe)
            search_results = api.Search(" OR ".join([t.term for t in tribe.interestterm_set.all()]))
            cache.set(tribe.slug, search_results, tribe.update_interval)

    except HTTPError, e:
        # an HTTPError means that the Twitter api returned an error, parse it and return it to an error template
        error = parse_twitter_http_error(e)

        return render_to_response(error_template,
            { 'error' : error, 'exception' : e }, 
            context_instance=RequestContext(request))

    return render_to_response(tribe_template,
        { 'tribe' : tribe, 'members' : members, 'search' : search_results, 'results' : search_results.results }, 
        context_instance=RequestContext(request))