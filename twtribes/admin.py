from django.contrib import admin
from models import *

class MemberAdmin(admin.ModelAdmin):
    list_display = ('twitter_account','tribe','note')

admin.site.register(Member, MemberAdmin)

class InterestTermAdmin(admin.ModelAdmin):
    list_display = ('term','tribe')

admin.site.register(InterestTerm, InterestTermAdmin)

class InterestTermInlineAdmin(admin.TabularInline):
    model = InterestTerm

class MemberInlineAdmin(admin.TabularInline):
    model = Member

class ExcludedUserInlineAdmin(admin.TabularInline):
    model=ExcludedUser
    
class ExcludedRegexpInlineAdmin(admin.TabularInline):
    model=ExcludedRegexp

class PageAdmin(admin.ModelAdmin):
    list_display = ('slug','title')

admin.site.register(Page, PageAdmin)
    
class TribeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [ MemberInlineAdmin, InterestTermInlineAdmin,
                ExcludedUserInlineAdmin, ExcludedRegexpInlineAdmin ]

admin.site.register(Tribe, TribeAdmin)