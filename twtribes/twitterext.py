import twitter
import simplejson
import calendar
import rfc822
from datetime import datetime
import pytz

class SearchStatus(object):
    def __init__(self, json):
        for k,v in json.items():
            if k != 'results':
                setattr(self, k, v)
            else:
                self.results = [ SearchResult(r) for r in v ]
    
class SearchResult(object):
    
    def __init__(self, json):
        for k,v in json.items():
            setattr(self, k, v)
    
    def GetCreatedAtInSeconds(self):
        '''Get the time this status message was posted, in seconds since the epoch.

            Returns:
                The time this status message was posted, in seconds since the epoch.
        '''
        
        return calendar.timegm(rfc822.parsedate(self.created_at))

    created_at_in_seconds = property(GetCreatedAtInSeconds,
                                 doc="The time this status message was "
                                 "posted, in seconds since the epoch")
                                 
    def GetCreatedAtAsDateTime(self):
        return datetime.fromtimestamp(self.created_at_in_seconds)
        
    created_at_as_datetime = property(GetCreatedAtAsDateTime,
                                     doc="The time this status message was "
                                     "posted converted to a datetime object")
    
class SearchApi(twitter.Api):
    """docstring for SearchApi"""
    def __init__(self, *argl, **argd):
        super(SearchApi, self).__init__(*argl, **argd)
        
    def Search(self, query, rpp=100):
        """ 
        Returns twitter search results
        """
        parameters = {}
        parameters['q'] = query
        parameters['rpp'] = rpp
        url = 'http://search.twitter.com/search.json'
        json = self._FetchUrl(url, parameters=parameters)
        data = simplejson.loads(json)
        
        if 'error' in data:
            raise twitter.TwitterError(data["error"])
        
        return SearchStatus(data)        