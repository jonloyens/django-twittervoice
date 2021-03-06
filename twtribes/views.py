from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.cache import cache
from django.conf import settings

from datetime import datetime

from urllib2 import HTTPError, URLError
import twitter
import calendar
import email
import pytz

from models import *

def status_sorter(s1, s2):
    if s1["created_at_in_seconds"] < s2["created_at_in_seconds"]:
        return 1
    elif s1["created_at_in_seconds"] > s2["created_at_in_seconds"]:
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

def get_api(tribe, domain="api.twitter.com"):
    acc, pwd = tribe.master_account, tribe.master_password
    
    if hasattr(settings, "TWITTER_USE_OAUTH") and settings.TWITTER_USE_OAUTH:
        auth_method = twitter.oauth.OAuth(settings.TWITTER_OATH_TOKEN, settings.TWITTER_OATH_SECRET, settings.TWITTER_OATH_CONSUMER_KEY, settings.TWITTER_OATH_CONSUMER_SECRET)
    elif acc and pwd:
        auth_method = twitter.auth.UserPassAuth(username=acc, password=pwd)
    else:
        auth_method = twitter.auth.NoAuth()
        
    return twitter.api.Twitter(auth=auth_method, domain=domain)

def get_search_results(tribe, page=None, check_cache=True, filter_results=True):
    """ This function is used to call the twitter api to seach for a tribe's interest terms
        either from a view or in a cronjob to cache the interest search in advance
        
        Can also be called wtih a page object to build the results for a page (i.e. a group of interest terms)
        
        Note: there is also the utility function 'cache_search' that will prefetch all tribes status updates"""
    
    if check_cache:
        search_results = cache.get(tribe.slug+'_search'+ ("_"+page.slug) if page else "" )
    else:
        search_results = None
        
    if not search_results:
        try:
            api=get_api(tribe, "search.twitter.com")
        except URLError, e:
            pass # swallow potential servname/node name errors from the twitter api. TODO: Should probably log this
        
        if page:
            query = '"'+'" OR "'.join([t.term for t in page.terms.all()])+'"'
        else:
            query = '"'+'" OR "'.join([t.term for t in tribe.interestterm_set.all()])+'"'
        
        search_results = api.search(q=query, rpp=100)
        
        if filter_results:
            search_results = filter_search_results(tribe, search_results)
        
        # add a datetime to each status (better done on creation but will need to extend python twitter tools)
        for s in search_results["results"]:
            s["created_at_in_seconds"] = calendar.timegm(email.utils.parsedate(s["created_at"]))
            s["created_at_as_datetime"] = datetime.fromtimestamp(s["created_at_in_seconds"])
            
            if hasattr(settings, "ADJUST_TWITTER_TIMEZONE")  and settings.ADJUST_TWITTER_TIMEZONE:
                s["created_at_as_datetime"] = pytz.utc.localize(s["created_at_as_datetime"]).astimezone(pytz.timezone(settings.TIME_ZONE))
            
        cache.set(tribe.slug+'_search'+ ("_"+page.slug) if page else "", search_results, tribe.update_interval)
        
    return search_results

def filter_search_results(tribe, search_results):
    """ Return the search results that are 'allowable': they don't match any of
        the excluded filters. """
    
    new_results = []
    # filter out excluded users
    for result in search_results["results"]:
        # check to see if this user is in the excluded accounts list
        if not tribe.excludeduser_set.filter(twitter_account=result["from_user"]):
            if matches_no_regexps(tribe, result["text"]):
                new_results.append(result)

    search_results["results"] = new_results

    return search_results

def matches_no_regexps(tribe, text_to_check):
    """Returns True if this text doesn't match an enabled exclude
       regular expressions"""
    for regexp in tribe.excludedregexp_set.filter(enabled=True):
        if regexp.search(text_to_check):
            return False
    return True    
    
def cache_search(slug=None, page_slug=None):
    """ Function to be called in a cronjob to cache the search results for interest terms
        for all tribes or one tribe dependent on parameters
        
        Can also be used to cache an individual interest page if the correct slug is provided
        
        Calling with slug set to None will retrieve all tribes """
    if slug:
        tribes = Tribe.objects.filter(slug=slug)
        if page_slug:
            page = Page.objects.filter(slug=page_slug, tribe=tribes[0])
    else:
        tribes = Tribe.objects.all()
        page = None

    for tribe in tribes:
        try:
            get_search_results(tribe, page, False)
        except twitter.api.TwitterHTTPError, e:
            # an HTTPError means that the Twitter api returned an error, parse it and pass it back
            error = parse_twitter_http_error(e.e)
            return error
            
