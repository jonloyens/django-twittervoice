from django.db import models

class Tribe(models.Model):
    """A group of twitter users with a common interest or purpose"""
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    master_account = models.CharField(blank=True, max_length=100)
    master_password = models.CharField(blank=True, max_length=100)
    update_interval = models.IntegerField(default=0)
    max_status = models.IntegerField(default=10)

    def __unicode__(self):
        return self.name

class InterestTerm(models.Model):
    """A term that the tribe is interested in for the live feed view"""
    
    term = models.CharField(max_length=255)
    tribe = models.ForeignKey(Tribe)
    
    def __unicode__(self):
        return self.term

class Member(models.Model):
    """A twitter user account that's a member of a tribe"""
    
    twitter_account = models.CharField(max_length=255)
    note = models.CharField(blank=True, max_length=255)
    tribe = models.ForeignKey(Tribe)

    def __unicode__(self):
        return self.tribe.name + ": " + self.twitter_account
