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

class TribeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [ MemberInlineAdmin, InterestTermInlineAdmin ]

admin.site.register(Tribe, TribeAdmin)