def get_status_updates(tribe, members, check_cache=True, filter_results=True):
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
                status_list.extend(api.statuses.user_timeline(id=m.twitter_account, count=tribe.max_status))
            except twitter.api.TwitterHTTPError, e:
                # watch for unknown user exceptions as we retrieve the status list, swallow the exception if we get them
                if e.e.code != 404 and e.e.code != 401:
                    raise # reraise the exception if it's not an unknown user or the user is protected
            except URLError, e:
                pass # swallow potential servname/node name errors from the twitter api. TODO: Should probably log this
                    
        # filter out by regular expression
        if filter_results:
            status_list = [status for status in status_list if matches_no_regexps(tribe, status["text"])]
                
        # add a datetime to each status (better done on creation but will need to extend python twitter tools)
        for s in status_list:
            s["created_at_in_seconds"] = calendar.timegm(email.utils.parsedate(s["created_at"]))
            s["created_at_as_datetime"] = datetime.fromtimestamp(s["created_at_in_seconds"])
            
            if hasattr(settings, "ADJUST_TWITTER_TIMEZONE") and settings.ADJUST_TWITTER_TIMEZONE:
                s["created_at_as_datetime"] = pytz.utc.localize(s["created_at_as_datetime"]).astimezone(pytz.timezone(settings.TIME_ZONE))
        
        # sort the statuses 
        status_list.sort(status_sorter)
        
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
        except twitter.api.TwitterHTTPError, e:
            # an HTTPError means that the Twitter api returned an error, parse it and pass it back
            error = parse_twitter_http_error(e.e)
            return error
    
def tribe(request, tribe_slug, tribe_template='twtribes/tribe.html', error_template='twtribes/tribe_error.html'):
    """ Django view function that displays collated tribe member statuses
    """
    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')
    
    try:
        status_list = get_status_updates(tribe, members)
        if request.GET and 'filter' in request.GET:
            f = request.GET['filter']
            f_upper = f.upper()
            status_list = [s for s in status_list if s["text"].upper().find(f_upper) > -1 or s["user"]["screen_name"].upper().find(f_upper) > -1]
        else:
            f = None
                            
    except twitter.api.TwitterHTTPError, e:
        # an HTTPError means that the Twitter api returned an error, parse it and return it to an error template
        error = parse_twitter_http_error(e.e)
        return render_to_response(error_template,
            { 'error' : error, 'exception' : e }, 
            context_instance=RequestContext(request))
    
    return render_to_response(tribe_template,
        { 'tribe' : tribe, 'members' : members, 'status_list' : status_list, 'filter' : f }, 
        context_instance=RequestContext(request))
        
def tribe_search(request, tribe_slug, page_slug=None, tribe_template='twtribes/tribe_search.html', page_template='twtribes/tribe_page.html', error_template='twtribes/tribe_error.html'):
    """ Django view function that displays search results of tribe interest terms or a page of interest terms
    """
    tribe = get_object_or_404(Tribe, slug__iexact=tribe_slug)
    members = tribe.member_set.order_by('twitter_account')

    if page_slug:
        page = get_object_or_404(Page, slug__iexact=page_slug)
    else:
        page = None

    # initialize the API, using the master tribe username and password
    # using the username and password for a tribe allows for API rate limit lifting at Twitter
    # NEW: You should look into using a single sign on OAuth token in settings instead of simple auth clear text passwords
    try:
        search_results = get_search_results(tribe, page)
        results = search_results["results"]
        if request.GET and 'filter' in request.GET:
            f = request.GET['filter']
            f_upper = f.upper()
            results = [s for s in results if s["text"].upper().find(f_upper) > -1 or s["from_user"].upper().find(f_upper) > -1]
        else:
            f = None
            
    except twitter.api.TwitterHTTPError, e:
        # an HTTPError means that the Twitter api returned an error, parse it and return it to an error template
        error = parse_twitter_http_error(e.e)

        return render_to_response(error_template,
            { 'error' : error, 'exception' : e }, 
            context_instance=RequestContext(request))

    return render_to_response(page_template if page else tribe_template,
        { 'tribe' : tribe, 'members' : members, 'search' : search_results, 'results' : results, 'filter' : f, 'page' : page }, 
        context_instance=RequestContext(request))
