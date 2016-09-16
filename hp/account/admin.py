# -*- coding: utf-8 -*-
#
# This file is part of the jabber.at homepage (https://github.com/jabber-at/hp).
#
# This project is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This project is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-xmpp-account.
# If not, see <http://www.gnu.org/licenses/>.

import logging

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from .models import Confirmation
from .models import GpgKey
from .models import User
from .models import UserLogEntry
from .tasks import resend_confirmations

log = logging.getLogger(__name__)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_fieldsets = (
        (None, {
            'fields': ('username', 'email', 'gpg_fingerprint'),
        }),
    )
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'registered', 'registration_method', 'confirmed',
                       'gpg_fingerprint'),
        }),
    )
    list_display = ('username', 'email', 'registered', 'confirmed', )
    list_filter = ('is_superuser', )
    ordering = ('-registered', )
    readonly_fields = ['username', 'registered', ]
    search_fields = ['username', 'email', ]


@admin.register(UserLogEntry)
class UserLogEntryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'created')
    ordering = ('-created', )


@admin.register(GpgKey)
class GpgKeyAdmin(admin.ModelAdmin):
    actions = ['refresh']
    list_display = ('user', 'fingerprint', 'expires', 'valid', 'usable')
    list_select_related = ('user', )
    list_filter = ('revoked', )
    ordering = ('-created', )
    search_fields = ('fingerprint', 'user__username', 'user__email', )

    def valid(self, obj):
        return not obj.revoked  # just the inverse, more intuitive
    valid.boolean = True

    def usable(self, obj):
        now = timezone.now()
        if obj.expires:
            return obj.expires > now and not obj.revoked
        else:
            return not obj.revoked
    usable.boolean = True

    def refresh(self, request, queryset):
        for obj in queryset:
            try:
                obj.refresh()
            except Exception as e:
                log.exception(e)
                messages.error(request, _('Error importing %s: %s') % (obj.fingerprint, e))
    refresh.short_description = _('Refresh keys from keyserver.')


@admin.register(Confirmation)
class ConfirmationAdmin(admin.ModelAdmin):
    actions = ['resend']
    list_display = ('key', 'user', 'address', 'purpose', 'to', 'expires', )
    list_filter = ('purpose', )
    list_select_related = ('user', 'address', )
    search_fields = ('key', 'to', 'user__username', 'user__email', )

    def resend(self, request, queryset):
        resend_confirmations.delay(*queryset.values_list('pk', flat=True))
    resend.short_description = _('Resend confirmations')


admin.site.unregister(Group)
