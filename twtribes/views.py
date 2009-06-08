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

def get_search_results(tribe, check_cache=True):
    """ This function is used to call the twitter api to seach for a tribe's interest terms
        either from a view or in a cronjob to cache the interest search in advance
        Note: there is also the utility function 'cache_search' that will prefetch all tribes status updates"""
    
    if check_cache:
        search_results = cache.get(tribe.slug+'_search')
    else:
        search_results = None
        
    if not search_results:
        api=get_api(tribe)
        search_results = api.Search(" OR ".join([t.term for t in tribe.interestterm_set.all()]))
        cache.set(tribe.slug, search_results, tribe.update_interval)

    return search_results

def cache_search(slug=None):
    """ Function to be called in a cronjob to cache the search results for interest terms
        for all tribes or one tribe dependent on parameters
        
        Calling with slug set to None will retrieve all tribes """
    if slug:
        tribes = Tribe.objects.filter(slug=slug)
    else:
        tribes = Tribe.objects.all()

    for tribe in tribes:
        try:
            get_search_results(tribe, False)
        except HTTPError, e:
            # an HTTPError means that the Twitter api returned an error, parse it and pass it back
            error = parse_twitter_http_error(e)
            return error
            
def get_status_updates(tribe, members, check_cache=True):
    """ This function is to be used to fetch all status updates for a particular tribe or in a cronjob 
        to cache tribe statuses in advance
        Note: there is also the utility function 'cache_tribes' that will prefetch all tribes status updates"""
    
    if check_cache:
        status_list = cache.get(tribe.slug+'_status')
    else:
        status_list = None
    
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
        
        # add a datetime to each status (better done on creation but will need to extend python-twitter)
        for s in status_list:
            s.created_at_as_datetime = pytz.utc.localize(datetime.fromtimestamp(s.created_at_in_seconds)).astimezone(pytz.timezone('US/Central'))
        
        cache.set(tribe.slug+'_status', status_list, tribe.update_interval)
        
    return status_list

def cache_tribes(slug=None):
    """ Function to be called in a cronjob to cache the status lists for all tribes or one tribe dependent on parameters
        Calling with slug set to None will retrieve all tribes """
    if slug:
        tribes = Tribe.objects.filter(slug=slug)
    else:
        tribes = Tribe.objects.all()
    
    for tribe in tribes:
        try:
            get_status_updates(tribe, tribe.member_set.all(), False)
        except HTTPError, e:
            # an HTTPError means that the Twitter api returned an error, parse it and pass it back
            error = parse_twitter_http_error(e)
            return error
    
def tribe(request, tribe_slug, tribe_template='twtribes/tribe.html', error_template='twtribes/tribe_error.html'):
    """ Django view function that displays collated tribe member statuses
    """
    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')
    
    # initialize the API, using the master tribe username and password
    # using the username and password for a tribe allows for API rate limit lifting at Twitter    
    try:
        status_list = get_status_updates(tribe, members)
        
        if request.GET and 'filter' in request.GET:
            f = request.GET['filter'].upper()
            status_list = [s for s in status_list if s.text.upper().find(f) > -1 or s.user.screen_name.upper().find(f) > -1]
                        
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
    """ Django view function that displays search results of tribe interest terms 
    """
    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')

    # initialize the API, using the master tribe username and password
    # using the username and password for a tribe allows for API rate limit lifting at Twitter
    try:
        search_results = get_search_results(tribe)
        results = search_results.results
        if request.GET and 'filter' in request.GET:
            f = request.GET['filter']
            results = [s for s in results if s.text.find(f) > -1 or s.user.from_user.upper().find(f) > -1]
            
    except HTTPError, e:
        # an HTTPError means that the Twitter api returned an error, parse it and return it to an error template
        error = parse_twitter_http_error(e)

        return render_to_response(error_template,
            { 'error' : error, 'exception' : e }, 
            context_instance=RequestContext(request))

    return render_to_response(tribe_template,
        { 'tribe' : tribe, 'members' : members, 'search' : search_results, 'results' : results }, 
        context_instance=RequestContext(request))